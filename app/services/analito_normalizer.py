import re
from datetime import date
from typing import Tuple, Optional, Any, Dict

def calcular_edad_en_fecha(fecha_nacimiento: Optional[str], fecha_referencia: Optional[str]) -> Optional[int]:
    """
    Calcula los años cumplidos en una fecha de referencia específica
    (por ejemplo, la fecha exacta de una analítica).
    """
    if not fecha_nacimiento or not fecha_referencia:
        return None
    try:
        def _parse(f_str: str) -> Optional[date]:
            s = str(f_str).strip()
            if "-" in s:
                p = s.split("-")
                if len(p) == 3:
                    return date(int(p[0]), int(p[1]), int(p[2]))
            elif "/" in s:
                p = s.split("/")
                if len(p) == 3:
                    return date(int(p[2]), int(p[1]), int(p[0]))
            return None

        d_nac = _parse(fecha_nacimiento)
        d_ref = _parse(fecha_referencia)
        if not d_nac or not d_ref:
            return None

        edad = d_ref.year - d_nac.year - ((d_ref.month, d_ref.day) < (d_nac.month, d_nac.day))
        if 0 <= edad <= 125:
            return edad
    except Exception:
        pass
    return None

# Catálogo canónico estricto de analitos agrupados por especialidad clínica
CANONICAL_CATALOG = {
    # 1. Metabolismo Lipídico y Riesgo Cardiovascular
    "CHOLESTEROL_TOTAL": {
        "nombre": "Colesterol Total",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "mg/dL",
        "ref": "< 200 mg/dL",
        "orden": 10
    },
    "HDL": {
        "nombre": "HDL-Colesterol",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "mg/dL",
        "ref": "> 40 mg/dL",
        "orden": 20
    },
    "LDL": {
        "nombre": "LDL-Colesterol",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "mg/dL",
        "ref": "< 116 mg/dL (SEA 2023)",
        "orden": 30
    },
    "TRIGLYCERIDES": {
        "nombre": "Triglicéridos",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "mg/dL",
        "ref": "< 150 mg/dL",
        "orden": 40
    },
    "RATIO_COL_HDL": {
        "nombre": "Colesterol Total / HDL (Castelli I)",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "ratio",
        "ref": "< 5.0",
        "orden": 50
    },
    "RATIO_LDL_HDL": {
        "nombre": "LDL / HDL (Castelli II)",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "ratio",
        "ref": "< 4.3",
        "orden": 60
    },
    "RATIO_TG_HDL": {
        "nombre": "Triglicéridos / HDL",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "ratio",
        "ref": "< 2.0",
        "orden": 70
    },
    "RATIO_LDL_COL": {
        "nombre": "Ratio LDL / Col. Total",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "ratio",
        "ref": "< 0.65",
        "orden": 80
    },
    "RATIO_HDL_COL": {
        "nombre": "Ratio HDL / Col. Total",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "ratio",
        "ref": "> 0.20",
        "orden": 81
    },
    "RATIO_TG_COL": {
        "nombre": "Ratio TG / Col. Total",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "ratio",
        "ref": "< 0.50",
        "orden": 82
    },
    "APOB": {
        "nombre": "Apolipoproteína B (ApoB)",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "mg/dL",
        "ref": "< 100 mg/dL",
        "orden": 85
    },
    "LPA": {
        "nombre": "Lipoproteína (a) [Lp(a)]",
        "categoria": "bioquimica",
        "grupo": "🧬 Metabolismo Lipídico y Riesgo Cardiovascular",
        "unidad": "mg/dL",
        "ref": "< 50 mg/dL",
        "orden": 86
    },

    # 2. Metabolismo Hidrocarbonado y Glucídico
    "GLUCOSE": {
        "nombre": "Glucosa Basal",
        "categoria": "bioquimica",
        "grupo": "🩸 Metabolismo Hidrocarbonado (Glucemia)",
        "unidad": "mg/dL",
        "ref": "60 - 100 mg/dL",
        "orden": 100
    },
    "HBA1C": {
        "nombre": "HbA1c",
        "categoria": "bioquimica",
        "grupo": "🩸 Metabolismo Hidrocarbonado (Glucemia)",
        "unidad": "%",
        "ref": "< 5.7 %",
        "orden": 110
    },
    "HBA1C_IFCC": {
        "nombre": "HbA1c (IFCC)",
        "categoria": "bioquimica",
        "grupo": "🩸 Metabolismo Hidrocarbonado (Glucemia)",
        "unidad": "mmol/mol",
        "ref": "< 38.8 mmol/mol",
        "orden": 120
    },
    "INSULINA": {
        "nombre": "Insulina Basal",
        "categoria": "bioquimica",
        "grupo": "🩸 Metabolismo Hidrocarbonado (Glucemia)",
        "unidad": "µUI/mL",
        "ref": "2.6 - 24.9 µUI/mL",
        "orden": 125
    },
    "HOMA_IR": {
        "nombre": "Índice HOMA-IR",
        "categoria": "bioquimica",
        "grupo": "🩸 Metabolismo Hidrocarbonado (Glucemia)",
        "unidad": "ratio",
        "ref": "< 2.5",
        "orden": 126
    },

    # 3. Función Renal y Depuración
    "CREATININE": {
        "nombre": "Creatinina",
        "categoria": "bioquimica",
        "grupo": "🧪 Función Renal y Depuración",
        "unidad": "mg/dL",
        "ref": "0.70 - 1.20 mg/dL",
        "orden": 200
    },
    "EGFR": {
        "nombre": "Filtrado Glomerular (eGFR)",
        "categoria": "bioquimica",
        "grupo": "🧪 Función Renal y Depuración",
        "unidad": "mL/min/1.73m²",
        "ref": "> 60 mL/min/1.73m²",
        "orden": 205
    },
    "EGFR_CKD_EPI": {
        "nombre": "eGFR (CKD-EPI)",
        "categoria": "bioquimica",
        "grupo": "🧪 Función Renal y Depuración",
        "unidad": "mL/min/1.73m²",
        "ref": "> 90 mL/min/1.73m²",
        "orden": 206
    },
    "UREA": {
        "nombre": "Urea",
        "categoria": "bioquimica",
        "grupo": "🧪 Función Renal y Depuración",
        "unidad": "mg/dL",
        "ref": "17.0 - 49.2 mg/dL",
        "orden": 210
    },
    "BUN": {
        "nombre": "BUN (Nitrógeno Ureico)",
        "categoria": "bioquimica",
        "grupo": "🧪 Función Renal y Depuración",
        "unidad": "mg/dL",
        "ref": "7.0 - 21.0 mg/dL",
        "orden": 220
    },
    "URIC_ACID": {
        "nombre": "Ácido Úrico",
        "categoria": "bioquimica",
        "grupo": "🧪 Función Renal y Depuración",
        "unidad": "mg/dL",
        "ref": "3.5 - 7.2 mg/dL",
        "orden": 230
    },

    # 4. Eje Tiroideo y Metabolismo Óseo
    "TSH": {
        "nombre": "TSH",
        "categoria": "bioquimica",
        "grupo": "🦋 Eje Tiroideo y Metabolismo Óseo",
        "unidad": "µUI/mL",
        "ref": "0.27 - 4.29 µUI/mL",
        "orden": 300
    },
    "T4_LIBRE": {
        "nombre": "T4 Libre",
        "categoria": "bioquimica",
        "grupo": "🦋 Eje Tiroideo y Metabolismo Óseo",
        "unidad": "ng/dL",
        "ref": "0.71 - 1.85 ng/dL",
        "orden": 310
    },
    "T3_LIBRE": {
        "nombre": "T3 Libre",
        "categoria": "bioquimica",
        "grupo": "🦋 Eje Tiroideo y Metabolismo Óseo",
        "unidad": "pg/mL",
        "ref": "2.0 - 4.4 pg/mL",
        "orden": 315
    },
    "ANTI_TPO": {
        "nombre": "Anticuerpos Anti-TPO",
        "categoria": "inmunologia",
        "grupo": "🦋 Eje Tiroideo y Metabolismo Óseo",
        "unidad": "UI/mL",
        "ref": "< 34.0 UI/mL",
        "orden": 316
    },
    "ANTI_TG": {
        "nombre": "Anticuerpos Anti-Tiroglobulina",
        "categoria": "inmunologia",
        "grupo": "🦋 Eje Tiroideo y Metabolismo Óseo",
        "unidad": "UI/mL",
        "ref": "< 115.0 UI/mL",
        "orden": 317
    },
    "TRAB": {
        "nombre": "Anticuerpos Anti-Receptor TSH (TRAb)",
        "categoria": "inmunologia",
        "grupo": "🦋 Eje Tiroideo y Metabolismo Óseo",
        "unidad": "UI/L",
        "ref": "< 1.75 UI/L",
        "orden": 318
    },
    "VITAMIN_D": {
        "nombre": "25-OH Vitamina D",
        "categoria": "bioquimica",
        "grupo": "🦋 Eje Tiroideo y Metabolismo Óseo",
        "unidad": "ng/mL",
        "ref": "30 - 96 ng/mL",
        "orden": 320
    },
    "PTH_INTACTA": {
        "nombre": "PTH Intacta",
        "categoria": "bioquimica",
        "grupo": "🦋 Eje Tiroideo y Metabolismo Óseo",
        "unidad": "pg/mL",
        "ref": "14.5 - 87.1 pg/mL",
        "orden": 330
    },

    # 5. Marcadores Tumorales
    "PSA_TOTAL": {
        "nombre": "PSA Total",
        "categoria": "bioquimica",
        "grupo": "🔬 Marcadores Tumorales",
        "unidad": "ng/mL",
        "ref": "< 4.0 ng/mL",
        "orden": 400
    },
    "PSA_FREE": {
        "nombre": "PSA Libre",
        "categoria": "bioquimica",
        "grupo": "🔬 Marcadores Tumorales",
        "unidad": "ng/mL",
        "ref": "-",
        "orden": 410
    },
    "RATIO_PSA_L_T": {
        "nombre": "Ratio PSA Libre / Total",
        "categoria": "bioquimica",
        "grupo": "🔬 Marcadores Tumorales",
        "unidad": "%",
        "ref": "> 20 %",
        "orden": 420
    },
    "CEA": {
        "nombre": "CEA",
        "categoria": "bioquimica",
        "grupo": "🔬 Marcadores Tumorales",
        "unidad": "ng/mL",
        "ref": "< 5.0 ng/mL",
        "orden": 430
    },
    "CA_125_II": {
        "nombre": "CA 125 II",
        "categoria": "bioquimica",
        "grupo": "🔬 Marcadores Tumorales",
        "unidad": "UI/mL",
        "ref": "< 35 UI/mL",
        "orden": 440
    },
    "CA_19_9": {
        "nombre": "CA 19-9",
        "categoria": "bioquimica",
        "grupo": "🔬 Marcadores Tumorales",
        "unidad": "UI/mL",
        "ref": "< 34 UI/mL",
        "orden": 450
    },

    # 6. Metabolismo Férrico e Inflamatorio
    "HIERRO": {
        "nombre": "Hierro",
        "categoria": "bioquimica",
        "grupo": "🛡️ Metabolismo Férrico e Inflamatorio",
        "unidad": "µg/dL",
        "ref": "59 - 160 µg/dL",
        "orden": 500
    },
    "FERRITINA": {
        "nombre": "Ferritina",
        "categoria": "bioquimica",
        "grupo": "🛡️ Metabolismo Férrico e Inflamatorio",
        "unidad": "ng/mL",
        "ref": "27 - 300 ng/mL",
        "orden": 510
    },
    "PROTEINA_C_REACTIVA": {
        "nombre": "Proteína C Reactiva (PCR)",
        "categoria": "bioquimica",
        "grupo": "🛡️ Metabolismo Férrico e Inflamatorio",
        "unidad": "mg/dL",
        "ref": "< 0.5 mg/dL",
        "orden": 520
    },
    "FACTOR_REUMATOIDE": {
        "nombre": "Factor Reumatoide",
        "categoria": "bioquimica",
        "grupo": "🛡️ Metabolismo Férrico e Inflamatorio",
        "unidad": "UI/mL",
        "ref": "< 30 UI/mL",
        "orden": 530
    },
    "VITAMINA_B12": {
        "nombre": "Vitamina B12",
        "categoria": "bioquimica",
        "grupo": "🛡️ Metabolismo Férrico e Inflamatorio",
        "unidad": "pg/mL",
        "ref": "200 - 900 pg/mL",
        "orden": 540
    },
    "ACIDO_FOLICO": {
        "nombre": "Ácido Fólico (Folato)",
        "categoria": "bioquimica",
        "grupo": "🛡️ Metabolismo Férrico e Inflamatorio",
        "unidad": "ng/mL",
        "ref": "> 4.0 ng/mL",
        "orden": 545
    },

    # 7. Enzimas Hepáticas e Iones Séricos
    "GOT_AST": {
        "nombre": "GOT / AST",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "U/L",
        "ref": "< 45 U/L",
        "orden": 600
    },
    "GPT_ALT": {
        "nombre": "GPT / ALT",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "U/L",
        "ref": "7 - 55 U/L",
        "orden": 610
    },
    "GGT": {
        "nombre": "GGT",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "U/L",
        "ref": "8 - 78 U/L",
        "orden": 620
    },
    "FOSFATASA_ALCALINA": {
        "nombre": "Fosfatasa Alcalina",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "U/L",
        "ref": "38 - 126 U/L",
        "orden": 630
    },
    "AMILASA": {
        "nombre": "Amilasa",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "U/L",
        "ref": "30 - 110 U/L",
        "orden": 640
    },
    "SODIO": {
        "nombre": "Sodio",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "mmol/L",
        "ref": "135 - 147 mmol/L",
        "orden": 650
    },
    "POTASIO": {
        "nombre": "Potasio",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "mmol/L",
        "ref": "3.5 - 5.1 mmol/L",
        "orden": 660
    },
    "CALCIO_TOTAL": {
        "nombre": "Calcio Total",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "mg/dL",
        "ref": "8.2 - 10.6 mg/dL",
        "orden": 670
    },
    "CALCIO_CORREGIDO": {
        "nombre": "Calcio Corregido (con Albúmina)",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "mg/dL",
        "ref": "8.8 - 10.2 mg/dL",
        "orden": 672
    },
    "FOSFORO": {
        "nombre": "Fósforo",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "mg/dL",
        "ref": "2.5 - 5.0 mg/dL",
        "orden": 680
    },
    "MAGNESIO": {
        "nombre": "Magnesio",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "mmol/L",
        "ref": "0.65 - 1.10 mmol/L",
        "orden": 690
    },
    "BILIRRUBINA_TOTAL": {
        "nombre": "Bilirrubina Total",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "mg/dL",
        "ref": "< 1.2 mg/dL",
        "orden": 700
    },
    "ALBUMINA": {
        "nombre": "Albúmina",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "g/dL",
        "ref": "3.5 - 5.0 g/dL",
        "orden": 705
    },

    # 8. Hemograma Completo
    "HEMATIES": {
        "nombre": "Hematíes",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "x10^6/µL",
        "ref": "4.60 - 6.20 x10^6/µL",
        "orden": 800
    },
    "HEMOGLOBINA": {
        "nombre": "Hemoglobina",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "g/dL",
        "ref": "13.5 - 18.0 g/dL",
        "orden": 810
    },
    "HEMATOCRITO": {
        "nombre": "Hematocrito",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "%",
        "ref": "42.0 - 52.0 %",
        "orden": 820
    },
    "VCM": {
        "nombre": "VCM",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "fL",
        "ref": "80 - 100 fL",
        "orden": 830
    },
    "HCM": {
        "nombre": "HCM",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "pg",
        "ref": "27 - 33 pg",
        "orden": 840
    },
    "CHCM": {
        "nombre": "CHCM",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "%",
        "ref": "33 - 37 %",
        "orden": 850
    },
    "RDW": {
        "nombre": "RDW",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "%",
        "ref": "11 - 18 %",
        "orden": 860
    },
    "PLAQUETAS": {
        "nombre": "Plaquetas",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "x10^3/µL",
        "ref": "130 - 450 x10^3/µL",
        "orden": 870
    },
    "VPM": {
        "nombre": "VPM",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "fL",
        "ref": "7 - 13 fL",
        "orden": 880
    },
    "LEUCOCITOS": {
        "nombre": "Leucocitos",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "x10^3/µL",
        "ref": "4.00 - 11.00 x10^3/µL",
        "orden": 890
    },
    "NEUTROFILOS_ABS": {
        "nombre": "Neutrófilos Absolutos",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "/µL",
        "ref": "1800 - 7500 /µL",
        "orden": 900
    },
    "LINFOCITOS_ABS": {
        "nombre": "Linfocitos Absolutos",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "/µL",
        "ref": "1000 - 4500 /µL",
        "orden": 910
    },
    "MONOCITOS_ABS": {
        "nombre": "Monocitos Absolutos",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "/µL",
        "ref": "200 - 1000 /µL",
        "orden": 920
    },
    "EOSINOFILOS_ABS": {
        "nombre": "Eosinófilos Absolutos",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "/µL",
        "ref": "< 800 /µL",
        "orden": 930
    },
    "BASOFILOS_ABS": {
        "nombre": "Basófilos Absolutos",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "/µL",
        "ref": "< 200 /µL",
        "orden": 940
    },
    "VSG_1H": {
        "nombre": "VSG 1ª Hora",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "mm",
        "ref": "< 10 mm",
        "orden": 950
    },
    "VSG_2H": {
        "nombre": "VSG 2ª Hora",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "mm",
        "ref": "< 30 mm",
        "orden": 960
    },
    "KATZ_INDEX": {
        "nombre": "Índice de Katz",
        "categoria": "hemograma",
        "grupo": "🩸 Hemograma y Serie Hematológica",
        "unidad": "mm",
        "ref": "< 15 mm",
        "orden": 970
    },

    # 9. Sistemático y Sedimento de Orina
    "GLUCOSE_URINE": {
        "nombre": "Glucosa (Orina)",
        "categoria": "orina",
        "grupo": "📋 Sistemático y Sedimento de Orina",
        "unidad": "Cualitativo",
        "ref": "Negativo",
        "orden": 1000
    },
    "PROTEIN_URINE": {
        "nombre": "Proteínas / Albúmina (Orina)",
        "categoria": "orina",
        "grupo": "📋 Sistemático y Sedimento de Orina",
        "unidad": "Cualitativo",
        "ref": "Negativo",
        "orden": 1010
    },
    "UACR": {
        "nombre": "Cociente Albúmina/Creatinina (uACR)",
        "categoria": "orina",
        "grupo": "📋 Sistemático y Sedimento de Orina",
        "unidad": "mg/g",
        "ref": "< 30 mg/g",
        "orden": 1015
    },
    "DENSIDAD_URINE": {
        "nombre": "Densidad (Orina)",
        "categoria": "orina",
        "grupo": "📋 Sistemático y Sedimento de Orina",
        "unidad": "g/mL",
        "ref": "1.000 - 1.040",
        "orden": 1020
    },
    "PH_URINE": {
        "nombre": "pH (Orina)",
        "categoria": "orina",
        "grupo": "📋 Sistemático y Sedimento de Orina",
        "unidad": "pH",
        "ref": "4.5 - 7.5",
        "orden": 1030
    },
    "SEDIMENTO_URINARIO": {
        "nombre": "Sedimento Urinario",
        "categoria": "orina",
        "grupo": "📋 Sistemático y Sedimento de Orina",
        "unidad": "Texto",
        "ref": "Sin interés clínico",
        "orden": 1040
    },
    "CREATIN_KINASA": {
        "nombre": "Creatin Kinasa (CK)",
        "categoria": "bioquimica",
        "grupo": "⚡ Enzimas Hepáticas e Iones Séricos",
        "unidad": "U/L",
        "ref": "38 - 174 U/L",
        "orden": 675
    },

    # 10. Inmunología y Alergología (Anticuerpos IgE)
    "IGE_TOTAL": {
        "nombre": "Inmunoglobulina E Total (IgE)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "UI/mL",
        "ref": "< 100 UI/mL",
        "orden": 1100
    },
    "IGE_CYNODON_DACTYLON": {
        "nombre": "IgE Cynodon dactylon (Grama mayor)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1110
    },
    "IGE_LOLIUM_PERENNE": {
        "nombre": "IgE Lolium perenne (Ballico / Ray-grass)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1120
    },
    "IGE_CUPRESSUS_ARIZONICA": {
        "nombre": "IgE Cupressus arizonica (Arizónica)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1130
    },
    "IGE_OLEA_EUROPAEA": {
        "nombre": "IgE Olea europaea (Olivo)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1140
    },
    "IGE_PLANTAGO_LANCEOLATA": {
        "nombre": "IgE Plantago lanceolata (Llantén)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1150
    },
    "IGE_PARIETARIA_JUDAICA": {
        "nombre": "IgE Parietaria judaica",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1160
    },
    "IGE_SALSOLA_KALI": {
        "nombre": "IgE Salsola kali (Barrilla)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1170
    },
    "IGE_ARTEMISIA_VULGARIS": {
        "nombre": "IgE Artemisia vulgaris (Ajenjo)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1180
    },
    "IGE_DERMATOPHAGOIDES_PTERONYSSINUS": {
        "nombre": "IgE D. pteronyssinus (Ácaro)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1190
    },
    "IGE_DERMATOPHAGOIDES_FARINAE": {
        "nombre": "IgE D. farinae (Ácaro)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1200
    },
    "IGE_EPITELIO_GATO": {
        "nombre": "IgE Epitelio de Gato",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1210
    },
    "IGE_EPITELIO_PERRO": {
        "nombre": "IgE Epitelio de Perro",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1220
    },
    "IGE_ALTERNARIA_ALTERNATA": {
        "nombre": "IgE Alternaria alternata (Hongo)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "kU/L",
        "ref": "< 0.35 kU/L",
        "orden": 1230
    },

    # Inmunoglobulinas Séricas y Proteínas Séricas
    "IGG": {
        "nombre": "Inmunoglobulina IgG",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "mg/dL",
        "ref": "540 - 1822 mg/dL",
        "orden": 1240
    },
    "IGA": {
        "nombre": "Inmunoglobulina IgA",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "mg/dL",
        "ref": "70 - 400 mg/dL",
        "orden": 1242
    },
    "IGM": {
        "nombre": "Inmunoglobulina IgM",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "mg/dL",
        "ref": "40 - 230 mg/dL",
        "orden": 1244
    },
    "PROTEINAS_TOTALES": {
        "nombre": "Proteínas Totales",
        "categoria": "bioquimica",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "g/dL",
        "ref": "6.0 - 8.3 g/dL",
        "orden": 1246
    },
    "ALBUMINA_SERICA": {
        "nombre": "Albúmina Sérica",
        "categoria": "bioquimica",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "g/dL",
        "ref": "3.5 - 5.2 g/dL",
        "orden": 1248
    },
    "BETA_2_MICROGLOBULINA": {
        "nombre": "Beta-2 Microglobulina",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "mcg/mL",
        "ref": "< 3.0 mcg/mL",
        "orden": 1255
    },
    "ANTI_CCP": {
        "nombre": "Anticuerpos Anti-CCP",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "UI/mL",
        "ref": "< 7.0 UI/mL",
        "orden": 1260
    },
    "ANA": {
        "nombre": "Anticuerpos Anti-Nucleares (ANA)",
        "categoria": "inmunologia",
        "grupo": "🌸 Alergología e Inmunología",
        "unidad": "",
        "ref": "< 1:80",
        "orden": 1265
    },

    # 11. Coagulación y Hemostasia
    "TIEMPO_PROTROMBINA": {
        "nombre": "Tiempo de Protrombina (TP)",
        "categoria": "coagulacion",
        "grupo": "⏱️ Coagulación y Hemostasia",
        "unidad": "segundos",
        "ref": "10.0 - 14.5 s",
        "orden": 1300
    },
    "INDICE_QUICK": {
        "nombre": "Índice de Quick",
        "categoria": "coagulacion",
        "grupo": "⏱️ Coagulación y Hemostasia",
        "unidad": "%",
        "ref": "70 - 120 %",
        "orden": 1310
    },
    "RATIO_TP": {
        "nombre": "Ratio de Protrombina",
        "categoria": "coagulacion",
        "grupo": "⏱️ Coagulación y Hemostasia",
        "unidad": "ratio",
        "ref": "0.80 - 1.20",
        "orden": 1320
    },
    "INR": {
        "nombre": "INR",
        "categoria": "coagulacion",
        "grupo": "⏱️ Coagulación y Hemostasia",
        "unidad": "ratio",
        "ref": "0.80 - 1.20",
        "orden": 1330
    },
    "TTPA": {
        "nombre": "Tiempo de Tromboplastina Parcial (TTPA)",
        "categoria": "coagulacion",
        "grupo": "⏱️ Coagulación y Hemostasia",
        "unidad": "segundos",
        "ref": "20 - 39 s",
        "orden": 1340
    },
    "FIBRINOGENO": {
        "nombre": "Fibrinógeno",
        "categoria": "coagulacion",
        "grupo": "⏱️ Coagulación y Hemostasia",
        "unidad": "mg/dL",
        "ref": "200 - 400 mg/dL",
        "orden": 1350
    },
    "DIMERO_D": {
        "nombre": "Dímero D",
        "categoria": "coagulacion",
        "grupo": "⏱️ Coagulación y Hemostasia",
        "unidad": "ng/mL",
        "ref": "< 500 ng/mL",
        "orden": 1360
    }
}

