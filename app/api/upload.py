import re
import uuid
import shutil
import hashlib
import logging
import csv
import io
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Paciente, Informe, Analito, Medicion, AuditoriaRango
from app.schemas import AnaliticaPreviewResponse, ConfirmacionRequest, RegenerateDictamenRequest, RegenerateDictamenResponse
from app.services.llm_service import analyze_pdf_with_llm, generate_clinical_summary_from_measurements
from app.services.metrics import calculate_ratios
from app.services.analito_normalizer import normalize_analito, normalize_valor_numerico, standardize_medicion, CANONICAL_ANALITOS, evaluar_estado_semaforo

logger = logging.getLogger(__name__)

def sanitize_filename(name: str) -> str:
    """Elimina caracteres incompatibles con el sistema de archivos (barras, dos puntos, etc.)."""
    clean = re.sub(r'[\\/*?:"<>|]', '_', name or '')
    clean = re.sub(r'[\s_]+', '_', clean).strip('_.')
    return clean[:80] if clean else "laboratorio"

router = APIRouter(prefix="/upload", tags=["Carga de Analíticas"])


def _fecha_csv(value: str) -> str | None:
    """Convierte las cabeceras de fecha del historial a ISO."""
    value = (value or "").strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _etiqueta_corta(fecha: str) -> str:
    partes = fecha.split("-")
    return f"{partes[2]}/{partes[1]}/{partes[0][2:]}" if len(partes) == 3 else fecha


def _es_formula_leucocitaria_relativa(nombre: str, unidad: str, referencia: str) -> bool:
    """Reconoce filas porcentuales del hemograma cuando el CSV no incluye unidad.

    Algunos laboratorios llaman a estas filas solo ``MONOCITOS`` o
    ``SEGMENTADOS`` y dejan la unidad vacía. Sus rangos característicos (1-10,
    0-5, 0-4, 20-40, 45-70) evitan confundirlas con recuentos absolutos.
    """
    nombre_limpio = (nombre or "").lower()
    unidad_limpia = (unidad or "").strip().lower()
    if "%" in unidad_limpia or "relativ" in nombre_limpio or "%" in nombre_limpio:
        return True
    if unidad_limpia:
        return False
    numeros = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[\.,]\d+)?", referencia or "")]
    max_ref = max(numeros) if numeros else None
    rangos_porcentuales = {
        "linfocito": (15, 50),
        "monocito": (5, 20),
        "eosin": (2, 12),
        "baso": (1, 8),
        "basó": (1, 8),
        "segmentado": (35, 85),
        "neutro": (35, 85),
    }
    return bool(max_ref is not None and any(minimo <= max_ref <= maximo for clave, (minimo, maximo) in rangos_porcentuales.items() if clave in nombre_limpio))


def _guardar_medicion_csv(db: Session, informe: Informe, nombre: str, valor: str,
                          unidad: str, referencia: str) -> None:
    """Guarda una celda del CSV aplicando la misma normalización que el PDF."""
    # La tabla del usuario deja la unidad vacía en la fórmula leucocitaria.
    # Marcamos explícitamente el porcentaje antes de normalizarla.
    nombre_normalizacion = f"{nombre} %" if _es_formula_leucocitaria_relativa(nombre, unidad, referencia) else nombre
    code, nombre_normalizado, categoria, unidad_normalizada = normalize_analito(
        nombre_normalizacion, unidad=unidad, valor=valor
    )
    analito = db.query(Analito).filter_by(codigo=code).first()
    if not analito:
        from app.services.analito_normalizer import get_analito_order
        analito = Analito(
            codigo=code, nombre_visible=nombre_normalizado, categoria=categoria,
            unidad_estandar=unidad_normalizada, ref_texto_defecto=referencia,
            orden=get_analito_order(code)
        )
        db.add(analito)
        db.flush()

    numero, texto, unidad_estandar, referencia_estandar = standardize_medicion(
        code, valor, unidad, referencia
    )
    referencia_final = referencia_estandar or referencia
    estado = evaluar_estado_semaforo(numero, referencia_final) if numero is not None else "Normal"
    medicion = db.query(Medicion).filter_by(informe_id=informe.id, analito_id=analito.id).first()
    if not medicion:
        medicion = Medicion(informe_id=informe.id, analito_id=analito.id, unidad=unidad_estandar or unidad_normalizada)
        db.add(medicion)
    medicion.valor_numerico = numero
    medicion.valor_texto = texto if numero is None else None
    medicion.unidad = unidad_estandar or unidad_normalizada
    medicion.ref_texto = referencia_final
    medicion.estado_semaforo = estado

    # Corrige importaciones CSV anteriores que clasificaron erróneamente una
    # fila porcentual como absoluta. Solo se toca un informe cuyo origen sea
    # CSV, para no eliminar un recuento absoluto procedente de un PDF.
    codigo_absoluto_previo = {
        "LINFOCITOS_PCT": "LINFOCITOS_ABS",
        "NEUTROFILOS_PCT": "NEUTROFILOS_ABS",
        "MONOCITOS_PCT": "MONOCITOS_ABS",
        "EOSINOFILOS_PCT": "EOSINOFILOS_ABS",
        "BASOFILOS_PCT": "BASOFILOS_ABS",
    }.get(code)
    if codigo_absoluto_previo and (informe.archivo_pdf or "").startswith("CSV:"):
        anterior = db.query(Medicion).join(Analito).filter(
            Medicion.informe_id == informe.id, Analito.codigo == codigo_absoluto_previo
        ).first()
        if anterior:
            db.delete(anterior)


