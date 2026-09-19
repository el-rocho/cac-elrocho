"""
Servicio Clínico de Variaciones y Tendencias Longitudinales.
Implementa:
1. Variación entre las 2 últimas determinaciones (delta y RCV).
2. Tendencia longitudinal (últimos 24 meses, regresión lineal OLS con tiempo real, >= 3 determinaciones).
3. Interpretación clínica (FAVORABLE, ESTABLE, DESFAVORABLE).
4. Tendencia global de tarjeta (jerarquía de analitos principales y secundarios, 5 estados:
   FAVORABLE, ESTABLE, DESFAVORABLE, MIXTA, SIN TENDENCIA).
"""
from datetime import datetime, date
from typing import List, Dict, Tuple, Optional, Any


DIR_LOWER_IS_BETTER = "lower"
DIR_HIGHER_IS_BETTER = "higher"
DIR_RANGE_OPTIMAL = "range"

CLINICAL_FAVORABLE = "FAVORABLE"
CLINICAL_ESTABLE = "ESTABLE"
CLINICAL_DESFAVORABLE = "DESFAVORABLE"
CLINICAL_MIXTA = "MIXTA"
CLINICAL_SIN_TENDENCIA = "SIN TENDENCIA"

ANALITO_CONFIG: Dict[str, Dict[str, Any]] = {
    "GLUCOSE": {
        "var_threshold": 4.0,           # mg/dL
        "slope_threshold": 3.0,         # mg/dL/año
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 70.0,
        "opt_max": 99.0,
        "unit": "mg/dL",
        "decimals": 0
    },
    "HBA1C": {
        "var_threshold": 0.2,           # %
        "slope_threshold": 0.15,        # %/año
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 4.5,
        "opt_max": 5.6,
        "unit": "%",
        "decimals": 1
    },
    "RATIO_TG_HDL": {
        "var_threshold": 0.20,
        "slope_threshold": 0.20,        # ratio/año
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 0.5,
        "opt_max": 2.0,
        "unit": "",
        "decimals": 2
    },
    "INSULINA": {
        "var_threshold": 2.5,
        "slope_threshold": 2.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 2.6,
        "opt_max": 15.0,
        "unit": "µUI/mL",
        "decimals": 1
    },
    "HOMA_IR": {
        "var_threshold": 0.3,
        "slope_threshold": 0.25,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 0.5,
        "opt_max": 2.2,
        "unit": "",
        "decimals": 2
    },
    "CHOLESTEROL_TOTAL": {
        "var_threshold": 10.0,
        "slope_threshold": 8.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 120.0,
        "opt_max": 200.0,
        "unit": "mg/dL",
        "decimals": 0
    },
    "LDL": {
        "var_threshold": 8.0,
        "slope_threshold": 6.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 50.0,
        "opt_max": 115.0,
        "unit": "mg/dL",
        "decimals": 0
    },
    "HDL": {
        "var_threshold": 4.0,
        "slope_threshold": 3.0,
        "direction": DIR_HIGHER_IS_BETTER,
        "opt_min": 45.0,
        "opt_max": 90.0,
        "unit": "mg/dL",
        "decimals": 0
    },
    "TRIGLYCERIDES": {
        "var_threshold": 15.0,
        "slope_threshold": 12.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 50.0,
        "opt_max": 150.0,
        "unit": "mg/dL",
        "decimals": 0
    },
    "RATIO_COL_HDL": {
        "var_threshold": 0.25,
        "slope_threshold": 0.20,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 2.0,
        "opt_max": 4.5,
        "unit": "",
        "decimals": 2
    },
    "RATIO_LDL_HDL": {
        "var_threshold": 0.20,
        "slope_threshold": 0.15,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 1.0,
        "opt_max": 3.0,
        "unit": "",
        "decimals": 2
    },
    "APOB": {
        "var_threshold": 8.0,
        "slope_threshold": 6.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 40.0,
        "opt_max": 90.0,
        "unit": "mg/dL",
        "decimals": 0
    },
    "LPA": {
        "var_threshold": 5.0,
        "slope_threshold": 4.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 0.0,
        "opt_max": 30.0,
        "unit": "mg/dL",
        "decimals": 0
    },
    "CREATININE": {
        "var_threshold": 0.08,
        "slope_threshold": 0.06,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 0.60,
        "opt_max": 1.15,
        "unit": "mg/dL",
        "decimals": 2
    },
    "EGFR": {
        "var_threshold": 5.0,
        "slope_threshold": 3.0,
        "direction": DIR_HIGHER_IS_BETTER,
        "opt_min": 90.0,
        "opt_max": 130.0,
        "unit": "mL/min",
        "decimals": 1
    },
    "UREA": {
        "var_threshold": 5.0,
        "slope_threshold": 4.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 15.0,
        "opt_max": 45.0,
        "unit": "mg/dL",
        "decimals": 0
    },
    "URIC_ACID": {
        "var_threshold": 0.5,
        "slope_threshold": 0.4,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 3.0,
        "opt_max": 6.5,
        "unit": "mg/dL",
        "decimals": 1
    },
    "UACR": {
        "var_threshold": 5.0,
        "slope_threshold": 4.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 0.0,
        "opt_max": 30.0,
        "unit": "mg/g",
        "decimals": 1
    },
    "GPT_ALT": {
        "var_threshold": 6.0,
        "slope_threshold": 5.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 8.0,
        "opt_max": 40.0,
        "unit": "U/L",
        "decimals": 0
    },
    "GOT_AST": {
        "var_threshold": 5.0,
        "slope_threshold": 4.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 8.0,
        "opt_max": 38.0,
        "unit": "U/L",
        "decimals": 0
    },
    "GGT": {
        "var_threshold": 5.0,
        "slope_threshold": 4.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 8.0,
        "opt_max": 50.0,
        "unit": "U/L",
        "decimals": 0
    },
    "FOSFATASA_ALCALINA": {
        "var_threshold": 8.0,
        "slope_threshold": 6.0,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 40.0,
        "opt_max": 120.0,
        "unit": "U/L",
        "decimals": 0
    },
    "BILIRRUBINA_TOTAL": {
        "var_threshold": 0.20,
        "slope_threshold": 0.15,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 0.2,
        "opt_max": 1.1,
        "unit": "mg/dL",
        "decimals": 1
    },
    "HEMOGLOBINA": {
        "var_threshold": 0.5,
        "slope_threshold": 0.4,
        "direction": DIR_RANGE_OPTIMAL,
        "opt_min": 13.0,
        "opt_max": 17.5,
        "unit": "g/dL",
        "decimals": 1
    },
    "HEMATOCRITO": {
        "var_threshold": 1.5,
        "slope_threshold": 1.0,
        "direction": DIR_RANGE_OPTIMAL,
        "opt_min": 40.0,
        "opt_max": 51.0,
        "unit": "%",
        "decimals": 1
    },
    "VCM": {
        "var_threshold": 1.5,
        "slope_threshold": 1.0,
        "direction": DIR_RANGE_OPTIMAL,
        "opt_min": 82.0,
        "opt_max": 96.0,
        "unit": "fL",
        "decimals": 1
    },
    "LEUCOCITOS": {
        "var_threshold": 0.8,
        "slope_threshold": 0.6,
        "direction": DIR_RANGE_OPTIMAL,
        "opt_min": 4.2,
        "opt_max": 10.5,
        "unit": "mil/µL",
        "decimals": 2
    },
    "PLAQUETAS": {
        "var_threshold": 25.0,
        "slope_threshold": 20.0,
        "direction": DIR_RANGE_OPTIMAL,
        "opt_min": 140.0,
        "opt_max": 400.0,
        "unit": "mil/µL",
        "decimals": 0
    },
    "FERRITINA": {
        "var_threshold": 15.0,
        "slope_threshold": 10.0,
        "direction": DIR_RANGE_OPTIMAL,
        "opt_min": 35.0,
        "opt_max": 250.0,
        "unit": "ng/mL",
        "decimals": 0
    },
    "HIERRO": {
        "var_threshold": 15.0,
        "slope_threshold": 12.0,
        "direction": DIR_RANGE_OPTIMAL,
        "opt_min": 65.0,
        "opt_max": 155.0,
        "unit": "µg/dL",
        "decimals": 0
    },
    "TSH": {
        "var_threshold": 0.40,
        "slope_threshold": 0.30,
        "direction": DIR_RANGE_OPTIMAL,
        "opt_min": 0.40,
        "opt_max": 3.80,
        "unit": "µUI/mL",
        "decimals": 2
    },
    "T4_LIBRE": {
        "var_threshold": 0.15,
        "slope_threshold": 0.10,
        "direction": DIR_RANGE_OPTIMAL,
        "opt_min": 0.75,
        "opt_max": 1.70,
        "unit": "ng/dL",
        "decimals": 2
    },
    "T3_LIBRE": {
        "var_threshold": 0.30,
        "slope_threshold": 0.20,
        "direction": DIR_RANGE_OPTIMAL,
        "opt_min": 2.20,
        "opt_max": 4.20,
        "unit": "pg/mL",
        "decimals": 2
    },
    "PSA_TOTAL": {
        "var_threshold": 0.20,
        "slope_threshold": 0.15,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 0.0,
        "opt_max": 2.5,
        "unit": "ng/mL",
        "decimals": 2
    },
    "VITAMINA_D": {
        "var_threshold": 4.0,
        "slope_threshold": 3.0,
        "direction": DIR_HIGHER_IS_BETTER,
        "opt_min": 30.0,
        "opt_max": 60.0,
        "unit": "ng/mL",
        "decimals": 1
    },
    "PROTEINA_C_REACTIVA": {
        "var_threshold": 0.15,
        "slope_threshold": 0.10,
        "direction": DIR_LOWER_IS_BETTER,
        "opt_min": 0.0,
        "opt_max": 0.5,
        "unit": "mg/dL",
        "decimals": 2
    }
}