# Alias directos para normalización
CANONICAL_CATALOG["GOT"] = CANONICAL_CATALOG["GOT_AST"]
CANONICAL_CATALOG["GPT"] = CANONICAL_CATALOG["GPT_ALT"]
CANONICAL_CATALOG["HEMATÍES"] = CANONICAL_CATALOG["HEMATIES"]
CANONICAL_CATALOG["PROTEÍNA_C_REACTIVA_(PCR)"] = CANONICAL_CATALOG["PROTEINA_C_REACTIVA"]
CANONICAL_CATALOG["FÓSFORO"] = CANONICAL_CATALOG["FOSFORO"]
CANONICAL_CATALOG["CREATIN_KINASA_(CK)"] = CANONICAL_CATALOG["CREATIN_KINASA"]
CANONICAL_CATALOG["TP"] = CANONICAL_CATALOG["TIEMPO_PROTROMBINA"]
CANONICAL_CATALOG["QUICK"] = CANONICAL_CATALOG["INDICE_QUICK"]
CANONICAL_CATALOG["APTT"] = CANONICAL_CATALOG["TTPA"]
CANONICAL_CATALOG["CEFALINA"] = CANONICAL_CATALOG["TTPA"]
CANONICAL_CATALOG["FIBRINÓGENO"] = CANONICAL_CATALOG["FIBRINOGENO"]
CANONICAL_CATALOG["DÍMERO_D"] = CANONICAL_CATALOG["DIMERO_D"]
CANONICAL_CATALOG["APO_B"] = CANONICAL_CATALOG["APOB"]
CANONICAL_CATALOG["LIPOPROTEIN_A"] = CANONICAL_CATALOG["LPA"]
CANONICAL_CATALOG["LP_A"] = CANONICAL_CATALOG["LPA"]
CANONICAL_CATALOG["FG_ESTIMADO"] = CANONICAL_CATALOG["EGFR"]
CANONICAL_CATALOG["MDRD"] = CANONICAL_CATALOG["EGFR"]
CANONICAL_CATALOG["CKD_EPI"] = CANONICAL_CATALOG["EGFR"]
CANONICAL_CATALOG["ALBUMINURIA"] = CANONICAL_CATALOG["UACR"]
CANONICAL_CATALOG["MICROALBUMINURIA"] = CANONICAL_CATALOG["UACR"]
CANONICAL_CATALOG["FT3"] = CANONICAL_CATALOG["T3_LIBRE"]
CANONICAL_CATALOG["FOLATO"] = CANONICAL_CATALOG["ACIDO_FOLICO"]
CANONICAL_CATALOG["B12"] = CANONICAL_CATALOG["VITAMINA_B12"]
CANONICAL_CATALOG["INMUMOGLOBULINA_IGG"] = CANONICAL_CATALOG["IGG"]
CANONICAL_CATALOG["INMUNOGLOBULINA_IGG"] = CANONICAL_CATALOG["IGG"]
CANONICAL_CATALOG["INMUNOGLOBULINA_G"] = CANONICAL_CATALOG["IGG"]
CANONICAL_CATALOG["IG_G"] = CANONICAL_CATALOG["IGG"]
CANONICAL_CATALOG["INMUNOGLOBULINA_IGA"] = CANONICAL_CATALOG["IGA"]
CANONICAL_CATALOG["INMUMOGLOBULINA_IGA"] = CANONICAL_CATALOG["IGA"]
CANONICAL_CATALOG["INMUNOGLOBULINA_A"] = CANONICAL_CATALOG["IGA"]
CANONICAL_CATALOG["IG_A"] = CANONICAL_CATALOG["IGA"]
CANONICAL_CATALOG["INMUNOGLOBULINA_IGM"] = CANONICAL_CATALOG["IGM"]
CANONICAL_CATALOG["INMUMOGLOBULINA_IGM"] = CANONICAL_CATALOG["IGM"]
CANONICAL_CATALOG["INMUNOGLOBULINA_M"] = CANONICAL_CATALOG["IGM"]
CANONICAL_CATALOG["IG_M"] = CANONICAL_CATALOG["IGM"]
CANONICAL_CATALOG["PROTEÍNAS_SÉRICAS"] = CANONICAL_CATALOG["PROTEINAS_TOTALES"]
CANONICAL_CATALOG["PROTEINAS_SERICAS"] = CANONICAL_CATALOG["PROTEINAS_TOTALES"]
CANONICAL_CATALOG["PROTEÍNAS_TOTALES"] = CANONICAL_CATALOG["PROTEINAS_TOTALES"]
CANONICAL_CATALOG["RATIO_PSA"] = CANONICAL_CATALOG["RATIO_PSA_L_T"]
CANONICAL_CATALOG["RATIO_PSA_LIBRE_TOTAL"] = CANONICAL_CATALOG["RATIO_PSA_L_T"]
CANONICAL_CATALOG["RATIO_PSA_L/T"] = CANONICAL_CATALOG["RATIO_PSA_L_T"]
CANONICAL_CATALOG["RATIO_PSA_TOTAL_LIBRE"] = CANONICAL_CATALOG["RATIO_PSA_L_T"]
CANONICAL_CATALOG["CALCIO_CORREGIDO_ALBUMINA"] = CANONICAL_CATALOG["CALCIO_CORREGIDO"]
CANONICAL_CATALOG["CALCIO_CORREGIDO_CON_ALBUMINA"] = CANONICAL_CATALOG["CALCIO_CORREGIDO"]
CANONICAL_CATALOG["CALCIO_CORREGIDO_CON_ALBÚMINA"] = CANONICAL_CATALOG["CALCIO_CORREGIDO"]
CANONICAL_CATALOG["CALCIO_AJUSTADO"] = CANONICAL_CATALOG["CALCIO_CORREGIDO"]
CANONICAL_CATALOG["BETA2_MICROGLOBULINA"] = CANONICAL_CATALOG["BETA_2_MICROGLOBULINA"]
CANONICAL_CATALOG["BETA_2_MICROGLOBULINA_SUERO"] = CANONICAL_CATALOG["BETA_2_MICROGLOBULINA"]
CANONICAL_CATALOG["B2_MICROGLOBULINA"] = CANONICAL_CATALOG["BETA_2_MICROGLOBULINA"]
CANONICAL_CATALOG["BETA_2_M"] = CANONICAL_CATALOG["BETA_2_MICROGLOBULINA"]
CANONICAL_CATALOG["ANTICUERPOS_ANTI_PEPTIDO_CICLICO_CITRULINADO"] = CANONICAL_CATALOG["ANTI_CCP"]
CANONICAL_CATALOG["ANTICUERPOS_ANTI_PEPTIDO_CICLICO_CITRULINADO_(CCP)"] = CANONICAL_CATALOG["ANTI_CCP"]
CANONICAL_CATALOG["ANTI_PEPTIDO_CICLICO_CITRULINADO"] = CANONICAL_CATALOG["ANTI_CCP"]
CANONICAL_CATALOG["ANTICUERPOS_ANTI_CCP"] = CANONICAL_CATALOG["ANTI_CCP"]
CANONICAL_CATALOG["ANTI_CCP"] = CANONICAL_CATALOG["ANTI_CCP"]
CANONICAL_CATALOG["AC_ANTI_CCP"] = CANONICAL_CATALOG["ANTI_CCP"]
CANONICAL_CATALOG["CCP"] = CANONICAL_CATALOG["ANTI_CCP"]
CANONICAL_CATALOG["ANTICUERPOS_ANTI_NUCLEARES"] = CANONICAL_CATALOG["ANA"]
CANONICAL_CATALOG["ANTICUERPOS_ANTI_NUCLEARES_(ANA)"] = CANONICAL_CATALOG["ANA"]
CANONICAL_CATALOG["ANTICUERPOS_ANTINUCLEARES"] = CANONICAL_CATALOG["ANA"]
CANONICAL_CATALOG["ANTI_NUCLEARES"] = CANONICAL_CATALOG["ANA"]
CANONICAL_CATALOG["ANTINUCLEARES"] = CANONICAL_CATALOG["ANA"]
CANONICAL_CATALOG["ANA"] = CANONICAL_CATALOG["ANA"]
CANONICAL_CATALOG["AC_ANTI_NUCLEARES"] = CANONICAL_CATALOG["ANA"]
CANONICAL_CATALOG["IDH"] = CANONICAL_CATALOG["RDW"]
CANONICAL_CATALOG["IDE"] = CANONICAL_CATALOG["RDW"]
CANONICAL_CATALOG["ADE"] = CANONICAL_CATALOG["RDW"]
CANONICAL_CATALOG["INDICE_DISTRIBUCION_HEMATIES"] = CANONICAL_CATALOG["RDW"]
CANONICAL_CATALOG["INDICE_DE_DISTRIBUCION_DE_HEMATIES"] = CANONICAL_CATALOG["RDW"]
CANONICAL_CATALOG["VOLUMEN_PLAQUETAR_MEDIO"] = CANONICAL_CATALOG["VPM"]
CANONICAL_CATALOG["VOLUMEN_PLAQUETARIO_MEDIO"] = CANONICAL_CATALOG["VPM"]
CANONICAL_CATALOG["MPV"] = CANONICAL_CATALOG["VPM"]

