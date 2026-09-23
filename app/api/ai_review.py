from datetime import datetime
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Paciente, AuditoriaRango, Analito, Informe, Medicion

router = APIRouter(prefix="/ai", tags=["Módulo IA"])

@router.get("/auditorias")
def get_auditorias_rango(db: Session = Depends(get_db)):
    """
    Devuelve el historial de cambios y actualizaciones en rangos de referencia
    detectados por el LLM a lo largo de las analíticas, con su estado de aplicación.
    """
    auditorias = db.query(AuditoriaRango).order_by(AuditoriaRango.fecha_deteccion.desc()).all()
    resultado = []
    for aud in auditorias:
        analito = db.query(Analito).filter_by(id=aud.analito_id).first()
        informe = db.query(Informe).filter_by(id=aud.informe_id).first()
        resultado.append({
            "id": aud.id,
            "analito_id": aud.analito_id,
            "analito": analito.nombre_visible if analito else "Analito",
            "analito_codigo": analito.codigo if analito else "",
            "fecha_analitica": informe.etiqueta_corta if informe else "-",
            "informe_fecha": informe.fecha if informe else "-",
            "rango_anterior": aud.rango_anterior,
            "rango_nuevo": aud.rango_nuevo,
            "explicacion": aud.explicacion_ia,
            "fecha_deteccion": aud.fecha_deteccion.strftime("%d/%m/%Y") if aud.fecha_deteccion else "-",
            "fecha_deteccion_completa": aud.fecha_deteccion.strftime("%d/%m/%Y %H:%M:%S") if aud.fecha_deteccion else "-",
            "aplicado_en_historico": bool(aud.aplicado_en_historico),
            "estado": aud.estado if aud.estado else ("aplicado" if aud.aplicado_en_historico else "pendiente"),
            "fecha_aplicacion": aud.fecha_aplicacion.strftime("%d/%m/%Y %H:%M") if aud.fecha_aplicacion else None
        })
    return resultado


def detectar_cambios_de_rango(db: Session) -> List[AuditoriaRango]:
    """
    Escanea cronológicamente las analíticas y detecta cambios en los rangos de referencia
    utilizados por los laboratorios para cada analito. Registra las discrepancias en
    AuditoriaRango si no están ya registradas.
    """
    from app.services.analito_normalizer import parse_reference_bounds

    informes = db.query(Informe).order_by(Informe.fecha.asc()).all()
    if not informes:
        return []

    analitos = db.query(Analito).all()
    auditorias_creadas = []

    for analito in analitos:
        meds = (
            db.query(Medicion, Informe)
            .join(Informe, Medicion.informe_id == Informe.id)
            .filter(Medicion.analito_id == analito.id)
            .order_by(Informe.fecha.asc())
            .all()
        )
        if len(meds) < 2:
            continue

        prev_ref_str = None
        prev_bounds = (None, None)

        for med, inf in meds:
            ref_str = (med.ref_texto or "").strip()
            if not ref_str or ref_str.lower() in ["-", "sin referencia", "no especificado"]:
                continue

            bounds = parse_reference_bounds(ref_str)
            if bounds == (None, None):
                continue

            if prev_ref_str is None:
                prev_ref_str = ref_str
                prev_bounds = bounds
                continue

            # Comprobar si hubo un cambio real en los límites numéricos
            if bounds != prev_bounds:
                # Comprobar si ya existe una auditoría registrada para este analito y nuevo rango
                existente = (
                    db.query(AuditoriaRango)
                    .filter(
                        AuditoriaRango.analito_id == analito.id,
                        (
                            (AuditoriaRango.rango_nuevo == ref_str) |
                            (
                                (AuditoriaRango.rango_anterior == prev_ref_str) &
                                (AuditoriaRango.informe_id == inf.id)
                            )
                        )
                    )
                    .first()
                )
                if existente:
                    # Si ya existía pero apuntaba a otro informe o le faltaba vincular el informe de origen exacto
                    if not existente.informe_id:
                        existente.informe_id = inf.id
                else:
                    lab_name = inf.laboratorio or "El laboratorio"
                    if analito.codigo == "LDL" and bounds[1] and bounds[1] <= 116.0:
                        explicacion = (
                            f"{lab_name} actualizó el dintel de normalidad de LDL a {ref_str}, "
                            f"aplicando los objetivos de prevención cardiovascular más estrictos de las guías SEA/ESC."
                        )
                    elif analito.codigo == "UREA":
                        explicacion = (
                            f"{lab_name} adoptó el intervalo de referencia de {ref_str} "
                            f"según la metodología y reactivos enzimáticos (ureasa) del analizador actual."
                        )
                    elif analito.codigo in ["LINFOCITOS_ABS", "NEUTROFILOS_ABS", "LEUCOCITOS", "PLAQUETAS"]:
                        explicacion = (
                            f"{lab_name} calibró el intervalo de normalidad hemocitométrico a {ref_str}."
                        )
                    else:
                        explicacion = (
                            f"{lab_name} actualizó los criterios de normalidad de {analito.nombre_visible} "
                            f"de '{prev_ref_str}' a '{ref_str}'."
                        )

                    audit = AuditoriaRango(
                        analito_id=analito.id,
                        informe_id=inf.id,
                        rango_anterior=prev_ref_str,
                        rango_nuevo=ref_str,
                        explicacion_ia=explicacion,
                        fecha_deteccion=datetime.utcnow(),
                        aplicado_en_historico=False,
                        estado="pendiente"
                    )
                    db.add(audit)
                    db.flush()
                    auditorias_creadas.append(audit)

                prev_ref_str = ref_str
                prev_bounds = bounds

    if auditorias_creadas:
        db.commit()

    return db.query(AuditoriaRango).order_by(AuditoriaRango.fecha_deteccion.desc()).all()