CARD_CONFIG: Dict[str, Dict[str, List[str]]] = {
    "metabolismo_glucidico": {
        "primary": ["GLUCOSE", "HBA1C"],
        "secondary": ["RATIO_TG_HDL", "INSULINA", "HOMA_IR"]
    },
    "perfil_lipidico": {
        "primary": ["CHOLESTEROL_TOTAL", "LDL", "APOB", "RATIO_COL_HDL"],
        "secondary": ["HDL", "TRIGLYCERIDES", "RATIO_LDL_HDL", "RATIO_TG_HDL", "LPA"]
    },
    "funcion_renal": {
        "primary": ["CREATININE", "EGFR"],
        "secondary": ["UREA", "URIC_ACID", "UACR"]
    },
    "funcion_hepatica": {
        "primary": ["GPT_ALT", "GOT_AST"],
        "secondary": ["GGT", "FOSFATASA_ALCALINA", "BILIRRUBINA_TOTAL"]
    },
    "hemograma_hierro": {
        "primary": ["HEMOGLOBINA", "HEMATOCRITO", "FERRITINA"],
        "secondary": ["VCM", "LEUCOCITOS", "PLAQUETAS", "HIERRO"]
    },
    "tiroides": {
        "primary": ["TSH"],
        "secondary": ["T4_LIBRE", "T3_LIBRE"]
    }
}