# Compatibilidad con clave canónica antigua
CANONICAL_ANALITOS = {
    k: (v["nombre"], v["categoria"], v["unidad"])
    for k, v in CANONICAL_CATALOG.items()
}

def _normalize_str_key(s: str) -> str:
    import unicodedata
    return unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8').upper()

def get_analito_group(code: str) -> str:
    """Devuelve el grupo clínico formateado para un analito."""
    item = CANONICAL_CATALOG.get(code)
    if item:
        return item["grupo"]
    code_u = _normalize_str_key(code)
    if any(k in code_u for k in ["PROTROMB", "QUICK", "INR", "TTPA", "TROMBOPLAST", "APTT", "CEFALINA", "FIBRINOG", "DIMERO"]):
        return "⏱️ Coagulación y Hemostasia"
    if code_u.startswith("IGE_") or "ALERG" in code_u or any(k in code_u for k in ["IGG", "IGA", "IGM", "INMUNOGLOB", "INMUMOGLOB", "PROTEINAS_TOTALES", "PROTEINAS_SERICAS", "MICROGLOBULINA", "BETA_2", "CCP", "ANA", "NUCLEARES", "AUTOINMUN"]):
        return "🌸 Alergología e Inmunología"
    if any(k in code_u for k in ["CALCIO", "POTASIO", "SODIO", "MAGNESIO", "FOSFORO"]):
        return "⚡ Enzimas Hepáticas e Iones Séricos"
    if "ORINA" in code_u or "URIN" in code_u:
        return "📋 Sistemático y Sedimento de Orina"
    if any(k in code_u for k in ["NEUTR", "LINFO", "MONO", "EOSIN", "BASO", "LEUCO", "HEMAT", "PLAQUET"]):
        return "🩸 Hemograma y Serie Hematológica"
    if any(k in code_u for k in ["VSG", "KATZ"]):
        return "🛡️ Metabolismo Férrico e Inflamatorio"
    return "🔬 Otros Parámetros Bioquímicos"