@router.post("/csv")
async def upload_history_csv(
    file: UploadFile = File(...),
    confirmar_coincidencias: bool = Form(False),
    db: Session = Depends(get_db)
):
    """Importa la tabla ancha del panel Historial: analitos en filas y fechas en columnas."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Solo se admiten archivos en formato CSV.")
    try:
        raw = await file.read()
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="El archivo CSV debe estar codificado en UTF-8 o Latin-1.")

    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"
    rows = list(csv.reader(io.StringIO(text), dialect))
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="El CSV debe incluir una cabecera y al menos una fila de parámetros.")

    header = [cell.strip() for cell in rows[0]]
    if len(header) < 4:
        raise HTTPException(status_code=400, detail="Se requieren las columnas Parámetro, Unidad, Referencia y al menos una fecha.")
    date_columns = [(index, _fecha_csv(name)) for index, name in enumerate(header[3:], start=3)]
    date_columns = [(index, fecha) for index, fecha in date_columns if fecha]
    if not date_columns:
        raise HTTPException(status_code=400, detail="No se encontró ninguna fecha válida en la cabecera. Usa AAAA-MM-DD o DD/MM/AAAA.")

    # Una coincidencia se define por la fecha de la analítica, igual que en el
    # historial. El usuario decide explícitamente si desea complementar esos
    # informes antes de que se modifique ningún dato.
    fechas_csv = [fecha for _, fecha in date_columns]
    coincidencias = [
        fecha for (fecha,) in db.query(Informe.fecha).filter(Informe.fecha.in_(fechas_csv)).all()
    ]
    if coincidencias and not confirmar_coincidencias:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "El CSV contiene fechas que ya existen en el historial.",
                "total_coincidencias": len(coincidencias)
            }
        )

    paciente = db.query(Paciente).first()
    if not paciente:
        paciente = Paciente(nombre_completo="", sexo="No especificado")
        db.add(paciente)
        db.flush()

    importados = 0
    actualizados = 0
    try:
        for column, fecha in date_columns:
            filas_con_valor = []
            for row in rows[1:]:
                if len(row) <= column:
                    continue
                nombre = row[0].strip() if row else ""
                valor = row[column].strip()
                if not nombre or not valor:
                    continue
                unidad = row[1].strip() if len(row) > 1 else ""
                referencia = row[2].strip() if len(row) > 2 else ""
                filas_con_valor.append((nombre, valor, unidad, referencia))
            if not filas_con_valor:
                continue

            informe = db.query(Informe).filter_by(fecha=fecha).first()
            if informe:
                actualizados += 1
            else:
                informe = Informe(
                    paciente_id=paciente.id, fecha=fecha, etiqueta_corta=_etiqueta_corta(fecha),
                    laboratorio="Importado desde CSV", facultativo="No especificado",
                    archivo_pdf=f"CSV: {sanitize_filename(file.filename)}",
                    dictamen_global="Importado desde archivo CSV", estado="confirmado"
                )
                db.add(informe)
                db.flush()
                importados += 1

            for nombre, valor, unidad, referencia in filas_con_valor:
                _guardar_medicion_csv(db, informe, nombre, valor, unidad, referencia)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Error al importar CSV", exc_info=True)
        raise HTTPException(status_code=400, detail=f"No se pudo importar el CSV: {exc}")

    if not importados and not actualizados:
        raise HTTPException(status_code=400, detail="El CSV no contiene valores para importar.")
    # El encabezado refleja la analítica más reciente disponible. Generamos un
    # resumen conciso solo con un LLM activo; no se inventa una interpretación
    # clínica cuando ningún modelo está configurado o puede responder.
    resumen_generado = False
    try:
        ultimo_informe = db.query(Informe).order_by(Informe.fecha.desc()).first()
        mediciones_ultima = db.query(Medicion).filter_by(informe_id=ultimo_informe.id).all() if ultimo_informe else []
        datos_resumen = [
            {
                "nombre": med.analito.nombre_visible if med.analito else "Analito",
                "valor": med.valor_numerico if med.valor_numerico is not None else (med.valor_texto or ""),
                "unidad": med.unidad or "",
                "rango_referencia": med.ref_texto or ""
            }
            for med in mediciones_ultima
            if med.analito and (med.valor_numerico is not None or med.valor_texto)
        ]
        resultado_resumen = await generate_clinical_summary_from_measurements(
            mediciones=datos_resumen,
            fecha=ultimo_informe.fecha,
            laboratorio=ultimo_informe.laboratorio or "Importado desde CSV",
            facultativo=ultimo_informe.facultativo,
            paciente_nombre=paciente.nombre_completo if paciente else "Paciente",
            modo="resumido"
        )
        if resultado_resumen.get("llm_utilizado"):
            ultimo_informe.dictamen_global = resultado_resumen.get("dictamen_global") or "Resumen de salud actualizado."
            # El resumen conciso ya incorpora las alteraciones y sus rangos.
            # No repetimos las alertas como subtítulo en la cabecera.
            ultimo_informe.observaciones_ia = None
            resumen_generado = True
        else:
            ultimo_informe.dictamen_global = "Informe resumen de salud actual no generado. Active la funcionalidad LLM."
            ultimo_informe.observaciones_ia = None
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("No se pudo generar el resumen tras importar CSV: %s", exc)

    return {
        "message": f"CSV importado: {importados} analítica(s) nueva(s) y {actualizados} actualizada(s).",
        "nuevas": importados, "actualizadas": actualizados,
        "resumen_generado": resumen_generado
    }

@router.post("/regenerate-dictamen", response_model=RegenerateDictamenResponse)
async def regenerate_dictamen_endpoint(req: RegenerateDictamenRequest, db: Session = Depends(get_db)):
    """
    Regenera dinámicamente el dictamen clínico y las alertas IA utilizando el LLM,
    basándose exclusivamente en las mediciones actuales de la tabla (incluyendo las correcciones del usuario).
    """
    paciente = db.query(Paciente).first()
    pac_nom = paciente.nombre_completo if paciente else "Paciente"
    resultado = await generate_clinical_summary_from_measurements(
        mediciones=req.mediciones,
        fecha=req.fecha,
        laboratorio=req.laboratorio,
        facultativo=req.facultativo,
        paciente_nombre=pac_nom,
        modo=req.modo or "completo"
    )
    return RegenerateDictamenResponse(
        dictamen_global=resultado.get("dictamen_global", "Dictamen actualizado con las mediciones vigentes."),
        alertas_ia=resultado.get("alertas_ia", [])
    )

@router.post("", response_model=AnaliticaPreviewResponse)
async def upload_pdf_for_analysis(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Recibe un documento PDF, calcula su hash SHA-256 para prevenir duplicados,
    lo analiza mediante el LLM (Gemini) y genera un borrador estructurado para confirmación previa por el usuario.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se admiten documentos en formato PDF.")

    temp_id = str(uuid.uuid4())
    upload_dir = settings.paths.uploads_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_path = upload_dir / f"temp_{temp_id}.pdf"

    try:
        content = await file.read()
        file_sha256 = hashlib.sha256(content).hexdigest()

        with open(temp_path, "wb") as buffer:
            buffer.write(content)

        paciente = db.query(Paciente).first()
        # Analizar el archivo con el servicio LLM, validar discrepancias de paciente y comprobar duplicidad
        preview = await analyze_pdf_with_llm(
            temp_path,
            temp_id,
            paciente_db=paciente,
            db=db,
            sha256=file_sha256
        )
        return preview

    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        logger.error(f"Error al procesar el archivo subido: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")

@router.post("/confirm")
def confirm_analitica(req: ConfirmacionRequest, db: Session = Depends(get_db)):
    """
    Consolida e inserta de forma definitiva en la base de datos la analítica
    revisada y aprobada por el usuario. Permite actualizar y sobrescribir si ya existía.
    """
    try:
        upload_dir = settings.paths.uploads_dir
        upload_dir.mkdir(parents=True, exist_ok=True)
        temp_path = upload_dir / f"temp_{req.temp_id}.pdf"
        
        # Calcular SHA-256 si no venía en la petición
        file_sha256 = req.sha256
        if not file_sha256 and temp_path.exists():
            try:
                with open(temp_path, "rb") as f:
                    file_sha256 = hashlib.sha256(f.read()).hexdigest()
            except Exception as e:
                logger.warning(f"No se pudo calcular SHA-256 de {temp_path}: {e}")

        # 1. Obtener o crear paciente sin pre-rellenar datos falsos
        paciente = db.query(Paciente).first()
        if not paciente:
            paciente = Paciente(
                nombre_completo="",
                fecha_nacimiento=None,
                dni=None,
                sexo="No especificado",
                centro_referencia=None
            )
            db.add(paciente)
            db.flush()

        # 2. Formato de etiqueta corta (DD/MM/AA)
        partes_fecha = req.fecha.split("-")
        if len(partes_fecha) == 3:
            etiq_corta = f"{partes_fecha[2]}/{partes_fecha[1]}/{partes_fecha[0][2:]}"
        else:
            etiq_corta = req.fecha

        # 3. Guardar archivo definitivo de forma segura (sanitizando caracteres como / o \)
        clean_lab = sanitize_filename(req.laboratorio)
        nombre_archivo = f"{req.fecha}_{clean_lab}.pdf"
        ruta_definitiva = upload_dir / nombre_archivo
        if temp_path.exists():
            try:
                shutil.copy2(str(temp_path), str(ruta_definitiva))
                temp_path.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Aviso al archivar PDF definitivo: {e}")

        # 4. Determinar si se actualiza un informe existente, se fusiona o se crea uno nuevo
        informe = None
        modo = req.modo_coincidencia or ("reemplazar" if req.sobrescribir_existente else "fusionar")
        es_sobrescritura = False

        if modo in ("reemplazar", "fusionar"):
            if req.informe_id_a_reemplazar:
                informe = db.query(Informe).filter_by(id=req.informe_id_a_reemplazar).first()
            if not informe and file_sha256:
                informe = db.query(Informe).filter_by(sha256=file_sha256).first()
            if not informe and req.fecha:
                informe = db.query(Informe).filter(Informe.fecha == req.fecha).first()

        if informe:
            es_sobrescritura = True
            if modo == "reemplazar":
                informe.fecha = req.fecha
                informe.etiqueta_corta = etiq_corta
                informe.laboratorio = req.laboratorio
                informe.facultativo = req.facultativo or "No especificado"
                informe.referencia = req.referencia
                informe.archivo_pdf = nombre_archivo
                informe.sha256 = file_sha256
                informe.dictamen_global = req.dictamen_global or "Control favorable"
                informe.estado = "confirmado"

                # Vaciar mediciones anteriores para reescribirlas limpias
                db.query(Medicion).filter_by(informe_id=informe.id).delete()
                db.query(AuditoriaRango).filter_by(informe_id=informe.id).delete()
                db.flush()
            elif modo == "fusionar":
                informe.fecha = req.fecha
                informe.etiqueta_corta = etiq_corta

                # Combinar facultativos evitando repeticiones
                if req.facultativo and req.facultativo.strip() and req.facultativo.strip() != "No especificado":
                    new_fac = req.facultativo.strip()
                    if informe.facultativo and informe.facultativo.strip() != "No especificado":
                        partes_fac = [f.strip() for f in informe.facultativo.split("/") if f.strip()]
                        if new_fac not in partes_fac and new_fac.lower() not in [p.lower() for p in partes_fac]:
                            informe.facultativo = f"{informe.facultativo} / {new_fac}"
                    else:
                        informe.facultativo = new_fac

                # Combinar referencias evitando repeticiones
                if req.referencia and req.referencia.strip():
                    new_ref = req.referencia.strip()
                    if informe.referencia and informe.referencia.strip():
                        partes_ref = [r.strip() for r in informe.referencia.split("/") if r.strip()]
                        if new_ref not in partes_ref:
                            informe.referencia = f"{informe.referencia} / {new_ref}"
                    else:
                        informe.referencia = new_ref

                # Combinar laboratorios si son distintos
                if req.laboratorio and req.laboratorio.strip() and req.laboratorio.strip() != "Desconocido":
                    new_lab = req.laboratorio.strip()
                    if informe.laboratorio and informe.laboratorio.strip():
                        partes_lab = [l.strip() for l in informe.laboratorio.split("/") if l.strip()]
                        if new_lab not in partes_lab and new_lab.lower() not in [p.lower() for p in partes_lab]:
                            informe.laboratorio = f"{informe.laboratorio} / {new_lab}"
                    else:
                        informe.laboratorio = new_lab

                if req.dictamen_global and req.dictamen_global.strip() and req.dictamen_global != "Control favorable":
                    informe.dictamen_global = req.dictamen_global

                informe.estado = "confirmado"
                db.flush()
            else:
                informe = Informe(
                    paciente_id=paciente.id,
                    fecha=req.fecha,
                    etiqueta_corta=etiq_corta,
                    laboratorio=req.laboratorio,
                    facultativo=req.facultativo or "No especificado",
                    referencia=req.referencia,
                    archivo_pdf=nombre_archivo,
                    sha256=file_sha256,
                    dictamen_global=req.dictamen_global or "Control favorable",
                    estado="confirmado"
                )
                db.add(informe)
                db.flush()
        else:
            informe = Informe(
                paciente_id=paciente.id,
                fecha=req.fecha,
                etiqueta_corta=etiq_corta,
                laboratorio=req.laboratorio,
                facultativo=req.facultativo or "No especificado",
                referencia=req.referencia,
                archivo_pdf=nombre_archivo,
                sha256=file_sha256,
                dictamen_global=req.dictamen_global or "Control favorable",
                estado="confirmado"
            )
            db.add(informe)
            db.flush()

        # 5. Insertar o actualizar mediciones y calcular ratios
        mediciones_dict = {}
        existentes = db.query(Medicion).filter_by(informe_id=informe.id).all()
        analitos_procesados = {}  # code_key -> Medicion
        for em in existentes:
            if em.analito:
                analitos_procesados[em.analito.codigo] = em
                if em.valor_numerico is not None:
                    mediciones_dict[em.analito.codigo] = em.valor_numerico

        for item in req.mediciones:
            if not item.nombre or not item.nombre.strip():
                continue

            code_key, norm_nombre, norm_cat, norm_unit = normalize_analito(
                item.nombre,
                unidad=item.unidad,
                valor=item.valor,
                codigo_sugerido=getattr(item, "codigo", None)
            )

            analito = db.query(Analito).filter_by(codigo=code_key).first()
            if not analito:
                from app.services.analito_normalizer import get_analito_order
                analito = Analito(
                    codigo=code_key,
                    nombre_visible=norm_nombre,
                    categoria=norm_cat,
                    unidad_estandar=norm_unit,
                    ref_texto_defecto=item.rango_referencia,
                    orden=get_analito_order(code_key)
                )
                db.add(analito)
                db.flush()

            num_val, clean_val, std_unit, std_ref = standardize_medicion(
                code_key, item.valor, item.unidad, item.rango_referencia
            )

            ref_final = std_ref or item.rango_referencia
            calc_st = evaluar_estado_semaforo(num_val, ref_final) if num_val is not None else "Normal"
            est_final = calc_st if calc_st in ["Alto", "Bajo"] else (getattr(item, "estado_estimado", None) or "Normal")

            # Si este analito canónico ya se procesó en este informe, resolvemos colisiones:
            # Priorizar siempre valores numéricos de suero sobre valores nulos o cualitativos
            if code_key in analitos_procesados:
                med_existente = analitos_procesados[code_key]
                if num_val is not None or med_existente.valor_numerico is None:
                    med_existente.valor_numerico = num_val
                    med_existente.valor_texto = clean_val if num_val is None else None
                    med_existente.unidad = std_unit or norm_unit
                    med_existente.ref_texto = ref_final
                    med_existente.estado_semaforo = est_final
                if num_val is not None:
                    mediciones_dict[code_key] = num_val
                continue

            med = Medicion(
                informe_id=informe.id,
                analito_id=analito.id,
                valor_numerico=num_val,
                valor_texto=clean_val if num_val is None else None,
                unidad=std_unit or norm_unit,
                ref_texto=ref_final,
                estado_semaforo=est_final
            )
            db.add(med)
            db.flush()
            analitos_procesados[code_key] = med

            if num_val is not None:
                mediciones_dict[code_key] = num_val

        # 6. Calcular marcadores derivados y guardarlos si no venían en el informe
        ratios_calc = calculate_ratios(mediciones_dict)
        ratio_names = {
            "NON_HDL": ("Colesterol no-HDL", "mg/dL", "< 130 mg/dL"),
            "RATIO_COL_HDL": ("Colesterol Total / HDL (Castelli I)", "ratio", "< 5.0"),
            "RATIO_LDL_HDL": ("LDL / HDL (Castelli II)", "ratio", "< 4.3"),
            "RATIO_TG_HDL": ("Triglicéridos / HDL", "ratio", "< 2.0"),
            "RATIO_LDL_COL": ("Ratio LDL / Col. Total", "ratio", "< 0.65"),
            "RATIO_HDL_COL": ("Ratio HDL / Col. Total", "ratio", "> 0.20"),
            "RATIO_TG_COL": ("Ratio TG / Col. Total", "ratio", "< 0.50"),
            "RATIO_PSA_L_T": ("Ratio PSA Libre / Total", "%", "> 20 %")
        }

        for r_code, r_val in ratios_calc.items():
            if r_code in analitos_procesados and analitos_procesados[r_code].valor_numerico is not None:
                continue

            nom, uni, ref = ratio_names.get(r_code, (r_code, "ratio", ""))
            a_ratio = db.query(Analito).filter_by(codigo=r_code).first()
            if not a_ratio:
                from app.services.analito_normalizer import get_analito_order
                a_ratio = Analito(
                    codigo=r_code,
                    nombre_visible=nom,
                    categoria="bioquimica",
                    unidad_estandar=uni,
                    ref_texto_defecto=ref,
                    orden=get_analito_order(r_code)
                )
                db.add(a_ratio)
                db.flush()

            r_calc_st = evaluar_estado_semaforo(r_val, ref) if r_val is not None else "Normal"
            med_ratio = Medicion(
                informe_id=informe.id,
                analito_id=a_ratio.id,
                valor_numerico=r_val,
                unidad=uni,
                ref_texto=ref,
                estado_semaforo=r_calc_st
            )
            db.add(med_ratio)

        db.commit()
        if modo == "fusionar" and es_sobrescritura:
            msg = f"Analítica del {req.fecha} unificada y fusionada con éxito en el historial."
        elif es_sobrescritura:
            msg = f"Analítica del {req.fecha} actualizada y sobrescrita con éxito en el historial."
        else:
            msg = f"Analítica del {req.fecha} incorporada con éxito al historial."

        return {
            "status": "success",
            "message": msg,
            "informe_id": informe.id,
            "es_sobrescritura": es_sobrescritura
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error en confirm_analitica: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al guardar la analítica: {str(e)}")

