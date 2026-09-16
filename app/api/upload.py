import re
import uuid
import shutil
import hashlib
import logging
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Paciente, Informe, Analito, Medicion, AuditoriaRango
from app.schemas import AnaliticaPreviewResponse, ConfirmacionRequest
from app.services.llm_service import analyze_pdf_with_llm
from app.services.metrics import calculate_ratios
from app.services.analito_normalizer import normalize_analito, CANONICAL_ANALITOS

logger = logging.getLogger(__name__)

def sanitize_filename(name: str) -> str:
    """Elimina caracteres incompatibles con el sistema de archivos (barras, dos puntos, etc.)."""
    clean = re.sub(r'[\\/*?:"<>|]', '_', name or '')
    clean = re.sub(r'[\s_]+', '_', clean).strip('_.')
    return clean[:80] if clean else "laboratorio"

router = APIRouter(prefix="/upload", tags=["Carga de Analíticas"])

@router.post("", response_model=AnaliticaPreviewResponse)
async def upload_pdf_for_analysis(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Recibe un documento PDF, calcula su hash SHA-256 para prevenir duplicados,
    lo analiza mediante el LLM (Gemini) y genera un borrador estructurado para confirmación previa por el usuario.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se admiten documentos en formato PDF.")

    temp_id = str(uuid.uuid4())
    upload_dir = settings.DATA_DIR / "uploads"
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
        upload_dir = settings.DATA_DIR / "uploads"
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

        # 4. Determinar si se actualiza un informe existente o se crea uno nuevo
        informe = None
        es_sobrescritura = False

        if req.sobrescribir_existente:
            if req.informe_id_a_reemplazar:
                informe = db.query(Informe).filter_by(id=req.informe_id_a_reemplazar).first()
            if not informe and file_sha256:
                informe = db.query(Informe).filter_by(sha256=file_sha256).first()
            if not informe and req.fecha:
                informe = db.query(Informe).filter(Informe.fecha == req.fecha).first()

        if informe:
            es_sobrescritura = True
            informe.fecha = req.fecha
            informe.etiqueta_corta = etiq_corta
            informe.laboratorio = req.laboratorio
            informe.facultativo = req.facultativo or "No especificado"
            informe.archivo_pdf = nombre_archivo
            informe.sha256 = file_sha256
            informe.dictamen_global = req.dictamen_global or "Control favorable"
            informe.estado = "confirmado"

            # Vaciar mediciones anteriores para reescribirlas limpias
            db.query(Medicion).filter_by(informe_id=informe.id).delete()
            db.query(AuditoriaRango).filter_by(informe_id=informe.id).delete()
            db.flush()
        else:
            informe = Informe(
                paciente_id=paciente.id,
                fecha=req.fecha,
                etiqueta_corta=etiq_corta,
                laboratorio=req.laboratorio,
                facultativo=req.facultativo or "No especificado",
                archivo_pdf=nombre_archivo,
                sha256=file_sha256,
                dictamen_global=req.dictamen_global or "Control favorable",
                estado="confirmado"
            )
            db.add(informe)
            db.flush()

        # 5. Insertar mediciones y calcular ratios
        mediciones_dict = {}
        analitos_procesados = {}  # code_key -> Medicion

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

            try:
                num_val = float(str(item.valor).replace(",", ".").split()[0])
            except (ValueError, TypeError, IndexError):
                num_val = None

            # Si este analito canónico ya se procesó en este informe, resolvemos colisiones:
            # Priorizar siempre valores numéricos de suero sobre valores nulos o cualitativos
            if code_key in analitos_procesados:
                med_existente = analitos_procesados[code_key]
                if med_existente.valor_numerico is None and num_val is not None:
                    med_existente.valor_numerico = num_val
                    med_existente.valor_texto = None
                    med_existente.unidad = item.unidad or norm_unit
                    med_existente.ref_texto = item.rango_referencia
                    mediciones_dict[code_key] = num_val
                continue

            med = Medicion(
                informe_id=informe.id,
                analito_id=analito.id,
                valor_numerico=num_val,
                valor_texto=str(item.valor) if num_val is None else None,
                unidad=item.unidad or norm_unit,
                ref_texto=item.rango_referencia
            )
            db.add(med)
            db.flush()
            analitos_procesados[code_key] = med

            if num_val is not None:
                mediciones_dict[code_key] = num_val

        # 6. Calcular ratios automáticos y guardarlos si no venían en el informe
        ratios_calc = calculate_ratios(mediciones_dict)
        ratio_names = {
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

            med_ratio = Medicion(
                informe_id=informe.id,
                analito_id=a_ratio.id,
                valor_numerico=r_val,
                unidad=uni,
                ref_texto=ref
            )
            db.add(med_ratio)

        db.commit()
        msg = f"Analítica del {req.fecha} actualizada y sobrescrita con éxito en el historial." if es_sobrescritura else f"Analítica del {req.fecha} incorporada con éxito al historial."
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