def get_analito_order(code: str) -> int:
    """Devuelve el orden de visualización de un analito."""
    item = CANONICAL_CATALOG.get(code)
    if item:
        return item["orden"]
    code_u = _normalize_str_key(code)
    if any(k in code_u for k in ["PROTROMB", "QUICK", "INR", "TTPA", "TROMBOPLAST", "APTT", "CEFALINA", "FIBRINOG", "DIMERO"]):
        return 1325
    if any(k in code_u for k in ["NEUTR", "LINFO", "MONO", "EOSIN", "BASO", "LEUCO", "HEMAT", "PLAQUET"]):
        return 825
    if any(k in code_u for k in ["VSG", "KATZ"]):
        return 550
    if any(k in code_u for k in ["CALCIO", "POTASIO", "SODIO"]):
        return 675
    if "ORINA" in code_u or "URIN" in code_u:
        return 1025
    if code_u.startswith("IGE_") or "ALERG" in code_u or any(k in code_u for k in ["IGG", "IGA", "IGM", "INMUNOGLOB", "INMUMOGLOB", "MICROGLOBULINA", "BETA_2", "CCP", "ANA", "NUCLEARES"]):
        return 1250
    return 9999

def get_analito_ref(code: str) -> str:
    """Devuelve el rango de referencia por defecto."""
    item = CANONICAL_CATALOG.get(code)
    if item:
        return item["ref"]
    return ""

