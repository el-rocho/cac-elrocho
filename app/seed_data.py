"""
Datos demostrativos sintéticos para la inicialización en 'Modo Demo' de cac-elrocho.
No contiene ningún dato personal ni clínico real.
"""
import math

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

DEMO_FACULTATIVO = "Dr. Demo"
DEMO_LABORATORIO = "Laboratorio Central Demo"

# 15 controles trimestrales anteriores a la serie reciente. Con 20 informes en
# total, el registro de la pestaña «Gestión» muestra el paginador en marcha.
DEMO_FECHAS_ANTERIORES = [
    "2019-04-15", "2019-07-15", "2019-10-15",
    "2020-01-15", "2020-04-15", "2020-07-15", "2020-10-15",
    "2021-01-15", "2021-04-15", "2021-07-15", "2021-10-15",
    "2022-01-15", "2022-04-15", "2022-07-15", "2022-10-15",
]
DEMO_FECHAS_RECIENTES = [
    "2023-01-15", "2023-09-20", "2024-06-10", "2025-03-05", "2026-06-15",
]


def _controles_demo() -> list:
    """20 controles sintéticos, todos con el mismo facultativo ficticio."""
    controles = []
    por_anio = {}
    for fecha_iso in DEMO_FECHAS_ANTERIORES + DEMO_FECHAS_RECIENTES:
        anio = fecha_iso[:4]
        por_anio[anio] = por_anio.get(anio, 0) + 1
        etiqueta = f"{fecha_iso[8:10]}/{fecha_iso[5:7]}/{fecha_iso[2:4]}"
        controles.append((
            fecha_iso,
            etiqueta,
            DEMO_LABORATORIO,
            DEMO_FACULTATIVO,
            f"DEMO-{anio}-{por_anio[anio]:03d}",
        ))
    return controles


def _completar_valores_demo(valores_recientes: list, total_controles: int) -> list:
    """Extiende una serie analítica hacia atrás hasta ``total_controles``.

    Los valores declarados (los más recientes) se conservan literalmente; los
    anteriores oscilan de forma determinista alrededor de la media de la serie y
    se mantienen dentro de su banda observada, de modo que los gráficos de la
    demo muestren una evolución creíble y sin valores atípicos inventados.
    """
    faltantes = total_controles - len(valores_recientes)
    if faltantes <= 0:
        return list(valores_recientes)

    media = sum(valores_recientes) / len(valores_recientes)
    minimo, maximo = min(valores_recientes), max(valores_recientes)
    amplitud = max((maximo - minimo) * 0.35, abs(media) * 0.02)
    desviacion_inicial = valores_recientes[0] - media
    decimales = max(
        len(str(valor).split(".")[1]) if "." in str(valor) else 0
        for valor in valores_recientes
    )

    anteriores = []
    for k in range(faltantes, 0, -1):
        # El pasado se acerca progresivamente a la media de los controles
        # declarados y añade una oscilación suave y reproducible.
        deriva = desviacion_inicial * (0.35 + 0.6 * k / faltantes)
        oscilacion = amplitud * math.sin(k * 1.1)
        valor = media + deriva + oscilacion
        valor = min(max(valor, minimo - amplitud), maximo + amplitud)
        anteriores.append(round(valor, decimales))
    return anteriores + list(valores_recientes)


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
            fecha_nacimiento="1989-07-02",
            dni="00000000T",
            sexo="No especificado",
            centro_referencia="Hospital Universitario Central (Demo)"
        )
        db.add(paciente)
        db.flush()

        # 2. Controles Demostrativos (20 controles cronológicos sintéticos)
        controles_meta = _controles_demo()
        if len({c[1] for c in controles_meta}) != len(controles_meta):
            raise ValueError("Etiquetas de control duplicadas en la demo")

        informes_map = {}
        for idx, (fecha_iso, etiq, lab, fac, ref) in enumerate(controles_meta):
            dictamen = "Favorable con Puntos de Atención (Demo)" if idx == len(controles_meta) - 1 else "Control favorable"
            inf = Informe(
                paciente_id=paciente.id,
                fecha=fecha_iso,
                etiqueta_corta=etiq,
                laboratorio=lab,
                facultativo=fac,
                referencia=ref,
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

            valores_demo = _completar_valores_demo(vals, len(controles_meta))
            for col_idx, val in enumerate(valores_demo):
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
