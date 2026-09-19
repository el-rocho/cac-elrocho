import logging
from typing import Tuple
from sqlalchemy.orm import Session
from app.models import Medicion, Analito, Informe
from app.services.analito_normalizer import standardize_medicion, CANONICAL_CATALOG

logger = logging.getLogger("cac-elrocho.harmonizer")

def harmonize_database_records(db: Session) -> int:
    """
    Recorre todas las determinaciones analíticas existentes en la base de datos
    y armoniza aquellas que presenten discrepancias de unidad o escala numérica:
    - Fórmula leucocitaria absoluta (Linfocitos, Neutrófilos, Monocitos, Eosinófilos, Basófilos) en /µL.
    - Leucocitos y Plaquetas en x10^3/µL.
    - Hematíes en x10^6/µL (convirtiendo notaciones de millares a formato decimal estándar).
    - Rangos de referencia proporcionales a la unidad canónica.
    - Unidades canónicas estandarizadas (ej: /µL, x10^3/µL, U/L, ng/mL).
    
    Es idempotente: si los registros ya se encuentran estandarizados, no realiza cambios.
    
    Retorna el número de mediciones actualizadas.
    """
    try:
        meds = db.query(Medicion, Analito).join(Analito).all()
        if not meds:
            return 0

        updated_count = 0
        analitos_updated = set()

        for m, a in meds:
            val_to_check = m.valor_numerico if m.valor_numerico is not None else m.valor_texto
            if val_to_check is None and not m.valor_texto:
                continue

            num_val, clean_text, std_unit, std_ref = standardize_medicion(
                a.codigo,
                val_to_check,
                m.unidad,
                m.ref_texto
            )

            modified = False

            # 1. Comprobar valor numérico
            if num_val is not None:
                if m.valor_numerico is None or abs(m.valor_numerico - num_val) > 0.0001:
                    m.valor_numerico = num_val
                    m.valor_texto = None
                    modified = True
            elif clean_text and m.valor_texto != clean_text:
                m.valor_texto = clean_text
                modified = True

            # 2. Comprobar unidad estandarizada
            if std_unit and m.unidad != std_unit:
                m.unidad = std_unit
                modified = True

            # 3. Comprobar rango de referencia estandarizado
            if std_ref and m.ref_texto != std_ref:
                m.ref_texto = std_ref
                modified = True

            # 4. Asegurar que el estado semafórico refleje la normalidad del rango del informe
            if m.valor_numerico is not None and m.ref_texto:
                from app.services.analito_normalizer import evaluar_estado_semaforo
                calc_status = evaluar_estado_semaforo(m.valor_numerico, m.ref_texto)
                if calc_status != "Normal" and m.estado_semaforo in [None, "Normal"]:
                    m.estado_semaforo = calc_status
                    modified = True

            if modified:
                updated_count += 1

            # 5. Asegurar que el catálogo de Analito en BD use la unidad canónica
            if std_unit and a.unidad_estandar != std_unit and a.id not in analitos_updated:
                a.unidad_estandar = std_unit
                analitos_updated.add(a.id)

        # 6. Sincronizar ref_texto_defecto del Analito con el informe más reciente
        analitos_all = db.query(Analito).all()
        for a in analitos_all:
            latest_med = (
                db.query(Medicion)
                .join(Informe, Medicion.informe_id == Informe.id)
                .filter(Medicion.analito_id == a.id)
                .order_by(Informe.fecha.desc())
                .first()
            )
            if latest_med and latest_med.ref_texto:
                ref_clean = latest_med.ref_texto.strip()
                if ref_clean and ref_clean not in ["-", "Sin referencia", "No especificado"]:
                    if a.ref_texto_defecto != ref_clean:
                        a.ref_texto_defecto = ref_clean
                        analitos_updated.add(a.id)

        if updated_count > 0 or analitos_updated:
            db.commit()
            logger.info(
                f"Armonización completada: {updated_count} mediciones y "
                f"{len(analitos_updated)} analitos actualizados con rangos y unidades vigentes."
            )
        else:
            logger.info("Verificación de base de datos: Todas las analíticas históricas están en unidades estándar.")

        return updated_count
    except Exception as e:
        db.rollback()
        logger.error(f"Error durante la armonización de la base de datos: {e}", exc_info=True)
        return 0