def normalize_analito(
    nombre: str,
    unidad: Optional[str] = None,
    valor: Optional[Any] = None,
    codigo_sugerido: Optional[str] = None
) -> Tuple[str, str, str, str]:
    """
    Normaliza cualquier nombre extraído a su código canónico, nombre estándar,
    categoría y unidad estandarizada.
    
    Aplica salvaguardas clínicas:
    - Impide que un cociente o ratio aterogénico se asigne a Colesterol Total o HDL.
    - Impide que analitos de orina sobrescriban analitos séricos.
    """
    nom = (nombre or "").strip()
    # Limpiar asteriscos de positividad o notas de OCR al inicio o final del nombre
    nom = re.sub(r"^[\s\*#•\-]+|[\s\*#•\-]+$", "", nom).strip()
    nom_lower = nom.lower()
    uni = (unidad or "").strip()
    # Corregir erratas frecuentes de OCR en unidades de alérgenos (ej: KkU/L, KkUIL, ku/l)
    if re.search(r"(?i)\bkk?u[\s/]*i?l\b", uni):
        uni = "kU/L"
    val_str = str(valor or "").strip()
    
    # 1. Si viene un código sugerido válido del LLM, comprobar que no tenga conflicto flagrante
    if codigo_sugerido and codigo_sugerido.upper() in CANONICAL_CATALOG:
        cand_code = codigo_sugerido.upper()
        es_ratio = any(r in nom_lower for r in ["cociente", "ratio", "índice", "indice", "castelli"]) or uni == "ratio"
        if cand_code in ["CHOLESTEROL_TOTAL", "HDL", "LDL", "TRIGLYCERIDES"] and es_ratio:
            pass  # Descartar código incorrecto y analizar semánticamente
        else:
            std = CANONICAL_CATALOG[cand_code]
            unit_ret = unidad or std["unidad"]
            if cand_code in ["HEMATIES", "HEMATÍES"] and any(u in (unidad or "").lower() for u in ["ul", "µl", "mm3"]):
                unit_ret = "x10^6/µL"
            return cand_code, std["nombre"], std["categoria"], unit_ret

    # 2. Desambiguación de Orina / Sistemático / Sedimento
    val_lower = val_str.lower()
    es_cualitativo_orina = any(q in val_lower for q in ["negativo", "positivo", "indicios", "trazas"]) or "cualitativo" in uni
    es_orina = (
        any(k in nom_lower for k in ["orina", "sedimento", "sistemático", "sistematico", "urina", "tira reactiva", "albúmina-prot", "albumina-prot"])
        or (es_cualitativo_orina and any(k in nom_lower for k in ["glucosa", "albúmina", "albumina", "proteína", "proteina", "densidad", "nitrito", "urobilin", "ceton"]))
    )
    if es_orina:
        if any(k in nom_lower for k in ["uacr", "cociente albúmina/creatinina", "cociente albumina/creatinina", "microalbuminuria", "albuminuria"]):
            return "UACR", "Cociente Albúmina/Creatinina (uACR)", "orina", unidad or "mg/g"
        if any(k in nom_lower for k in ["glucosa", "glucosuria"]):
            return "GLUCOSE_URINE", "Glucosa (Orina)", "orina", unidad or "Cualitativo"
        if any(k in nom_lower for k in ["albúmina", "albumina", "proteína", "proteina", "prot"]):
            return "PROTEIN_URINE", "Proteínas / Albúmina (Orina)", "orina", unidad or "Cualitativo"
        if "densidad" in nom_lower:
            return "DENSIDAD_URINE", "Densidad (Orina)", "orina", unidad or "g/mL"
        if "ph" in nom_lower:
            return "PH_URINE", "pH (Orina)", "orina", unidad or "pH"
        if "sedimento" in nom_lower:
            return "SEDIMENTO_URINARIO", "Sedimento Urinario", "orina", unidad or "Texto"

    # 3. Desambiguación de Cocientes e Índices Aterogénicos (Castelli I, II y TG/HDL)
    es_cociente = any(k in nom_lower for k in ["cociente", "ratio", "índice", "indice", "castelli"]) or uni == "ratio"
    if es_cociente or (("col" in nom_lower or "ldl" in nom_lower or "tg" in nom_lower) and "/" in nom_lower):
        # Ratios de composición con Colesterol Total en denominador
        if "hdl" in nom_lower and ("col" in nom_lower) and ("hdl / col" in nom_lower or "hdl/col" in nom_lower or nom_lower.startswith("ratio hdl")):
            return "RATIO_HDL_COL", "Ratio HDL / Col. Total", "bioquimica", "ratio"
        if "ldl" in nom_lower and ("col" in nom_lower) and ("ldl / col" in nom_lower or "ldl/col" in nom_lower or nom_lower.startswith("ratio ldl")):
            return "RATIO_LDL_COL", "Ratio LDL / Col. Total", "bioquimica", "ratio"
        if ("tg" in nom_lower or "trigli" in nom_lower) and ("col" in nom_lower) and ("tg / col" in nom_lower or "tg/col" in nom_lower or "triglicéridos / col" in nom_lower):
            return "RATIO_TG_COL", "Ratio TG / Col. Total", "bioquimica", "ratio"

        # Triglicéridos / HDL
        if ("tg" in nom_lower or "trigli" in nom_lower) and "hdl" in nom_lower:
            return "RATIO_TG_HDL", "Triglicéridos / HDL", "bioquimica", "ratio"
        # Castelli I: Colesterol Total / HDL
        if ("col" in nom_lower and "hdl" in nom_lower and "ldl" not in nom_lower) or "castelli i" in nom_lower or "col.t/hdl" in nom_lower:
            return "RATIO_COL_HDL", "Colesterol Total / HDL (Castelli I)", "bioquimica", "ratio"
        # Castelli II: LDL / HDL
        if ("ldl" in nom_lower and "hdl" in nom_lower) or "castelli ii" in nom_lower or "ldl-col/hdl" in nom_lower:
            return "RATIO_LDL_HDL", "LDL / HDL (Castelli II)", "bioquimica", "ratio"
        # Ratio PSA
        if "psa" in nom_lower and any(k in nom_lower for k in ["l/t", "libre", "fracción", "fraccion", "ratio", "cociente"]):
            unit_ret = unidad or ("%" if "%" in (unidad or "") else "ratio")
            return "RATIO_PSA_L_T", "Ratio PSA Libre / Total", "bioquimica", unit_ret

    # 3.4 Inmunoglobulinas Séricas y Proteínas Séricas
    es_igg = (
        (codigo_sugerido and codigo_sugerido.upper() in ["IGG", "INMUNOGLOBULINA_IGG", "INMUMOGLOBULINA_IGG", "INMUNOGLOBULINA_G"])
        or any(k in nom_lower for k in ["inmunoglobulina igg", "inmumoglobulina igg", "inmunoglobulina g", "inmumoglobulina g", "inmuno globulina igg"])
        or (re.search(r"\bigg\b", nom_lower) and not any(k in nom_lower for k in ["ige", "igm", "iga"]))
    )
    if es_igg:
        return "IGG", "Inmunoglobulina IgG", "inmunologia", unidad or "mg/dL"

    es_iga = (
        (codigo_sugerido and codigo_sugerido.upper() in ["IGA", "INMUNOGLOBULINA_IGA", "INMUMOGLOBULINA_IGA", "INMUNOGLOBULINA_A"])
        or any(k in nom_lower for k in ["inmunoglobulina iga", "inmumoglobulina iga", "inmunoglobulina a", "inmumoglobulina a"])
        or (re.search(r"\biga\b", nom_lower) and not any(k in nom_lower for k in ["ige", "igm", "igg"]))
    )
    if es_iga:
        return "IGA", "Inmunoglobulina IgA", "inmunologia", unidad or "mg/dL"

    es_igm = (
        (codigo_sugerido and codigo_sugerido.upper() in ["IGM", "INMUNOGLOBULINA_IGM", "INMUMOGLOBULINA_IGM", "INMUNOGLOBULINA_M"])
        or any(k in nom_lower for k in ["inmunoglobulina igm", "inmumoglobulina igm", "inmunoglobulina m", "inmumoglobulina m"])
        or (re.search(r"\bigm\b", nom_lower) and not any(k in nom_lower for k in ["ige", "iga", "igg"]))
    )
    if es_igm:
        return "IGM", "Inmunoglobulina IgM", "inmunologia", unidad or "mg/dL"

    if any(k in nom_lower for k in ["proteínas séricas", "proteinas sericas", "proteínas totales", "proteinas totales"]) and not es_orina:
        return "PROTEINAS_TOTALES", "Proteínas Totales", "bioquimica", unidad or "g/dL"

    if any(k in nom_lower for k in ["beta-2 microglobulina", "beta 2 microglobulina", "beta-2-microglobulina", "b2 microglobulina", "b2-microglobulina", "microglobulina beta 2", "microglobulina beta-2", "microglobulina"]) and not es_orina:
        return "BETA_2_MICROGLOBULINA", "Beta-2 Microglobulina", "inmunologia", unidad or "mcg/mL"

    # 3.4.1 Autoinmunidad y Anticuerpos Específicos (Anti-CCP y ANA)
    es_anti_ccp = (
        (codigo_sugerido and codigo_sugerido.upper() in ["ANTI_CCP", "ANTICUERPOS_ANTI_CCP", "ANTICUERPOS_ANTI_PEPTIDO_CICLICO_CITRULINADO", "CCP"])
        or any(k in nom_lower for k in ["peptido ciclico", "péptido cíclico", "citrulinado", "anti-ccp", "anticuerpos anti-ccp", "anticuerpos anti-péptido", "anticuerpos anti-peptido"])
        or (re.search(r"\bccp\b", nom_lower) and "pcp" not in nom_lower)
    )
    if es_anti_ccp:
        return "ANTI_CCP", "Anticuerpos Anti-CCP", "inmunologia", unidad or "UI/mL"

    es_ana = (
        (codigo_sugerido and codigo_sugerido.upper() in ["ANA", "ANTICUERPOS_ANTI_NUCLEARES", "ANTICUERPOS_ANTINUCLEARES"])
        or any(k in nom_lower for k in ["antinucleares", "anti-nucleares", "antinuclear", "anti-nuclear"])
        or (re.search(r"\bana\b", nom_lower) and (nom_lower == "ana" or "anticuerpo" in nom_lower or "inmuno" in nom_lower or "auto" in nom_lower or codigo_sugerido == "ANA"))
    )
    if es_ana:
        return "ANA", "Anticuerpos Anti-Nucleares (ANA)", "inmunologia", unidad or ""

    # 3.4.2 Anticuerpos Tiroideos (Anti-TPO, Anti-TG, TRAb)
    es_anti_tpo = (
        (codigo_sugerido and codigo_sugerido.upper() in ["ANTI_TPO", "ANTICUERPOS_ANTI_TPO", "ANTI-TPO", "TPO", "ATPO"])
        or any(k in nom_lower for k in ["anti-tpo", "anti tpo", "antiperoxidasa", "anti-peroxidasa", "peroxidasa tiroidea", "microsomales"])
    )
    if es_anti_tpo:
        return "ANTI_TPO", "Anticuerpos Anti-TPO", "inmunologia", unidad or "UI/mL"

    es_anti_tg = (
        (codigo_sugerido and codigo_sugerido.upper() in ["ANTI_TG", "ANTICUERPOS_ANTI_TG", "ANTI-TG", "ATG"])
        or any(k in nom_lower for k in ["anti-tiroglobulina", "anti tiroglobulina", "antitiroglobulina", "anti-tg", "anti tg"])
    )
    if es_anti_tg:
        return "ANTI_TG", "Anticuerpos Anti-Tiroglobulina", "inmunologia", unidad or "UI/mL"

    es_trab = (
        (codigo_sugerido and codigo_sugerido.upper() in ["TRAB", "TSI", "ANTICUERPOS_TRAB", "ANTI_TSHR"])
        or any(k in nom_lower for k in ["trab", "tshr", "receptor de tsh", "antirreceptor de tsh", "tsi", "inmunoglobulina estimulante del tiroides"])
    )
    if es_trab:
        return "TRAB", "Anticuerpos Anti-Receptor TSH (TRAb)", "inmunologia", unidad or "UI/L"

    # 3.5 Alergología e Inmunología (Anticuerpos IgE específicos y totales)
    es_ige = (
        (codigo_sugerido and codigo_sugerido.upper().startswith("IGE_"))
        or "ige" in nom_lower
        or "alérgeno" in nom_lower or "alergeno" in nom_lower
        or "anticuerpo" in nom_lower and any(k in nom_lower for k in ["específico", "especifico", "alerg"])
        or any(k in nom_lower for k in [
            "cynodon", "lolium", "cupressus", "ballico", "grama mayor", "grama de olor", 
            "arizonica", "arizónica", "olea europaea", "dermatophagoides", "parietaria", 
            "salsola", "artemisia", "alternaria", "anthoxanthum"
        ])
    )
    if es_ige:
        # IgE Total
        if ("total" in nom_lower or "inmunoglobulina e total" in nom_lower or (codigo_sugerido and codigo_sugerido.upper() == "IGE_TOTAL")) and not any(k in nom_lower for k in ["cynodon", "lolium", "cupressus", "especific", "ballico", "grama"]):
            return "IGE_TOTAL", "Inmunoglobulina E Total (IgE)", "inmunologia", uni or "UI/mL"

        # IgE Específicas catalogadas
        if "cynodon" in nom_lower or "grama mayor" in nom_lower:
            return "IGE_CYNODON_DACTYLON", "IgE Cynodon dactylon (Grama mayor)", "inmunologia", uni or "kU/L"
        if "lolium" in nom_lower or "ballico" in nom_lower or "ray-grass" in nom_lower:
            return "IGE_LOLIUM_PERENNE", "IgE Lolium perenne (Ballico / Ray-grass)", "inmunologia", uni or "kU/L"
        if "cupressus" in nom_lower or "arizonica" in nom_lower or "arizónica" in nom_lower:
            return "IGE_CUPRESSUS_ARIZONICA", "IgE Cupressus arizonica (Arizónica)", "inmunologia", uni or "kU/L"
        if "olea" in nom_lower or "olivo" in nom_lower:
            return "IGE_OLEA_EUROPAEA", "IgE Olea europaea (Olivo)", "inmunologia", uni or "kU/L"
        if "plantago" in nom_lower or "llantén" in nom_lower or "llanten" in nom_lower:
            return "IGE_PLANTAGO_LANCEOLATA", "IgE Plantago lanceolata (Llantén)", "inmunologia", uni or "kU/L"
        if "parietaria" in nom_lower:
            return "IGE_PARIETARIA_JUDAICA", "IgE Parietaria judaica", "inmunologia", uni or "kU/L"
        if "salsola" in nom_lower or "barrilla" in nom_lower:
            return "IGE_SALSOLA_KALI", "IgE Salsola kali (Barrilla)", "inmunologia", uni or "kU/L"
        if "artemisia" in nom_lower or "ajenjo" in nom_lower:
            return "IGE_ARTEMISIA_VULGARIS", "IgE Artemisia vulgaris (Ajenjo)", "inmunologia", uni or "kU/L"
        if "pteronyssinus" in nom_lower:
            return "IGE_DERMATOPHAGOIDES_PTERONYSSINUS", "IgE D. pteronyssinus (Ácaro)", "inmunologia", uni or "kU/L"
        if "farinae" in nom_lower:
            return "IGE_DERMATOPHAGOIDES_FARINAE", "IgE D. farinae (Ácaro)", "inmunologia", uni or "kU/L"
        if "gato" in nom_lower:
            return "IGE_EPITELIO_GATO", "IgE Epitelio de Gato", "inmunologia", uni or "kU/L"
        if "perro" in nom_lower:
            return "IGE_EPITELIO_PERRO", "IgE Epitelio de Perro", "inmunologia", uni or "kU/L"
        if "alternaria" in nom_lower:
            return "IGE_ALTERNARIA_ALTERNATA", "IgE Alternaria alternata (Hongo)", "inmunologia", uni or "kU/L"

        # Otros alérgenos o anticuerpos específicos dinámicos
        clean_nom = re.sub(r"(?i)^anticuerpos\s+ige\s+espec[íi]ficos?\s*[:-]?\s*", "", nom).strip()
        if not clean_nom.lower().startswith("ige"):
            clean_nom = f"IgE {clean_nom}"

        if codigo_sugerido and codigo_sugerido.upper().startswith("IGE_"):
            code_gen = codigo_sugerido.upper()
        else:
            cand_slug = re.sub(r"[^A-Z0-9_]", "", _normalize_str_key(clean_nom).replace(" ", "_"))[:25]
            code_gen = cand_slug if cand_slug.startswith("IGE_") else f"IGE_{cand_slug}"

        return code_gen, clean_nom, "inmunologia", uni or "kU/L"

    # 4. Analitos de Suero y Bioquímica General
    # 4.1 Glucosa basal en sangre
    if any(k in nom_lower for k in ["glucosa", "glucemia", "glicemia"]) and not es_orina:
        return "GLUCOSE", "Glucosa Basal", "bioquimica", unidad or "mg/dL"

    # 4.2 HbA1c, Insulina y HOMA
    if any(k in nom_lower for k in ["hba1c", "hemoglobina glicada", "hemoglobina glicosilada"]):
        if "ifcc" in nom_lower or "mmol" in uni:
            return "HBA1C_IFCC", "HbA1c (IFCC)", "bioquimica", "mmol/mol"
        return "HBA1C", "HbA1c", "bioquimica", "%"
    if "insulina" in nom_lower:
        return "INSULINA", "Insulina Basal", "bioquimica", unidad or "µUI/mL"
    if "homa" in nom_lower:
        return "HOMA_IR", "Índice HOMA-IR", "bioquimica", "ratio"

    # 4.3 Fracciones Lipídicas en sangre (solo si NO son cocientes)
    if not es_cociente:
        if "apob" in nom_lower or "apolipoproteina b" in nom_lower or "apolipoproteína b" in nom_lower:
            return "APOB", "Apolipoproteína B (ApoB)", "bioquimica", unidad or "mg/dL"
        if "lp(a)" in nom_lower or "lpa" in nom_lower or "lipoproteina a" in nom_lower or "lipoproteína a" in nom_lower:
            return "LPA", "Lipoproteína (a) [Lp(a)]", "bioquimica", unidad or "mg/dL"
        if "hdl" in nom_lower:
            return "HDL", "HDL-Colesterol", "bioquimica", unidad or "mg/dL"
        if "ldl" in nom_lower:
            return "LDL", "LDL-Colesterol", "bioquimica", unidad or "mg/dL"
        if any(k in nom_lower for k in ["triglicérido", "triglicerido", "trigliceridos", "triglicéridos"]):
            return "TRIGLYCERIDES", "Triglicéridos", "bioquimica", unidad or "mg/dL"
        if "colesterol" in nom_lower:
            return "CHOLESTEROL_TOTAL", "Colesterol Total", "bioquimica", unidad or "mg/dL"

    # 4.4 Renal
    if any(k in nom_lower for k in ["filtrado glomerular", "fg estimado", "egfr", "ckd-epi", "mdrd"]):
        return "EGFR", "Filtrado Glomerular Estimado (eGFR CKD-EPI)", "bioquimica", unidad or "mL/min/1.73m²"
    if "creatinina" in nom_lower and not es_orina:
        return "CREATININE", "Creatinina", "bioquimica", unidad or "mg/dL"
    if "urea" in nom_lower and "nitrógeno" not in nom_lower and "bun" not in nom_lower and not es_orina:
        return "UREA", "Urea", "bioquimica", unidad or "mg/dL"
    if "bun" in nom_lower or "nitrógeno ureico" in nom_lower or "nitrogeno ureico" in nom_lower:
        return "BUN", "BUN (Nitrógeno Ureico)", "bioquimica", unidad or "mg/dL"
    if any(k in nom_lower for k in ["ácido úrico", "acido urico", "urato"]) and not es_orina:
        return "URIC_ACID", "Ácido Úrico", "bioquimica", unidad or "mg/dL"

    # 4.5 PSA y Marcadores
    if "psa" in nom_lower:
        if any(k in nom_lower for k in ["ratio", "cociente", "l/t", "libre/total", "libre/psa", "libre / total", "libre / psa-total", "l-total", "l_t"]):
            unit_ret = unidad or ("%" if "%" in (unidad or "") else "ratio")
            return "RATIO_PSA_L_T", "Ratio PSA Libre / Total", "bioquimica", unit_ret
        if any(k in nom_lower for k in ["libre", "free", "fracción libre", "fraccion libre"]):
            return "PSA_FREE", "PSA Libre", "bioquimica", unidad or "ng/mL"
        return "PSA_TOTAL", "PSA Total", "bioquimica", unidad or "ng/mL"
    if "tsh" in nom_lower:
        return "TSH", "TSH", "bioquimica", unidad or "µUI/mL"
    if any(k in nom_lower for k in ["t4 libre", "t4l", "ft4"]):
        return "T4_LIBRE", "T4 Libre", "bioquimica", unidad or "ng/dL"
    if any(k in nom_lower for k in ["t3 libre", "t3l", "ft3", "triyodotironina libre"]):
        return "T3_LIBRE", "T3 Libre", "bioquimica", unidad or "pg/mL"
    if any(k in nom_lower for k in ["vitamina d", "25-oh", "calcidiol"]):
        return "VITAMIN_D", "25-OH Vitamina D", "bioquimica", unidad or "ng/mL"
    if "parathormona" in nom_lower or "pth" in nom_lower:
        return "PTH_INTACTA", "PTH Intacta", "bioquimica", unidad or "pg/mL"
    if "cea" in nom_lower:
        return "CEA", "CEA", "bioquimica", unidad or "ng/mL"
    if "ca 125" in nom_lower or "ca125" in nom_lower:
        return "CA_125_II", "CA 125 II", "bioquimica", unidad or "UI/mL"
    if "ca 19" in nom_lower or "ca19" in nom_lower:
        return "CA_19_9", "CA 19-9", "bioquimica", unidad or "UI/mL"

    # 4.6 Hierro, Vitaminas y Proteínas
    if "ferritina" in nom_lower:
        return "FERRITINA", "Ferritina", "bioquimica", unidad or "ng/mL"
    if "hierro" in nom_lower and "orina" not in nom_lower:
        return "HIERRO", "Hierro", "bioquimica", unidad or "µg/dL"
    if any(k in nom_lower for k in ["vitamina b12", "b12", "cobalamina"]):
        return "VITAMINA_B12", "Vitamina B12", "bioquimica", unidad or "pg/mL"
    if any(k in nom_lower for k in ["ácido fólico", "acido folico", "folato", "folatos"]):
        return "ACIDO_FOLICO", "Ácido Fólico (Folato)", "bioquimica", unidad or "ng/mL"
    if any(k in nom_lower for k in ["proteina c reactiva", "proteína c reactiva"]) or re.search(r"\bpcr\b", nom_lower):
        if "orina" not in nom_lower:
            return "PROTEINA_C_REACTIVA", "Proteína C Reactiva (PCR)", "bioquimica", unidad or "mg/dL"
    if "factor reumatoide" in nom_lower:
        return "FACTOR_REUMATOIDE", "Factor Reumatoide", "bioquimica", unidad or "UI/mL"
    if "calcio" in nom_lower and any(k in nom_lower for k in ["corregido", "ajustado", "albumina", "albúmina"]):
        return "CALCIO_CORREGIDO", "Calcio Corregido", "bioquimica", unidad or "mg/dL"
    if any(k in nom_lower for k in ["albúmina", "albumina"]) and not es_orina and "uacr" not in nom_lower and "ratio" not in nom_lower and "calcio" not in nom_lower:
        return "ALBUMINA", "Albúmina", "bioquimica", unidad or "g/dL"

    # 4.7 Enzimas e Iones
    if re.search(r"\b(got|ast)\b", nom_lower) or "aspartato" in nom_lower:
        return "GOT_AST", "GOT / AST", "bioquimica", unidad or "U/L"
    if re.search(r"\b(gpt|alt)\b", nom_lower) or "alanina" in nom_lower:
        return "GPT_ALT", "GPT / ALT", "bioquimica", unidad or "U/L"
    if re.search(r"\bggt\b", nom_lower) or "gamma glutamil" in nom_lower or "g-gt" in nom_lower:
        return "GGT", "GGT", "bioquimica", unidad or "U/L"
    if "fosfatasa alcalina" in nom_lower:
        return "FOSFATASA_ALCALINA", "Fosfatasa Alcalina", "bioquimica", unidad or "U/L"
    if "amilasa" in nom_lower:
        return "AMILASA", "Amilasa", "bioquimica", unidad or "U/L"
    if "sodio" in nom_lower and not es_orina:
        return "SODIO", "Sodio", "bioquimica", unidad or "mmol/L"
    if "potasio" in nom_lower and not es_orina:
        return "POTASIO", "Potasio", "bioquimica", unidad or "mmol/L"
    if "calcio" in nom_lower and not es_orina:
        if any(k in nom_lower for k in ["corregido", "ajustado", "albumina", "albúmina"]):
            return "CALCIO_CORREGIDO", "Calcio Corregido", "bioquimica", unidad or "mg/dL"
        return "CALCIO_TOTAL", "Calcio Total", "bioquimica", unidad or "mg/dL"
    if "fósforo" in nom_lower or "fosforo" in nom_lower:
        return "FOSFORO", "Fósforo", "bioquimica", unidad or "mg/dL"
    if "magnesio" in nom_lower:
        return "MAGNESIO", "Magnesio", "bioquimica", unidad or "mmol/L"
    if "bilirrubina" in nom_lower and not es_orina:
        return "BILIRRUBINA_TOTAL", "Bilirrubina Total", "bioquimica", unidad or "mg/dL"

    # 4.8 Hemograma
    if any(k in nom_lower for k in ["rdw", "idh", "ide", "ade", "distribución de hematíes", "distribucion de hematies", "distribución eritrocitaria", "distribucion eritrocitaria"]) or bool(re.search(r"\b(rdw|idh|ide|ade)\b", nom_lower)):
        return "RDW", "RDW", "hemograma", "%"
    if any(k in nom_lower for k in ["vpm", "mpv", "volumen plaquetar", "volumen plaquetario"]) or bool(re.search(r"\b(vpm|mpv)\b", nom_lower)):
        return "VPM", "VPM", "hemograma", "fL"
    if ("hematíes" in nom_lower or "hematies" in nom_lower) and not any(k in nom_lower for k in ["distribución", "distribucion", "idh", "rdw"]):
        unit_ret = "x10^6/µL" if not unidad or any(u in (unidad or "").lower() for u in ["ul", "µl", "mm3"]) else unidad
        return "HEMATIES", "Hematíes", "hemograma", unit_ret
    if "hemoglobina" in nom_lower and not es_orina:
        return "HEMOGLOBINA", "Hemoglobina", "hemograma", unidad or "g/dL"
    if "hematocrito" in nom_lower:
        return "HEMATOCRITO", "Hematocrito", "hemograma", "%"
    if nom_lower == "vcm" or "volumen corpuscular medio" in nom_lower:
        return "VCM", "VCM", "hemograma", "fL"
    if nom_lower == "hcm" or "hemoglobina corpuscular media" in nom_lower:
        return "HCM", "HCM", "hemograma", "pg"
    if nom_lower in ["chcm", "cmhc"]:
        return "CHCM", "CHCM", "hemograma", "%"
    if "plaquetas" in nom_lower:
        return "PLAQUETAS", "Plaquetas", "hemograma", "x10^3/µL"
    if "leucocitos" in nom_lower and not es_orina:
        return "LEUCOCITOS", "Leucocitos", "hemograma", "x10^3/µL"

    # 4.9 Coagulación y Hemostasia
    if "tiempo de protrombina" in nom_lower or (nom_lower.startswith("tiempo") and "protromb" in nom_lower):
        return "TIEMPO_PROTROMBINA", "Tiempo de Protrombina (TP)", "coagulacion", unidad or "segundos"
    if "quick" in nom_lower or "actividad de protrombina" in nom_lower:
        return "INDICE_QUICK", "Índice de Quick", "coagulacion", "%"
    if nom_lower == "inr" or "inr" in nom_lower.split():
        return "INR", "INR", "coagulacion", "ratio"
    if "ratio" in nom_lower and any(k in nom_lower for k in ["tp", "protrombina", "coagula"]):
        return "RATIO_TP", "Ratio de Protrombina", "coagulacion", "ratio"
    if nom_lower == "ratio" and (not codigo_sugerido or codigo_sugerido == "RATIO_TP"):
        return "RATIO_TP", "Ratio de Protrombina", "coagulacion", "ratio"
    if "fibrinógeno" in nom_lower or "fibrinogeno" in nom_lower:
        return "FIBRINOGENO", "Fibrinógeno", "coagulacion", unidad or "mg/dL"
    if "dímero d" in nom_lower or "dimero d" in nom_lower or "dimerod" in nom_lower:
        return "DIMERO_D", "Dímero D", "coagulacion", unidad or "ng/mL"

    # Fallback genérico limpio
    clean_code = re.sub(r"[^A-Z0-9_]", "", nom.upper().replace(" ", "_"))[:30]
    cat_fallback = "inmunologia" if clean_code.startswith("IGE_") or "ALERG" in clean_code else "bioquimica"
    return clean_code, nom, cat_fallback, unidad or "-"


