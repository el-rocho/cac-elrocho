"""
Datos demostrativos sintéticos para la inicialización en 'Modo Demo' de cac-elrocho.
No contiene ningún dato personal ni clínico real.
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Paciente, Informe, Analito, Medicion, AuditoriaRango

def run_seed(db: Session = None):
    close_db = False
    if db is None:
        init_db()
        db = SessionLocal()
        close_db = True

    try:
        # Comprobar si ya existen datos
        if db.query(Informe).count() > 0:
            return

        # 1. Paciente Demostrativo
        paciente = Paciente(
            nombre_completo="Paciente Ejemplo (Modo Demo)",
            fecha_nacimiento="1975-05-15",
            dni="00000000T",
            centro_referencia="Hospital Universitario Central (Demo)"
        )
        db.add(paciente)
        db.flush()

        # 2. Controles Demostrativos (5 controles cronológicos sintéticos)
        controles_meta = [
            ("2023-01-15", "15/01/23", "Laboratorio Central Demo", "Chequeo inicial"),
            ("2023-09-20", "20/09/23", "Laboratorio Central Demo", "Seguimiento semestral"),
            ("2024-06-10", "10/06/24", "Laboratorio Central Demo", "Control anual"),
            ("2025-03-05", "05/03/25", "Laboratorio Central Demo", "Revisión preventiva"),
            ("2026-06-15", "15/06/26", "Laboratorio Central Demo", "Control más reciente")
        ]

        informes_map = {}
        for idx, (fecha_iso, etiq, lab, fac) in enumerate(controles_meta):
            dictamen = "Favorable con Puntos de Atención (Demo)" if idx == len(controles_meta) - 1 else "Control favorable"
            inf = Informe(
                paciente_id=paciente.id,
                fecha=fecha_iso,
                etiqueta_corta=etiq,
                laboratorio=lab,
                facultativo=fac,
                dictamen_global=dictamen,
                observaciones_ia="Control de muestra generado para el modo demostración.",
                estado="confirmado"
            )
            db.add(inf)
            db.flush()
            informes_map[etiq] = inf

        # 3. Analitos y Valores Sintéticos Demostrativos
        demo_items = [
            ("GLUCOSE", "Glucosa Basal", "mg/dL", "60 - 100", [98.0, 95.0, 99.0, 102.0, 96.5]),
            ("HBA1C", "HbA1c", "%", "4.0 - 5.6", [5.1, 5.2, 5.3, 5.5, 5.7]),
            ("CREATININE", "Creatinina", "mg/dL", "0.70 - 1.20", [0.85, 0.90, 0.88, 0.92, 0.89]),
            ("UREA", "Urea", "mg/dL", "17 - 49.2", [38.0, 42.0, 39.5, 44.0, 41.0]),
            ("URIC_ACID", "Ácido Úrico", "mg/dL", "3.4 - 7.0", [5.8, 6.1, 5.9, 6.4, 6.2]),
            ("CHOLESTEROL_TOTAL", "Colesterol Total", "mg/dL", "100 - 200", [155.0, 160.0, 168.0, 172.0, 179.0]),
            ("TRIGLYCERIDES", "Triglicéridos", "mg/dL", "0 - 150", [75.0, 80.0, 68.0, 72.0, 66.0]),
            ("HDL", "HDL-Colesterol", "mg/dL", "40 - 100", [52.0, 50.0, 54.0, 51.0, 52.0]),
            ("LDL", "LDL-Colesterol", "mg/dL", "< 116 (Ref. 2023)", [88.0, 94.0, 100.0, 107.0, 118.0]),
            ("RATIO_COL_HDL", "Cociente Col/HDL", "ratio", "< 4.5 (Ópt. <3.5)", [2.98, 3.20, 3.11, 3.37, 3.44]),
            ("RATIO_LDL_HDL", "Cociente LDL/HDL", "ratio", "< 3.0 (Ópt. <2.0)", [1.69, 1.88, 1.85, 2.10, 2.27]),
            ("RATIO_LDL_COL", "Ratio LDL / Col. Total", "ratio", "< 0.65", [0.57, 0.59, 0.60, 0.62, 0.66]),
            ("RATIO_HDL_COL", "Ratio HDL / Col. Total", "ratio", "> 0.20", [0.34, 0.31, 0.32, 0.30, 0.29]),
            ("RATIO_TG_COL", "Ratio TG / Col. Total", "ratio", "< 0.50", [0.48, 0.50, 0.40, 0.42, 0.37]),
            ("PSA_TOTAL", "PSA Total", "ng/mL", "< 4.0", [0.55, 0.60, 0.62, 0.68, 0.71]),
            ("PSA_FREE", "PSA Libre", "ng/mL", "Orientativo", [0.28, 0.31, 0.33, 0.38, 0.42]),
            ("RATIO_PSA_L_T", "Ratio PSA L/T", "ratio", "> 0.20", [0.51, 0.52, 0.53, 0.56, 0.59]),
            ("TSH", "TSH", "µUI/mL", "0.27 - 4.29", [1.45, 1.80, 1.65, 2.10, 2.20]),
            ("VITAMIN_D", "Vitamina D (25-OH)", "ng/mL", "30 - 80", [21.0, 23.5, 26.0, 28.5, 32.5])
        ]

        orden = 1
        for cod, nom, uni, ref, vals in demo_items:
            analito = Analito(
                codigo=cod,
                nombre_visible=nom,
                categoria="bioquimica",
                unidad_estandar=uni,
                ref_texto_defecto=ref,
                orden=orden
            )
            db.add(analito)
            db.flush()
            orden += 1

            for col_idx, val in enumerate(vals):
                etiq = controles_meta[col_idx][1]
                inf = informes_map[etiq]
                med = Medicion(
                    informe_id=inf.id,
                    analito_id=analito.id,
                    valor_numerico=val,
                    unidad=uni,
                    ref_texto=ref
                )
                db.add(med)

        # 4. Auditoría Demo para ilustrar la funcionalidad de la IA
        ldl_analito = db.query(Analito).filter_by(codigo="LDL").first()
        ultimo_inf = informes_map["15/06/26"]
        audit = AuditoriaRango(
            analito_id=ldl_analito.id,
            informe_id=ultimo_inf.id,
            rango_anterior="< 130 mg/dL",
            rango_nuevo="< 116 mg/dL",
            explicacion_ia="El laboratorio aplicó criterios más estrictos de riesgo cardiovascular recomendados por guías clínicas."
        )
        db.add(audit)

        db.commit()

    except Exception as e:
        db.rollback()
        raise
    finally:
        if close_db:
            db.close()

if __name__ == "__main__":
    run_seed()