def parse_date_safe(d_str: str) -> Optional[date]:
    if not d_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(d_str.strip(), fmt).date()
        except ValueError:
            pass
    return None


def calcular_variacion_reciente(val_actual: Optional[float], val_anterior: Optional[float], cod_analito: str) -> Tuple[Optional[str], str, Optional[float], bool]:
    """
    Calcula la variación respecto a la determinación anterior.
    A petición clínica:
    - Sin flechas (↑, ↓, → eliminadas).
    - Solo muestra el valor numérico con su signo (+delta o -delta) cuando exista variación significativa.
    - Si la variación es nula o dentro del umbral de estabilidad, retorna cadena vacía "".
    """
    if val_actual is None or val_anterior is None:
        return None, "", None, False

    cfg = ANALITO_CONFIG.get(cod_analito, {})
    umbral = cfg.get("var_threshold")
    decimals = cfg.get("decimals", 1)

    if umbral is None:
        umbral = max(0.01, abs(val_actual) * 0.02)

    delta = val_actual - val_anterior
    if abs(delta) <= umbral:
        return None, "", delta, False

    if delta > 0:
        if decimals == 0:
            delta_str = f"+{int(round(delta))}"
        else:
            delta_str = f"+{delta:.{decimals}f}"
        return None, delta_str, delta, True
    else:
        if decimals == 0:
            delta_str = f"-{abs(int(round(delta)))}"
        else:
            delta_str = f"-{abs(delta):.{decimals}f}"
        return None, delta_str, delta, True