def scale_ref_range(
    ref_str: Optional[str],
    factor: float,
    new_unit: str = "",
    condition_fn: Optional[Any] = None
) -> str:
    """
    Escala los valores numéricos de un rango de referencia (ej: '1.1 - 4.5' -> '1100 - 4500 /µL').
    Si se especifica condition_fn, solo se escala si condition_fn(numeros) es True.
    """
    if not ref_str or str(ref_str).strip() in ["-", "", "None"]:
        return ref_str or ""
    core = re.sub(r"(?i)[/\s]*(?:x?10[\^%3][36]?|[pµu]?l|g/dl|g/l|mg/dl|ui/ml|ng/ml|%)\b.*$", "", str(ref_str).strip()).strip()
    nums = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[\.,]\d+)?", core)]
    if not nums:
        return ref_str
    if condition_fn and not condition_fn(nums):
        if new_unit and new_unit not in str(ref_str):
            return f"{str(ref_str).strip()} {new_unit}".strip()
        return ref_str

    def repl(m):
        try:
            val = float(m.group(1).replace(",", "."))
            new_val = val * factor
            if new_val.is_integer():
                return str(int(new_val))
            return f"{new_val:.2f}".rstrip("0").rstrip(".")
        except Exception:
            return m.group(0)
    scaled = re.sub(r"(\d+(?:[\.,]\d+)?)", repl, core)
    if new_unit and new_unit not in scaled:
        return f"{scaled} {new_unit}".strip()
    return scaled


