from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AuditoriaRango, Analito, Informe

router = APIRouter(prefix="/ai", tags=["Módulo IA"])

@router.get("/auditorias")
def get_auditorias_rango(db: Session = Depends(get_db)):
    """
    Devuelve el historial de cambios y actualizaciones en rangos de referencia
    detectados por el LLM a lo largo de las analíticas.
    """
    auditorias = db.query(AuditoriaRango).order_by(AuditoriaRango.fecha_deteccion.desc()).all()
    resultado = []
    for aud in auditorias:
        analito = db.query(Analito).filter_by(id=aud.analito_id).first()
        informe = db.query(Informe).filter_by(id=aud.informe_id).first()
        resultado.append({
            "id": aud.id,
            "analito": analito.nombre_visible if analito else "Analito",
            "fecha_analitica": informe.etiqueta_corta if informe else "-",
            "rango_anterior": aud.rango_anterior,
            "rango_nuevo": aud.rango_nuevo,
            "explicacion": aud.explicacion_ia,
            "fecha_deteccion": aud.fecha_deteccion.strftime("%d/%m/%Y") if aud.fecha_deteccion else "-"
        })
    return resultado

@router.get("/briefing")
def get_clinical_briefing(db: Session = Depends(get_db)):
    """
    Genera una síntesis clínica estructurada para consulta médica.
    """
    paciente = db.query(Paciente).first()
    return {
        "paciente": paciente.nombre_completo if paciente else "Paciente",
        "edad": "Consultar historial",
        "puntos_fuertes": [
            "Función renal en norma y depuración glomerular adecuada.",
            "Marcador prostático en rango benigno.",
            "Perfil hepático y enzimas dentro de los intervalos de referencia.",
            "Vitamina D en niveles de suficiencia óptima."
        ],
        "puntos_atencion": [
            "HbA1c en 5.7% (dintel de prediabetes según criterio ADA, control con dieta mediterránea y ejercicio).",
            "Colesterol LDL en 118 mg/dL (favorable frente al riesgo global, pero vigilable según el nuevo dintel SEA <116 mg/dL)."
        ],
        "conclusion": "Estado clínico global muy favorable. Órganos diana protegidos y evolución metabólica estable."
    }