def calcular_tendencia_longitudinal(
    puntos: List[Tuple[date, float]], 
    fecha_referencia: Optional[date] = None,
    ventana_meses: int = 24, 
    min_muestras: int = 3,
    cod_analito: str = ""
) -> Tuple[Optional[str], Optional[float], int]:
    """
    Calcula la tendencia longitudinal con OLS en tiempo real continuo (años).
    Estrategia de ventana:
    1. Si en la ventana de 24 meses existen >= min_muestras (3), se usan todas las determinaciones de esa ventana.
    2. Si en 24 meses existen menos de 3 determinaciones (debido a chequeos espaciados anualmente o gaps),
       pero el paciente dispone de >= 3 determinaciones en su historial, se toman las determinaciones más recientes
       disponibles (últimas 3 a 5 determinaciones) para computar la pendiente anual en tiempo real.
    3. Si el paciente tiene menos de 3 determinaciones en total, retorna None (Sin tendencia).
    """
    if not puntos or len(puntos) < min_muestras:
        return None, None, len(puntos) if puntos else 0

    puntos_sorted = sorted(puntos, key=lambda p: p[0])

    if fecha_referencia is None:
        fecha_referencia = puntos_sorted[-1][0]

    dias_ventana = int(ventana_meses * 30.4375)
    fecha_inicio = fecha_referencia.toordinal() - dias_ventana

    muestras_24m = [p for p in puntos_sorted if p[0].toordinal() >= fecha_inicio and p[0].toordinal() <= fecha_referencia.toordinal()]

    if len(muestras_24m) >= min_muestras:
        muestras_usadas = muestras_24m
    else:
        # Ventana adaptativa: determinaciones más recientes (hasta 5, mínimo 3)
        muestras_usadas = puntos_sorted[-5:] if len(puntos_sorted) >= 5 else puntos_sorted

    if len(muestras_usadas) < min_muestras:
        return None, None, len(muestras_usadas)

    d0 = muestras_usadas[0][0]
    t_vals = [(p[0] - d0).days / 365.25 for p in muestras_usadas]
    y_vals = [p[1] for p in muestras_usadas]

    n = len(muestras_usadas)
    t_bar = sum(t_vals) / n
    y_bar = sum(y_vals) / n

    denom = sum((ti - t_bar) ** 2 for ti in t_vals)
    if denom == 0:
        return "→", 0.0, n

    numer = sum((ti - t_bar) * (yi - y_bar) for ti, yi in zip(t_vals, y_vals))
    slope = numer / denom

    cfg = ANALITO_CONFIG.get(cod_analito, {})
    umbral = cfg.get("slope_threshold")
    if umbral is None:
        umbral = cfg.get("var_threshold", max(0.01, abs(y_bar) * 0.02))

    if slope > umbral:
        return "↗", slope, n
    elif slope < -umbral:
        return "↘", slope, n
    else:
        return "→", slope, n