def standardize_medicion(
    codigo: str,
    valor: Any,
    unidad: Optional[str] = None,
    rango_referencia: Optional[str] = None
) -> Tuple[Optional[float], str, str, str]:
    """
    Estandariza un valor analítico a su unidad fija canónica y transforma su magnitud numérica
    y su rango de referencia si el laboratorio utilizó métricas o escalas alternativas.
    
    Retorna:
    (valor_numerico_estandar: Optional[float],
     valor_texto_limpio: str,
     unidad_canonica: str,
     rango_referencia_estandar: str)
    """
    code_up = (codigo or "").upper()
    cat_entry = CANONICAL_CATALOG.get(code_up, {})
    canonical_unit = cat_entry.get("unidad", unidad or "")
    default_ref = cat_entry.get("ref", rango_referencia or "")
    ref_in = rango_referencia or default_ref

    if valor is None:
        return None, "", canonical_unit, ref_in

    val_raw = str(valor).strip()
    if not val_raw:
        return None, "", canonical_unit, ref_in

    # Limpiar prefijos de alerta o símbolos (ej: * 1.5 -> 1.5, # 4.9 -> 4.9)
    cleaned = re.sub(r"^[\s\*#•\-]+", "", val_raw).strip()
    if not cleaned:
        return None, val_raw, canonical_unit, ref_in

    # Tomar primer token si viene con unidad pegada (ej: "4.900.000 /ul")
    first_tok = cleaned.split()[0] if cleaned else ""

    # Manejar formatos de números con puntos y comas
    if first_tok.count(".") > 1:
        num_str = first_tok.replace(".", "").replace(",", ".")
    elif "," in first_tok and "." in first_tok:
        if first_tok.rfind(",") > first_tok.rfind("."):
            num_str = first_tok.replace(".", "").replace(",", ".")
        else:
            num_str = first_tok.replace(",", "")
    elif "," in first_tok:
        num_str = first_tok.replace(",", ".")
    else:
        num_str = first_tok

    try:
        num_val = float(num_str)
    except (ValueError, TypeError):
        return None, val_raw, canonical_unit, ref_in

    u_lower = (unidad or "").lower()

    # 1. Fórmula Leucocitaria Absoluta (Linfocitos, Neutrófilos, Monocitos, Eosinófilos, Basófilos) -> Unidad fija: /µL
    if code_up in ["LINFOCITOS_ABS", "NEUTROFILOS_ABS", "MONOCITOS_ABS", "EOSINOFILOS_ABS", "BASOFILOS_ABS"]:
        # Si viene en x10^3/µL o el valor es menor a 50, se escala x1000 a /µL
        if num_val < 50.0 or any(k in u_lower for k in ["10^3", "10*3", "10%", "mil", "k/", "10^9"]):
            num_val = round(num_val * 1000.0, 1)
            ref_final = scale_ref_range(ref_in, 1000.0, "/µL", lambda nums: all(n < 50 for n in nums)) if ref_in else default_ref
        else:
            ref_final = ref_in or default_ref
        formatted = str(int(round(num_val))) if num_val.is_integer() else f"{num_val:.1f}"
        return num_val, formatted, "/µL", ref_final

    # 2. Leucocitos Totales -> Unidad fija: x10^3/µL
    if code_up == "LEUCOCITOS":
        if num_val > 100.0:
            num_val = round(num_val / 1000.0, 2)
            ref_final = scale_ref_range(ref_in, 0.001, "x10^3/µL", lambda nums: any(n > 100 for n in nums)) if ref_in else default_ref
        else:
            ref_final = ref_in or default_ref
        formatted = f"{num_val:.2f}"
        return num_val, formatted, "x10^3/µL", ref_final

    # 3. Plaquetas -> Unidad fija: x10^3/µL
    if code_up == "PLAQUETAS":
        if num_val > 10_000.0:
            num_val = round(num_val / 1000.0, 1)
            ref_final = scale_ref_range(ref_in, 0.001, "x10^3/µL", lambda nums: any(n > 1000 for n in nums)) if ref_in else default_ref
        else:
            ref_final = ref_in or default_ref
        formatted = f"{int(num_val)}" if num_val.is_integer() else f"{num_val:.1f}"
        return num_val, formatted, "x10^3/µL", ref_final

    # 4. Hematíes -> Unidad fija: x10^6/µL
    if code_up in ["HEMATIES", "HEMATÍES"]:
        if num_val > 100_000.0:
            num_val = round(num_val / 1_000_000.0, 3)
            ref_final = scale_ref_range(ref_in, 0.000001, "x10^6/µL", lambda nums: any(n > 100000 for n in nums)) if ref_in else default_ref
        else:
            ref_final = ref_in or default_ref
        formatted = f"{num_val:.2f}" if first_tok.count(".") > 1 else (f"{num_val:.2f}" if num_val < 10 else first_tok)
        return num_val, formatted, "x10^6/µL", ref_final

    # 5. Hemoglobina -> Unidad fija: g/dL
    if code_up == "HEMOGLOBINA":
        if num_val > 50.0 or ("g/l" in u_lower and "dl" not in u_lower):
            num_val = round(num_val / 10.0, 1)
            ref_final = scale_ref_range(ref_in, 0.1, "g/dL", lambda nums: any(n > 50 for n in nums)) if ref_in else default_ref
        else:
            ref_final = ref_in or default_ref
        formatted = f"{num_val:.1f}"
        return num_val, formatted, "g/dL", ref_final

    # 6. Proteínas Totales y Albúmina -> Unidad fija: g/dL
    if code_up in ["PROTEINAS_TOTALES", "ALBUMINA", "ALBUMINA_SERICA"]:
        if num_val > 20.0 or ("g/l" in u_lower and "dl" not in u_lower):
            num_val = round(num_val / 10.0, 1)
            ref_final = scale_ref_range(ref_in, 0.1, "g/dL", lambda nums: any(n > 20 for n in nums)) if ref_in else default_ref
        else:
            ref_final = ref_in or default_ref
        formatted = f"{num_val:.1f}"
        return num_val, formatted, "g/dL", ref_final

    # 7. Vitamina D -> Unidad fija: ng/mL
    if code_up == "VITAMIN_D":
        if "nmol" in u_lower:
            num_val = round(num_val / 2.496, 2)
            ref_final = scale_ref_range(ref_in, 1.0 / 2.496, "ng/mL", lambda nums: any(n > 100 for n in nums)) if ref_in else default_ref
        else:
            ref_final = ref_in or default_ref
        formatted = f"{num_val:.2f}"
        return num_val, formatted, "ng/mL", ref_final

    return num_val, first_tok, canonical_unit, ref_in


