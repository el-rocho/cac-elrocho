"""
Datos demostrativos sintéticos para la inicialización en 'Modo Demo' de cac-elrocho.
No contiene ningún dato personal ni clínico real.
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.models import Paciente, Informe, Analito, Medicion, AuditoriaRango

# Perfil sintético de tres controles recientes. Los identificadores, fechas y
# mediciones son ficticios y no proceden literalmente de una historia clínica.
RECENT_SYNTHETIC_PROFILE = {
    "patient": ("Paciente Sintético", "1978-04-12", "SYNTHETIC-0001", "No especificado"),
    "reports": [
        ("2025-05-14", "14/05/25", "SYN-2026-001"),
        ("2025-11-20", "20/11/25", "SYN-2026-002"),
        ("2026-05-28", "28/05/26", "SYN-2026-003"),
    ],
    "items": [
        ("GLUCOSE", "Glucosa Basal", "mg/dL", "82 - 115", [84.83, 82.19, 84.83]),
        ("HBA1C", "HbA1c", "%", "< 5.7", [5.02, 4.84, 4.42]),
        ("CREATININE", "Creatinina", "mg/dL", "0.70 - 1.20", [1.10, 1.06, 1.22]),
        ("EGFR_CKD_EPI", "eGFR (CKD-EPI)", "mL/min/1.73m²", "> 60", [101.2, 103.5, 88.55]),
        ("CHOLESTEROL_TOTAL", "Colesterol Total", "mg/dL", "< 200", [158.9, 168.5, 143.8]),
        ("HDL", "HDL-Colesterol", "mg/dL", "> 40", [57.73, 51.71, 48.96]),
        ("LDL", "LDL-Colesterol", "mg/dL", "< 116", [87.0, 102.7, 83.52]),
        ("TRIGLYCERIDES", "Triglicéridos", "mg/dL", "< 150", [68.31, 64.35, 52.47]),
        ("TSH", "TSH", "µUI/mL", "0.270 - 4.29", [2.12, 2.48, 2.25]),
        ("VITAMIN_D", "25-OH Vitamina D", "ng/mL", "30 - 80", [34.1, 36.56, 35.92]),
    ],
}


def run_recent_synthetic_seed(db: Session = None):
    """Carga tres analíticas demostrativas anonimizadas para desarrollo."""
    close_db = db is None
    if close_db:
        init_db()
        db = SessionLocal()
    try:
        if db.query(Informe).count() > 0:
            return
        name, birth, dni, sex = RECENT_SYNTHETIC_PROFILE["patient"]
        patient = Paciente(nombre_completo=name, fecha_nacimiento=birth, dni=dni, sexo=sex,
                           centro_referencia="Centro de Demostración")
        db.add(patient); db.flush()
        reports = []
        for date, label, reference in RECENT_SYNTHETIC_PROFILE["reports"]:
            report = Informe(paciente_id=patient.id, fecha=date, etiqueta_corta=label,
                             referencia=reference, laboratorio="Laboratorio de Pruebas Sintéticas",
                             facultativo="Equipo Clínico de Demostración", estado="confirmado")
            db.add(report); db.flush(); reports.append(report)
        for order, (code, label, unit, reference, values) in enumerate(RECENT_SYNTHETIC_PROFILE["items"], 1):
            analyte = Analito(codigo=code, nombre_visible=label, categoria="bioquimica",
                              unidad_estandar=unit, ref_texto_defecto=reference, orden=order)
            db.add(analyte); db.flush()
            for report, value in zip(reports, values):
                db.add(Medicion(informe_id=report.id, analito_id=analyte.id,
                                valor_numerico=value, unidad=unit, ref_texto=reference))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        if close_db:
            db.close()

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
            sexo="Masculino",
            centro_referencia="Hospital Universitario Central (Demo)"
        )
        db.add(paciente)
        db.flush()

        # 2. Controles Demostrativos (5 controles cronológicos sintéticos)
        controles_meta = [
            ("2023-01-15", "15/01/23", "Laboratorio Central Demo", "Dra. Elena Ramos"),
            ("2023-09-20", "20/09/23", "Laboratorio Central Demo", "Dr. Carlos Mendoza"),
            ("2024-06-10", "10/06/24", "Laboratorio Central Demo", "Dra. Elena Ramos"),
            ("2025-03-05", "05/03/25", "Laboratorio Central Demo", "Dr. Antonio Álvarez"),
            ("2026-06-15", "15/06/26", "Laboratorio Central Demo", "Dr. Miguel Quiñones")
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