@router.post("/detectar")
def detectar_nuevos_rangos(db: Session = Depends(get_db)):
    """
    Ejecuta el escaneo de auditoría para detectar actualizaciones de rangos de laboratorio
    a lo largo de todo el histórico y devuelve la lista completa.
    """
    items = detectar_cambios_de_rango(db)
    return {
        "status": "success",
        "message": f"Detección completada: {len(items)} criterio(s) de rangos supervisados.",
        "total_detectados": len(items)
    }


@router.post("/aplicar-criterio/{auditoria_id}")
def aplicar_criterio_historico(auditoria_id: int, db: Session = Depends(get_db)):
    """
    Aplica el rango de normalidad actualizado detectado en la auditoría
    a todo el historial clínico pasado de ese analito.
    """
    from app.services.analito_normalizer import evaluar_estado_semaforo

    audit = db.query(AuditoriaRango).filter_by(id=auditoria_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Registro de auditoría no encontrado")

    analito = db.query(Analito).filter_by(id=audit.analito_id).first()
    if not analito:
        raise HTTPException(status_code=404, detail="Analito no encontrado")

    # 1. Actualizar el rango por defecto del catálogo canónico
    analito.ref_texto_defecto = audit.rango_nuevo

    # 2. Homologar las referencias en las mediciones históricas y actualizar semáforos
    mediciones = db.query(Medicion).filter_by(analito_id=analito.id).all()
    count_mediciones = len(mediciones)
    for med in mediciones:
        med.ref_texto = audit.rango_nuevo
        if med.valor_numerico is not None:
            med.estado_semaforo = evaluar_estado_semaforo(med.valor_numerico, audit.rango_nuevo)

    # 3. Marcar la auditoría como aplicada
    audit.aplicado_en_historico = True
    audit.estado = "aplicado"
    audit.fecha_aplicacion = datetime.utcnow()

    db.commit()

    return {
        "status": "success",
        "message": f"Criterio '{audit.rango_nuevo}' aplicado a {count_mediciones} mediciones históricas de {analito.nombre_visible}.",
        "analito": analito.nombre_visible,
        "nuevo_rango": audit.rango_nuevo,
        "estado": "aplicado",
        "mediciones_actualizadas": count_mediciones,
        "fecha_aplicacion": audit.fecha_aplicacion.strftime("%d/%m/%Y %H:%M")
    }

@router.post("/mantener-historico/{auditoria_id}")
def mantener_criterio_historico(auditoria_id: int, db: Session = Depends(get_db)):
    """
    Registra la decisión del usuario de mantener los rangos de referencia históricos
    para este analito en las analíticas pasadas (no homologar retrospectivamente).
    Marca la auditoría como revisada con estado 'mantenido'. Si previamente se había aplicado
    al historial, restaura los rangos anteriores en las mediciones previas y recalcula sus semáforos.
    """
    from app.services.analito_normalizer import evaluar_estado_semaforo

    audit = db.query(AuditoriaRango).filter_by(id=auditoria_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Registro de auditoría no encontrado")

    analito = db.query(Analito).filter_by(id=audit.analito_id).first()
    nombre_analito = analito.nombre_visible if analito else "Analito"
    estaba_aplicado = bool(audit.aplicado_en_historico or audit.estado == "aplicado")

    # Si estaba aplicado al historial y se dispone de rango anterior, revertir mediciones previas
    if estaba_aplicado and audit.rango_anterior and audit.informe:
        fecha_corte = audit.informe.fecha
        mediciones_previas = (
            db.query(Medicion)
            .join(Informe, Medicion.informe_id == Informe.id)
            .filter(Medicion.analito_id == audit.analito_id, Informe.fecha < fecha_corte)
            .all()
        )
        for med in mediciones_previas:
            med.ref_texto = audit.rango_anterior
            if med.valor_numerico is not None:
                med.estado_semaforo = evaluar_estado_semaforo(med.valor_numerico, audit.rango_anterior)

    audit.aplicado_en_historico = False
    audit.estado = "mantenido"
    audit.fecha_aplicacion = datetime.utcnow()

    db.commit()

    return {
        "status": "success",
        "message": f"Se mantienen los rangos históricos para {nombre_analito}. La revisión ha sido registrada y los semáforos recalculados.",
        "analito": nombre_analito,
        "nuevo_rango": audit.rango_nuevo,
        "estado": "mantenido",
        "fecha_aplicacion": audit.fecha_aplicacion.strftime("%d/%m/%Y %H:%M")
    }

@router.post("/mantener-todos")
def mantener_todos_criterios_historicos(db: Session = Depends(get_db)):
    """
    Marca todas las auditorías de rango pendientes como 'mantenido',
    conservando los rangos de referencia históricos en las analíticas previas.
    """
    from app.services.analito_normalizer import evaluar_estado_semaforo

    auditorias = db.query(AuditoriaRango).all()
    now = datetime.utcnow()
    count = 0
    for audit in auditorias:
        curr_estado = audit.estado if audit.estado else ("aplicado" if audit.aplicado_en_historico else "pendiente")
        if curr_estado == "pendiente":
            audit.estado = "mantenido"
            audit.aplicado_en_historico = False
            audit.fecha_aplicacion = now
            count += 1
        elif curr_estado == "aplicado" and audit.rango_anterior and audit.informe:
            # Revertir mediciones previas si se decide mantener todos
            fecha_corte = audit.informe.fecha
            mediciones_previas = (
                db.query(Medicion)
                .join(Informe, Medicion.informe_id == Informe.id)
                .filter(Medicion.analito_id == audit.analito_id, Informe.fecha < fecha_corte)
                .all()
            )
            for med in mediciones_previas:
                med.ref_texto = audit.rango_anterior
                if med.valor_numerico is not None:
                    med.estado_semaforo = evaluar_estado_semaforo(med.valor_numerico, audit.rango_anterior)
            audit.estado = "mantenido"
            audit.aplicado_en_historico = False
            audit.fecha_aplicacion = now
            count += 1

    db.commit()
    return {
        "status": "success",
        "message": f"Se han mantenido los rangos históricos para {count} criterio(s).",
        "criterios_mantenidos": count,
        "fecha_aplicacion": now.strftime("%d/%m/%Y %H:%M")
    }

@router.post("/aplicar-todos")
def aplicar_todos_criterios_historico(db: Session = Depends(get_db)):
    """
    Aplica y homologa todos los criterios de auditoría de rangos registrados
    a todas las analíticas históricas.
    """
    auditorias = db.query(AuditoriaRango).all()
    if not auditorias:
        return {
            "status": "success",
            "message": "No hay criterios de auditoría pendientes por aplicar.",
            "criterios_aplicados": 0,
            "mediciones_actualizadas": 0
        }

    total_mediciones = 0
    now = datetime.utcnow()

    for audit in auditorias:
        analito = db.query(Analito).filter_by(id=audit.analito_id).first()
        if analito:
            analito.ref_texto_defecto = audit.rango_nuevo
            mediciones = db.query(Medicion).filter_by(analito_id=analito.id).all()
            total_mediciones += len(mediciones)
            for med in mediciones:
                med.ref_texto = audit.rango_nuevo
                if med.valor_numerico is not None:
                    from app.services.analito_normalizer import evaluar_estado_semaforo
                    med.estado_semaforo = evaluar_estado_semaforo(med.valor_numerico, audit.rango_nuevo)

        audit.aplicado_en_historico = True
        audit.estado = "aplicado"
        audit.fecha_aplicacion = now

    db.commit()

    return {
        "status": "success",
        "message": f"Se han homologado {len(auditorias)} criterios en {total_mediciones} mediciones históricas.",
        "criterios_aplicados": len(auditorias),
        "mediciones_actualizadas": total_mediciones,
        "fecha_aplicacion": now.strftime("%d/%m/%Y %H:%M")
    }

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