def normalize_valor_numerico(
    codigo: str,
    valor: Any,
    unidad: Optional[str] = None
) -> Tuple[Optional[float], str]:
    """
    Convierte y normaliza de forma segura un valor analítico (texto o numérico) a:
    (num_val: Optional[float], text_val: str), asegurando escala canónica uniforme.
    """
    num_val, clean_text, _, _ = standardize_medicion(codigo, valor, unidad)
    return num_val, clean_text


def parse_reference_bounds(ref_str: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """
    Extrae los límites inferior y superior de un rango de referencia textual.
    Ejemplos:
      '17.4 - 49.2' -> (17.4, 49.2)
      '< 116 mg/dL' -> (None, 116.0)
      'Inf. 40' -> (None, 40.0)
      '> 40' -> (40.0, None)
      'Sup. 10' -> (10.0, None)
    """
    if not ref_str or str(ref_str).strip() in ["-", "", "None", "Sin referencia", "No especificado"]:
        return None, None
    s = str(ref_str).strip().replace(",", ".")
    
    # 1. Menor que / Inferior
    m_inf = re.search(r"(?:<|<=|inf\.?|inferior(?:\s+a)?)\s*(\d+(?:\.\d+)?)", s, re.IGNORECASE)
    if m_inf and not re.search(r"\d+\s*[-a]\s*\d+", s):
        try:
            return None, float(m_inf.group(1))
        except Exception:
            pass

    # 2. Mayor que / Superior
    m_sup = re.search(r"(?:>|>=|sup\.?|superior(?:\s+a)?)\s*(\d+(?:\.\d+)?)", s, re.IGNORECASE)
    if m_sup and not re.search(r"\d+\s*[-a]\s*\d+", s):
        try:
            return float(m_sup.group(1)), None
        except Exception:
            pass

    # 3. Intervalo min - max (o 'min a max')
    clean_s = re.sub(r"(?i)[/\s]*(?:x?10[\^%3][36]?|[pµu]?l|g/dl|g/l|mg/dl|ui/ml|ng/ml|%|ratio|segundos|mmol/mol)\b.*$", "", s).strip()
    m_range = re.findall(r"(\d+(?:\.\d+)?)", clean_s)
    if len(m_range) >= 2:
        try:
            low = float(m_range[0])
            high = float(m_range[1])
            if low <= high:
                return low, high
            return high, low
        except Exception:
            pass

    return None, None


def evaluar_estado_semaforo(val_num: Optional[float], ref_str: Optional[str]) -> str:
    """
    Determina si un valor numérico está dentro de rango (Normal), Alto o Bajo
    según la cadena de referencia dada.
    """
    if val_num is None:
        return "Normal"
    low, high = parse_reference_bounds(ref_str)
    if low is not None and val_num < low - 1e-5:
        return "Bajo"
    if high is not None and val_num > high + 1e-5:
        return "Alto"
    return "Normal"


def es_medicion_alterada(
    val_num: Optional[float],
    ref_str: Optional[str],
    estado_semaforo: Optional[str] = None
) -> bool:
    """
    Evalúa si un valor numérico está alterado basándose en el rango de referencia oficial
    y el estado semafórico del laboratorio.
    """
    if val_num is None:
        return False

    # 1. Si tenemos rango de referencia interpretable, evaluamos directamente el valor numérico
    if ref_str:
        calc_st = evaluar_estado_semaforo(val_num, ref_str)
        if calc_st in ["Alto", "Bajo"]:
            return True
        elif calc_st == "Normal":
            # Si el cálculo numérico dentro del rango da Normal, pero el semáforo indica alerta clínica grave
            if estado_semaforo:
                st_clean = estado_semaforo.strip().lower()
                if any(x in st_clean for x in ["atencion", "atención", "alerta", "alergen"]):
                    return True
            return False

    # 2. Si no hay rango de referencia o no fue interpretable, consultar estado semafórico
    if estado_semaforo:
        st_clean = estado_semaforo.strip().lower()
        if any(x in st_clean for x in ["alto", "bajo", "atencion", "atención", "alerta", "alergen", "fuera"]):
            return True
        if any(x in st_clean for x in ["normal", "ptim", "buen", "correcto"]):
            return False

    return False


