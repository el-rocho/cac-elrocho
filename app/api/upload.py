import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Paciente, Informe, Analito, Medicion, AuditoriaRango
from app.schemas import AnaliticaPreviewResponse, ConfirmacionRequest
from app.services.llm_service import analyze_pdf_with_llm
from app.services.metrics import calculate_ratios

router = APIRouter(prefix="/upload", tags=["Carga de Analíticas"])

@router.post("", response_model=AnaliticaPreviewResponse)
async def upload_pdf_for_analysis(file: UploadFile = File(...)):
    """
    Recibe un documento PDF, lo analiza mediante el LLM (Gemini) y genera
    un borrador estructurado para confirmación previa por el usuario.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se admiten documentos en formato PDF.")

    temp_id = str(uuid.uuid4())
    upload_dir = settings.DATA_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    temp_path = upload_dir / f"temp_{temp_id}.pdf"

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Analizar el archivo con el servicio LLM
        preview = await analyze_pdf_with_llm(temp_path, temp_id)
        return preview

    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=f"Error al procesar el archivo: {str(e)}")

@router.post("/confirm")
def confirm_analitica(req: ConfirmacionRequest, db: Session = Depends(get_db)):
    """
    Consolida e inserta de forma definitiva en la base de datos la analítica
    revisada y aprobada por el usuario.
    """
    upload_dir = settings.DATA_DIR / "uploads"
    temp_path = upload_dir / f"temp_{req.temp_id}.pdf"
    
    # 1. Obtener o crear paciente
    paciente = db.query(Paciente).first()
    if not paciente:
        paciente = Paciente(
            nombre_completo="Usuario Clínico",
            fecha_nacimiento="1980-01-01",
            dni="00000000T",
            centro_referencia="Hospital Clínico"
        )
        db.add(paciente)
        db.flush()

    # 2. Formato de etiqueta corta (DD/MM/AA)
    partes_fecha = req.fecha.split("-")
    if len(partes_fecha) == 3:
        etiq_corta = f"{partes_fecha[2]}/{partes_fecha[1]}/{partes_fecha[0][2:]}"
    else:
        etiq_corta = req.fecha

    # 3. Guardar archivo definitivo
    nombre_archivo = f"{req.fecha}_{req.laboratorio.replace(' ', '_')}.pdf"
    ruta_definitiva = upload_dir / nombre_archivo
    if temp_path.exists():
        shutil.move(str(temp_path), str(ruta_definitiva))

    # 4. Crear registro de Informe
    informe = Informe(
        paciente_id=paciente.id,
        fecha=req.fecha,
        etiqueta_corta=etiq_corta,
        laboratorio=req.laboratorio,
        facultativo=req.facultativo or "No especificado",
        archivo_pdf=nombre_archivo,
        dictamen_global=req.dictamen_global or "Control favorable",
        estado="confirmado"
    )
    db.add(informe)
    db.flush()

    # 5. Insertar mediciones y calcular ratios
    mediciones_dict = {}
    
    # Mapeo de analitos conocidos
    code_map = {
        "glucosa": "GLUCOSE",
        "hba1c": "HBA1C",
        "creatinina": "CREATININE",
        "urea": "UREA",
        "ácido úrico": "URIC_ACID",
        "acido urico": "URIC_ACID",
        "colesterol total": "CHOLESTEROL_TOTAL",
        "triglicéridos": "TRIGLYCERIDES",
        "trigliceridos": "TRIGLYCERIDES",
        "hdl": "HDL",
        "ldl": "LDL",
        "psa total": "PSA_TOTAL",
        "psa libre": "PSA_FREE",
        "tsh": "TSH",
        "vitamina d": "VITAMIN_D"
    }

    for item in req.mediciones:
        code_key = None
        for k, v in code_map.items():
            if k in item.nombre.lower():
                code_key = v
                break

        if not code_key:
            code_key = item.nombre.upper().replace(" ", "_")[:30]

        analito = db.query(Analito).filter_by(codigo=code_key).first()
        if not analito:
            analito = Analito(
                codigo=code_key,
                nombre_visible=item.nombre,
                categoria="bioquimica",
                unidad_estandar=item.unidad,
                ref_texto_defecto=item.rango_referencia
            )
            db.add(analito)
            db.flush()

        try:
            num_val = float(str(item.valor).replace(",", ".").split()[0])
            mediciones_dict[code_key] = num_val
        except (ValueError, TypeError):
            num_val = None

        med = Medicion(
            informe_id=informe.id,
            analito_id=analito.id,
            valor_numerico=num_val,
            valor_texto=str(item.valor) if num_val is None else None,
            unidad=item.unidad,
            ref_texto=item.rango_referencia
        )
        db.add(med)

    # 6. Calcular ratios automáticos y guardarlos si no venían en el informe
    ratios_calc = calculate_ratios(mediciones_dict)
    ratio_names = {
        "RATIO_COL_HDL": ("Cociente Col/HDL", "ratio", "< 4.5"),
        "RATIO_LDL_HDL": ("Cociente LDL/HDL", "ratio", "< 3.0"),
        "RATIO_LDL_COL": ("Ratio LDL / Col. Total", "ratio", "< 0.65"),
        "RATIO_HDL_COL": ("Ratio HDL / Col. Total", "ratio", "> 0.20"),
        "RATIO_TG_COL": ("Ratio TG / Col. Total", "ratio", "< 0.50"),
        "RATIO_PSA_L_T": ("Ratio PSA L/T", "ratio", "> 0.20")
    }

    for r_code, r_val in ratios_calc.items():
        nom, uni, ref = ratio_names.get(r_code, (r_code, "ratio", ""))
        a_ratio = db.query(Analito).filter_by(codigo=r_code).first()
        if not a_ratio:
            a_ratio = Analito(
                codigo=r_code,
                nombre_visible=nom,
                categoria="bioquimica",
                unidad_estandar=uni,
                ref_texto_defecto=ref
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
    return {
        "status": "success",
        "message": f"Analítica del {req.fecha} incorporada con éxito al historial.",
        "informe_id": informe.id
    }