def interpretar_tendencia_clinica(cod_analito: str, tendencia_simbolo: Optional[str], val_actual: Optional[float]) -> Optional[str]:
    if tendencia_simbolo is None:
        return None

    if tendencia_simbolo == "→":
        return CLINICAL_ESTABLE

    cfg = ANALITO_CONFIG.get(cod_analito, {})
    direction_type = cfg.get("direction", DIR_LOWER_IS_BETTER)
    opt_min = cfg.get("opt_min")
    opt_max = cfg.get("opt_max")

    if direction_type == DIR_LOWER_IS_BETTER:
        if tendencia_simbolo == "↘":
            if opt_min is not None and val_actual is not None and val_actual < opt_min:
                return CLINICAL_DESFAVORABLE
            return CLINICAL_FAVORABLE
        elif tendencia_simbolo == "↗":
            return CLINICAL_DESFAVORABLE

    elif direction_type == DIR_HIGHER_IS_BETTER:
        if tendencia_simbolo == "↗":
            return CLINICAL_FAVORABLE
        elif tendencia_simbolo == "↘":
            return CLINICAL_DESFAVORABLE

    elif direction_type == DIR_RANGE_OPTIMAL:
        if val_actual is None or opt_min is None or opt_max is None:
            return CLINICAL_ESTABLE

        if val_actual < opt_min:
            return CLINICAL_FAVORABLE if tendencia_simbolo == "↗" else CLINICAL_DESFAVORABLE
        elif val_actual > opt_max:
            return CLINICAL_FAVORABLE if tendencia_simbolo == "↘" else CLINICAL_DESFAVORABLE
        else:
            return CLINICAL_ESTABLE

    return CLINICAL_ESTABLE


def evaluar_tendencia_global_tarjeta(
    evaluaciones_analitos: Dict[str, Optional[str]], 
    card_id: str
) -> Tuple[str, str, str]:
    cfg = CARD_CONFIG.get(card_id, {"primary": [], "secondary": []})
    primary_codes = cfg.get("primary", [])
    secondary_codes = cfg.get("secondary", [])

    prim_trends = [evaluaciones_analitos[c] for c in primary_codes if c in evaluaciones_analitos and evaluaciones_analitos[c] is not None]
    sec_trends = [evaluaciones_analitos[c] for c in secondary_codes if c in evaluaciones_analitos and evaluaciones_analitos[c] is not None]

    if not prim_trends:
        if not sec_trends:
            return "sin_tendencia", CLINICAL_SIN_TENDENCIA, "bg-slate-100 text-slate-600 border-slate-200"
        prim_trends = sec_trends
        sec_trends = []

    has_fav = CLINICAL_FAVORABLE in prim_trends
    has_desfav = CLINICAL_DESFAVORABLE in prim_trends

    if has_fav and has_desfav:
        return "mixta", CLINICAL_MIXTA, "bg-purple-50 text-purple-700 border-purple-200"
    elif has_fav and not has_desfav:
        return "favorable", CLINICAL_FAVORABLE, "bg-emerald-50 text-emerald-700 border-emerald-200"
    elif has_desfav and not has_fav:
        return "desfavorable", CLINICAL_DESFAVORABLE, "bg-rose-50 text-rose-700 border-rose-200"
    else:
        if sec_trends:
            sec_has_fav = CLINICAL_FAVORABLE in sec_trends
            sec_has_desfav = CLINICAL_DESFAVORABLE in sec_trends

            if sec_has_fav and sec_has_desfav:
                return "mixta", CLINICAL_MIXTA, "bg-purple-50 text-purple-700 border-purple-200"
            elif sec_has_fav and not sec_has_desfav:
                return "favorable", CLINICAL_FAVORABLE, "bg-emerald-50 text-emerald-700 border-emerald-200"
            elif sec_has_desfav and not sec_has_fav:
                return "desfavorable", CLINICAL_DESFAVORABLE, "bg-rose-50 text-rose-700 border-rose-200"

        return "estable", CLINICAL_ESTABLE, "bg-blue-50 text-blue-700 border-blue-200"