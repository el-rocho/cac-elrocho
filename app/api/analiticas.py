from datetime import date
from typing import List, Dict, Any, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import __version__
from app.config import settings
from app.services.configuration_service import configuration_service
from app.database import get_db
from app.models import Paciente, Informe, Analito, Medicion
from app.schemas import (
    DashboardSummaryResponse, KpiCard, AnalitoFila, TablesResponse, TableRow, TableCell,
    ChartsResponse, ChartConfig, ChartDataset, AuditFileItem,
    InformeDetailResponse, InformeUpdateRequest, MedicionDetail,
    PacienteInfo, PacienteUpdateRequest, MetricaSimple, OtrosValoresSeccion
)
from app.services.metrics import get_cell_format, calculate_ratios
from app.services.analito_normalizer import (
    get_analito_group, normalize_analito, get_analito_order,
    normalize_valor_numerico, standardize_medicion, evaluar_estado_semaforo,
    es_medicion_alterada
)
from app.services.clinical_trends import (
    calcular_variacion_reciente,
    calcular_tendencia_longitudinal,
    interpretar_tendencia_clinica,
    evaluar_tendencia_global_tarjeta,
    parse_date_safe
)

router = APIRouter(prefix="/analiticas", tags=["Analíticas"])

def calcular_edad(fecha_nacimiento: str) -> str:
    """Calcula los años cumplidos a partir de una fecha en formato YYYY-MM-DD o DD/MM/YYYY."""
    if not fecha_nacimiento or not str(fecha_nacimiento).strip():
        return "-"
    try:
        limpia = str(fecha_nacimiento).strip()
        partes = limpia.split("-")
        if len(partes) == 3:
            birth_year, birth_month, birth_day = int(partes[0]), int(partes[1]), int(partes[2])
            hoy = date.today()
            edad = hoy.year - birth_year - ((hoy.month, hoy.day) < (birth_month, birth_day))
            if 0 <= edad <= 125:
                return f"{edad} años"
        partes_slash = limpia.split("/")
        if len(partes_slash) == 3:
            birth_day, birth_month, birth_year = int(partes_slash[0]), int(partes_slash[1]), int(partes_slash[2])
            hoy = date.today()
            edad = hoy.year - birth_year - ((hoy.month, hoy.day) < (birth_month, birth_day))
            if 0 <= edad <= 125:
                return f"{edad} años"
    except Exception:
        pass
    return "-"

def calcular_egfr(creat_mg_dl: float, edad_anos: Any, sexo: str) -> Any:
    """
    Calcula el Filtrado Glomerular Estimado (eGFR) mediante la fórmula CKD-EPI 2021
    (sin coeficiente de raza, estándar internacional KDIGO / consensos europeos).
    """
    if not creat_mg_dl or creat_mg_dl <= 0:
        return None
    try:
        es_mujer = bool(sexo and "fem" in str(sexo).lower())
        k = 0.7 if es_mujer else 0.9
        alpha = -0.241 if es_mujer else -0.302
        mult = 1.012 if es_mujer else 1.0
        age = 50
        if edad_anos is not None:
            if isinstance(edad_anos, (int, float)) and 18 <= edad_anos <= 120:
                age = float(edad_anos)
            elif isinstance(edad_anos, str) and edad_anos.replace("años", "").strip().isdigit():
                age = float(edad_anos.replace("años", "").strip())
        scr_k = creat_mg_dl / k
        egfr = 142.0 * (min(scr_k, 1.0) ** alpha) * (max(scr_k, 1.0) ** -1.200) * (0.9938 ** age) * mult
        return round(egfr, 1)
    except Exception:
        return None

def get_motor_llm_summary() -> Dict[str, Any]:
    """Retorna información del estado de los modelos LLM configurados."""
    slots = configuration_service.get_configured_llm_slots()
    llm_slots = [s for s in slots if s.get("provider") != "mock" and s.get("api_key") and s.get("model")]
    return {
        "activo": len(llm_slots) > 0,
        "tipo": "llm" if len(llm_slots) > 0 else "mock",
        "slots_totales": len(slots),
        "slots_llm": len(llm_slots),
        "modelos": [s["model"] for s in llm_slots],
        "descripcion": f"{len(llm_slots)} modelo(s) configurado(s)" if len(llm_slots) > 0 else "Extractor RegEx (Sin LLM)"
    }

@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(db: Session = Depends(get_db)):
    """
    Devuelve los datos del paciente, resumen de controles y tarjetas KPI de la última analítica.
    """
    paciente = db.query(Paciente).first()
    informes = db.query(Informe).order_by(Informe.fecha.asc()).all()
    motor_info = get_motor_llm_summary()
    
    if not informes:
        return DashboardSummaryResponse(
            paciente={
                "nombre": (paciente.nombre_completo if paciente and paciente.nombre_completo else "").strip(),
                "nacimiento": (paciente.fecha_nacimiento if paciente and paciente.fecha_nacimiento else "-"),
                "edad": calcular_edad(paciente.fecha_nacimiento) if paciente and paciente.fecha_nacimiento else "-",
                "dni": (paciente.dni if paciente and paciente.dni else "-"),
                "sexo": (paciente.sexo if paciente and paciente.sexo else "No especificado")
            },
            total_controles=0,
            periodo_historico="Sin registros",
            ultima_fecha="Ninguna",
            dictamen_global="Base de Datos Vacía",
            dictamen_subtitulo="Carga un PDF o importa un respaldo para iniciar el seguimiento",
            kpis=[],
            otros_valores=[],
            motor_llm_info=motor_info,
            app_version=__version__
        )

    ultimo_informe = informes[-1]
    total_controles = len(informes)
    periodo = f"{informes[0].fecha[:4]} - {informes[-1].fecha[:4]}"
    ultima_fecha = ultimo_informe.fecha

    # Obtener mapa de mediciones del último informe
    meds = db.query(Medicion).filter_by(informe_id=ultimo_informe.id).all()
    m_map = {m.analito.codigo: m for m in meds if m.analito}

    def fmt_date_es(d_str: Optional[str]) -> str:
        if not d_str:
            return ""
        parts = d_str.split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        return d_str

    def get_analyte_meta(cod, default="-") -> Tuple[str, Optional[str], bool]:
        """
        Retorna (valor_str, fecha_str, es_historico).
        Si el analito está en el informe actual:
            (valor, fecha_actual, False)
        Si no está en el actual pero existe en algún informe previo:
            (valor_previo, fecha_previo, True)
        Si no existe en ningún informe:
            (default, None, False)
        """
        m = m_map.get(cod)
        if m and (m.valor_numerico is not None or m.valor_texto):
            val = str(m.valor_numerico) if m.valor_numerico is not None else str(m.valor_texto)
            return val, ultimo_informe.fecha, False
        for inf in reversed(informes[:-1]):
            for past_m in inf.mediciones:
                if past_m.analito and past_m.analito.codigo == cod:
                    if past_m.valor_numerico is not None:
                        return str(past_m.valor_numerico), inf.fecha, True
                    elif past_m.valor_texto:
                        return str(past_m.valor_texto), inf.fecha, True
        return default, None, False

    def get_v(cod, default="-") -> str:
        v, _, _ = get_analyte_meta(cod, default)
        return v

    def fmt(v, decimals=None):
        if v is None or v == "" or v == "-":
            return "-"
        try:
            f = float(str(v).replace(",", "."))
            if decimals is not None:
                return f"{f:.{decimals}f}"
            return str(int(f)) if f == int(f) else str(round(f, 2))
        except Exception:
            return str(v)

    # Helper numérico seguro
    def parse_num(v, default=None):
        if v is None or v == "" or v == "-":
            return default
        try:
            return float(str(v).replace(",", "."))
        except Exception:
            return default

    analitos_cache = {a.codigo: a for a in db.query(Analito).all()}

    def get_analyte_record(cod):
        m = m_map.get(cod)
        if m and (m.valor_numerico is not None or m.valor_texto):
            return m, m.analito or analitos_cache.get(cod)
        for inf in reversed(informes[:-1]):
            for past_m in inf.mediciones:
                if past_m.analito and past_m.analito.codigo == cod:
                    if past_m.valor_numerico is not None or past_m.valor_texto:
                        return past_m, past_m.analito or analitos_cache.get(cod)
        return None, analitos_cache.get(cod)

    def check_is_altered(cod: str, val_str: Any, fallback_ref: Optional[str] = None) -> bool:
        if val_str is None or val_str == "" or val_str == "-":
            return False

        str_val = str(val_str).lower().strip()
        if cod == "ANA" or "anticuerpos" in cod.lower():
            if "positivo" in str_val or ("detecta" in str_val and "no se detecta" not in str_val):
                return True
            if "negativo" in str_val or "no se detecta" in str_val:
                return False

        val_num = parse_num(val_str)
        med_obj, an_obj = get_analyte_record(cod)

        ref_str = None
        estado_semaforo = None
        if med_obj:
            ref_str = med_obj.ref_texto
            estado_semaforo = med_obj.estado_semaforo

        if not ref_str and an_obj and an_obj.ref_texto_defecto:
            ref_str = an_obj.ref_texto_defecto
        if not ref_str:
            ref_str = fallback_ref

        return es_medicion_alterada(val_num, ref_str, estado_semaforo)


    # Helper para formatear valores con resaltado en rojo si están fuera de rango
    def fmt_val(v, decimals=None, is_altered=False):
        res = fmt(v, decimals)
        if res == "-" or not is_altered:
            return res
        return f"<span class='text-rose-600 font-bold'>{res}</span>"

    def get_clean_badge(is_atencion: bool, is_seguimiento: bool):
        if is_atencion:
            return "🔴 Atención", "bg-rose-50 text-rose-700 border-rose-200", "Atención", "bg-rose-100 text-rose-800"
        elif is_seguimiento:
            return "🟡 Seguimiento", "bg-amber-50 text-amber-800 border-amber-200", "Seguimiento", "bg-amber-100 text-amber-800"
        else:
            return "🟢 Normal", "bg-emerald-50 text-emerald-700 border-emerald-200", "Normal", "bg-emerald-100 text-emerald-800"

    # Construir historial cronológico de todas las determinaciones para cálculo de variación y tendencia
    fecha_ref = parse_date_safe(ultimo_informe.fecha) or date.today()
    hist_series: Dict[str, List[Tuple[date, float]]] = {}

    for inf in informes:
        inf_d = parse_date_safe(inf.fecha)
        if not inf_d:
            continue
        m_loc = {}
        for m in inf.mediciones:
            if m.analito and m.valor_numerico is not None:
                cod = m.analito.codigo
                val_f = float(m.valor_numerico)
                m_loc[cod] = val_f
                if cod not in hist_series:
                    hist_series[cod] = []
                hist_series[cod].append((inf_d, val_f))

        # Ratios calculadas en cada control
        if "TRIGLYCERIDES" in m_loc and "HDL" in m_loc and m_loc["HDL"] > 0:
            if "RATIO_TG_HDL" not in hist_series:
                hist_series["RATIO_TG_HDL"] = []
            hist_series["RATIO_TG_HDL"].append((inf_d, round(m_loc["TRIGLYCERIDES"] / m_loc["HDL"], 2)))

        if "CHOLESTEROL_TOTAL" in m_loc and "HDL" in m_loc and m_loc["HDL"] > 0:
            if "RATIO_COL_HDL" not in hist_series:
                hist_series["RATIO_COL_HDL"] = []
            hist_series["RATIO_COL_HDL"].append((inf_d, round(m_loc["CHOLESTEROL_TOTAL"] / m_loc["HDL"], 2)))

        # Friedewald para LDL cuando no esté medido directamente
        if "LDL" not in m_loc and "CHOLESTEROL_TOTAL" in m_loc and "HDL" in m_loc and "TRIGLYCERIDES" in m_loc:
            if m_loc["TRIGLYCERIDES"] < 400:
                ldl_calc = round(m_loc["CHOLESTEROL_TOTAL"] - m_loc["HDL"] - (m_loc["TRIGLYCERIDES"] / 5.0), 1)
                if ldl_calc > 0:
                    m_loc["LDL"] = ldl_calc
                    if "LDL" not in hist_series:
                        hist_series["LDL"] = []
                    hist_series["LDL"].append((inf_d, ldl_calc))

        if "LDL" in m_loc and "HDL" in m_loc and m_loc["HDL"] > 0:
            if "RATIO_LDL_HDL" not in hist_series:
                hist_series["RATIO_LDL_HDL"] = []
            hist_series["RATIO_LDL_HDL"].append((inf_d, round(m_loc["LDL"] / m_loc["HDL"], 2)))

        if "CREATININE" in m_loc:
            edad_inf = None
            if paciente and paciente.fecha_nacimiento:
                fn_d = parse_date_safe(paciente.fecha_nacimiento)
                if fn_d:
                    edad_inf = inf_d.year - fn_d.year - ((inf_d.month, inf_d.day) < (fn_d.month, fn_d.day))
            sexo_p = paciente.sexo if paciente else "Masculino"
            c_calc = calcular_egfr(m_loc["CREATININE"], edad_inf, sexo_p)
            if c_calc is not None:
                if "EGFR" not in hist_series:
                    hist_series["EGFR"] = []
                if not any(p[0] == inf_d for p in hist_series.get("EGFR", [])):
                    hist_series["EGFR"].append((inf_d, float(c_calc)))

    def get_analyte_trend_info(cod: str, val_actual_str: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        pts = hist_series.get(cod, [])
        v_act = parse_num(val_actual_str)
        if v_act is None or not pts:
            return None, None, None, None

        d_act = pts[-1][0]
        val_anterior = None

        # Buscar la determinación previa más reciente dentro de una ventana máxima de 24 meses (~730 días)
        for d_prev, v_prev in reversed(pts[:-1]):
            dias_diff = (d_act - d_prev).days
            if 0 < dias_diff <= 730:
                val_anterior = v_prev
                break
            elif dias_diff > 730:
                break

        var_sym, var_delta, _, _ = calcular_variacion_reciente(v_act, val_anterior, cod)
        trend_sym, slope, n = calcular_tendencia_longitudinal(pts, fecha_referencia=fecha_ref, ventana_meses=24, min_muestras=3, cod_analito=cod)
        clin_trend = interpretar_tendencia_clinica(cod, trend_sym, v_act)
        return var_sym, var_delta, trend_sym, clin_trend

    def asignar_notas_pie_tarjeta(
        main_is_hist: bool,
        main_fecha: Optional[str],
        filas: List[AnalitoFila],
        fecha_actual: str
    ) -> Tuple[Optional[str], List[Dict[str, str]]]:
        SUPER_INDICES = ["¹", "²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹"]
        fechas_unicas = []
        if main_is_hist and main_fecha and main_fecha != fecha_actual:
            if main_fecha not in fechas_unicas:
                fechas_unicas.append(main_fecha)
        for f in filas:
            if f.es_historico and f.fecha_origen and f.fecha_origen != fecha_actual:
                if f.fecha_origen not in fechas_unicas:
                    fechas_unicas.append(f.fecha_origen)

        mapa_simbolos = {}
        notas_pie = []
        for idx, f_raw in enumerate(fechas_unicas):
            sym = SUPER_INDICES[idx] if idx < len(SUPER_INDICES) else f"*{idx+1}"
            mapa_simbolos[f_raw] = sym
            f_fmt = fmt_date_es(f_raw)
            notas_pie.append({
                "simbolo": sym,
                "fecha": f_fmt,
                "texto": f"{sym} Analítica del {f_fmt}"
            })

        main_sym = mapa_simbolos.get(main_fecha) if (main_is_hist and main_fecha) else None
        for f in filas:
            if f.es_historico and f.fecha_origen:
                f.footnote_symbol = mapa_simbolos.get(f.fecha_origen)

        return main_sym, notas_pie

    def build_fila(
        cod: str,
        label: str,
        val_str: str,
        unit: str,
        is_altered: bool,
        decimals: Optional[int] = None,
        es_historico: bool = False,
        fecha_origen: Optional[str] = None,
        es_principal: bool = False,
        tipo_parametro: str = "secundario"
    ) -> Tuple[AnalitoFila, str, Optional[str]]:
        var_sym, var_delta, trend_sym, clin_trend = get_analyte_trend_info(cod, val_str)
        is_undetermined = not val_str or val_str == "-"

        fila = AnalitoFila(
            codigo=cod,
            label=label,
            val=fmt(val_str, decimals),
            unit=unit if not is_undetermined else "",
            is_altered=is_altered if not is_undetermined else False,
            var_symbol=var_sym,
            var_delta=var_delta,
            trend_symbol=trend_sym,
            clinical_trend=clin_trend,
            es_historico=es_historico,
            fecha_origen=fecha_origen,
            footnote_symbol=None,
            es_principal=es_principal,
            tipo_parametro=tipo_parametro
        )

        var_txt = var_delta or ""
        trend_txt = trend_sym or ""
        ind = " ".join([p for p in [var_txt, trend_txt] if p])
        u_str = f" {unit}" if (unit and not is_undetermined) else ""
        linea = f"{label}: {fmt_val(val_str, decimals, is_altered)}{u_str}".strip()
        if ind:
            linea = f"{linea}  {ind}"
        return fila, linea, clin_trend

    # =========================================================================
    # 1. METABOLISMO GLUCÍDICO (Glucosa, HbA1c, TG/HDL, Insulina...)
    # =========================================================================
    glu, glu_date, glu_hist = get_analyte_meta("GLUCOSE", "-")
    hba, hba_date, hba_hist = get_analyte_meta("HBA1C", "-")
    ins, ins_date, ins_hist = get_analyte_meta("INSULINA", "-")
    homa, homa_date, homa_hist = get_analyte_meta("HOMA_IR", "-")

    tg, tg_date, tg_hist = get_analyte_meta("TRIGLYCERIDES", "-")
    hdl, hdl_date, hdl_hist = get_analyte_meta("HDL", "-")

    # Regla estricta para ratio TG/HDL:
    ratio_tg_hdl = "-"
    ratio_tg_hdl_date = None
    ratio_tg_hdl_hist = False

    if tg != "-" and hdl != "-" and tg_date == hdl_date:
        tg_f = parse_num(tg)
        hdl_f = parse_num(hdl)
        if tg_f and hdl_f and hdl_f > 0:
            ratio_tg_hdl = str(round(tg_f / hdl_f, 2))
            ratio_tg_hdl_date = tg_date
            ratio_tg_hdl_hist = tg_hist
    else:
        # No se midieron juntos en el último informe. Buscar ratio histórico válido
        r_stored, r_date, r_hist = get_analyte_meta("RATIO_TG_HDL", "-")
        if r_stored != "-":
            ratio_tg_hdl = r_stored
            ratio_tg_hdl_date = r_date
            ratio_tg_hdl_hist = True
        else:
            for inf in reversed(informes[:-1]):
                loc = {m.analito.codigo: m.valor_numerico for m in inf.mediciones if m.analito and m.valor_numerico is not None}
                if "TRIGLYCERIDES" in loc and "HDL" in loc and loc["HDL"] > 0:
                    ratio_tg_hdl = str(round(loc["TRIGLYCERIDES"] / loc["HDL"], 2))
                    ratio_tg_hdl_date = inf.fecha
                    ratio_tg_hdl_hist = True
                    break

    r_tg_num = parse_num(ratio_tg_hdl)
    glu_num = parse_num(glu)
    hba_num = parse_num(hba)
    ins_num = parse_num(ins)
    homa_num = parse_num(homa)

    # Criterios de alteración unificados según el laboratorio y rangos oficiales
    glu_alt = check_is_altered("GLUCOSE", glu, fallback_ref="60 - 100")
    hba_alt = check_is_altered("HBA1C", hba, fallback_ref="< 5.7")
    tg_hdl_alt = check_is_altered("RATIO_TG_HDL", ratio_tg_hdl, fallback_ref="< 2.0")
    ins_alt = check_is_altered("INSULINA", ins, fallback_ref="2.6 - 24.9")
    homa_alt = check_is_altered("HOMA_IR", homa, fallback_ref="< 2.5")

    glu_atencion = bool((hba_num and hba_num >= 6.5) or (glu_num and glu_num >= 126.0))
    glu_seguimiento = bool(hba_alt or glu_alt or tg_hdl_alt or ins_alt or homa_alt)
    glu_badge, glu_badge_cls, glu_tag, glu_tag_cls = get_clean_badge(glu_atencion, glu_seguimiento)

    glu_v_sym, glu_v_delta, glu_tr_sym, glu_clin_tr = get_analyte_trend_info("GLUCOSE", glu)
    glu_filas = []
    glu_subtitles = []
    glu_evals = {"GLUCOSE": glu_clin_tr}

    # HbA1c y TG/HDL forman el perfil estándar del metabolismo glucídico
    f, l, c_tr = build_fila("HBA1C", "HbA1c", hba, "%", hba_alt, 1, es_historico=hba_hist, fecha_origen=hba_date, es_principal=True, tipo_parametro="principal")
    glu_filas.append(f); glu_subtitles.append(l); glu_evals["HBA1C"] = c_tr

    f, l, c_tr = build_fila("RATIO_TG_HDL", "TG/HDL", ratio_tg_hdl, "", tg_hdl_alt, 2, es_historico=ratio_tg_hdl_hist, fecha_origen=ratio_tg_hdl_date, es_principal=False, tipo_parametro="secundario")
    glu_filas.append(f); glu_subtitles.append(l); glu_evals["RATIO_TG_HDL"] = c_tr

    if ins != "-":
        f, l, c_tr = build_fila("INSULINA", "Insulina", ins, "µUI/mL", ins_alt, 1, es_historico=ins_hist, fecha_origen=ins_date, es_principal=False, tipo_parametro="secundario")
        glu_filas.append(f); glu_subtitles.append(l); glu_evals["INSULINA"] = c_tr
    if homa != "-":
        f, l, c_tr = build_fila("HOMA_IR", "HOMA-IR", homa, "", homa_alt, 2, es_historico=homa_hist, fecha_origen=homa_date, es_principal=False, tipo_parametro="secundario")
        glu_filas.append(f); glu_subtitles.append(l); glu_evals["HOMA_IR"] = c_tr

    glu_main_sym, glu_notas = asignar_notas_pie_tarjeta(glu_hist, glu_date, glu_filas, ultimo_informe.fecha)
    glu_t_state, glu_t_badge, glu_t_cls = evaluar_tendencia_global_tarjeta(glu_evals, "metabolismo_glucidico")

    card_metabolismo = KpiCard(
        id="metabolismo_glucidico",
        title="Metabolismo Glucídico",
        tag=glu_tag,
        tag_class=glu_tag_cls,
        main_label="Glucosa en ayunas",
        main_value=fmt(glu),
        unit="mg/dL",
        main_value_class="text-rose-600 font-semibold" if glu_alt else "text-slate-900 font-semibold",
        is_altered=glu_alt,
        main_var_symbol=glu_v_sym,
        main_var_delta=glu_v_delta,
        main_trend_symbol=glu_tr_sym,
        main_clinical_trend=glu_clin_tr,
        main_is_historical=glu_hist,
        main_fecha_origen=glu_date,
        main_footnote_symbol=glu_main_sym,
        subtitle_1=glu_subtitles[0] if len(glu_subtitles) > 0 else "",
        subtitle_2=glu_subtitles[1] if len(glu_subtitles) > 1 else "",
        subtitle_3=glu_subtitles[2] if len(glu_subtitles) > 2 else "",
        subtitles=glu_subtitles,
        filas=glu_filas,
        badge_text=glu_badge,
        badge_class=glu_badge_cls,
        trend_global=glu_t_state,
        trend_badge_text=glu_t_badge,
        trend_badge_class=glu_t_cls,
        notas_pie=glu_notas
    )

    # =========================================================================
    # 2. PERFIL LIPÍDICO (Col. Total, LDL, HDL, TG, ApoB, Lp(a), Ratios...)
    # =========================================================================
    col_t, col_t_date, col_t_hist = get_analyte_meta("CHOLESTEROL_TOTAL", "-")
    ldl, ldl_date, ldl_hist = get_analyte_meta("LDL", "-")
    hdl, hdl_date, hdl_hist = get_analyte_meta("HDL", "-")
    tg, tg_date, tg_hist = get_analyte_meta("TRIGLYCERIDES", "-")
    apob, apob_date, apob_hist = get_analyte_meta("APOB", "-")
    lpa, lpa_date, lpa_hist = get_analyte_meta("LPA", "-")

    # Friedewald solo si col_t, hdl y tg son de la misma fecha
    if ldl == "-" and col_t != "-" and hdl != "-" and tg != "-" and (col_t_date == hdl_date == tg_date):
        c_f = parse_num(col_t); h_f = parse_num(hdl); t_f = parse_num(tg)
        if c_f and h_f and t_f and t_f < 400:
            ldl_calc = round(c_f - h_f - (t_f / 5.0), 1)
            if ldl_calc > 0:
                ldl = str(ldl_calc)
                ldl_date = col_t_date
                ldl_hist = col_t_hist

    # Ratio Col/HDL (Castelli I)
    ratio_col_hdl = "-"
    ratio_col_hdl_date = None
    ratio_col_hdl_hist = False
    if col_t != "-" and hdl != "-" and col_t_date == hdl_date:
        c_f = parse_num(col_t); h_f = parse_num(hdl)
        if c_f and h_f and h_f > 0:
            ratio_col_hdl = str(round(c_f / h_f, 2))
            ratio_col_hdl_date = col_t_date
            ratio_col_hdl_hist = col_t_hist
    else:
        r_stored, r_date, r_hist = get_analyte_meta("RATIO_COL_HDL", "-")
        if r_stored != "-":
            ratio_col_hdl = r_stored
            ratio_col_hdl_date = r_date
            ratio_col_hdl_hist = True
        else:
            for inf in reversed(informes[:-1]):
                loc = {m.analito.codigo: m.valor_numerico for m in inf.mediciones if m.analito and m.valor_numerico is not None}
                if "CHOLESTEROL_TOTAL" in loc and "HDL" in loc and loc["HDL"] > 0:
                    ratio_col_hdl = str(round(loc["CHOLESTEROL_TOTAL"] / loc["HDL"], 2))
                    ratio_col_hdl_date = inf.fecha
                    ratio_col_hdl_hist = True
                    break

    # Ratio LDL/HDL (Castelli II)
    ratio_ldl_hdl = "-"
    ratio_ldl_hdl_date = None
    ratio_ldl_hdl_hist = False
    if ldl != "-" and hdl != "-" and ldl_date == hdl_date:
        l_f = parse_num(ldl); h_f = parse_num(hdl)
        if l_f and h_f and h_f > 0:
            ratio_ldl_hdl = str(round(l_f / h_f, 2))
            ratio_ldl_hdl_date = ldl_date
            ratio_ldl_hdl_hist = ldl_hist
    else:
        r_stored, r_date, r_hist = get_analyte_meta("RATIO_LDL_HDL", "-")
        if r_stored != "-":
            ratio_ldl_hdl = r_stored
            ratio_ldl_hdl_date = r_date
            ratio_ldl_hdl_hist = True
        else:
            for inf in reversed(informes[:-1]):
                loc = {m.analito.codigo: m.valor_numerico for m in inf.mediciones if m.analito and m.valor_numerico is not None}
                if "LDL" in loc and "HDL" in loc and loc["HDL"] > 0:
                    ratio_ldl_hdl = str(round(loc["LDL"] / loc["HDL"], 2))
                    ratio_ldl_hdl_date = inf.fecha
                    ratio_ldl_hdl_hist = True
                    break

    ldl_num = parse_num(ldl)
    col_num = parse_num(col_t)
    hdl_num = parse_num(hdl)
    tg_num = parse_num(tg)
    r_col_hdl_num = parse_num(ratio_col_hdl)
    r_ldl_hdl_num = parse_num(ratio_ldl_hdl)
    apob_num = parse_num(apob)
    lpa_num = parse_num(lpa)

    col_alt = check_is_altered("CHOLESTEROL_TOTAL", col_t, fallback_ref="< 200")
    ldl_alt = check_is_altered("LDL", ldl, fallback_ref="< 116")
    hdl_alt = check_is_altered("HDL", hdl, fallback_ref="> 40")
    tg_alt = check_is_altered("TRIGLYCERIDES", tg, fallback_ref="< 150")
    r_col_hdl_alt = check_is_altered("RATIO_COL_HDL", ratio_col_hdl, fallback_ref="< 5.0")
    r_ldl_hdl_alt = check_is_altered("RATIO_LDL_HDL", ratio_ldl_hdl, fallback_ref="< 3.0")
    apob_alt = check_is_altered("APOB", apob, fallback_ref="< 100")
    lpa_alt = check_is_altered("LPA", lpa, fallback_ref="< 50")

    lipid_atencion = bool((ldl_num and ldl_num >= 160.0) or (col_num and col_num >= 240.0) or (tg_num and tg_num >= 300.0))
    lipid_seguimiento = bool(col_alt or ldl_alt or hdl_alt or tg_alt or r_col_hdl_alt or r_ldl_hdl_alt or tg_hdl_alt or apob_alt or lpa_alt)
    lipid_badge, lipid_badge_cls, lipid_tag, lipid_tag_cls = get_clean_badge(lipid_atencion, lipid_seguimiento)

    col_v_sym, col_v_delta, col_tr_sym, col_clin_tr = get_analyte_trend_info("CHOLESTEROL_TOTAL", col_t)
    lip_filas = []
    lip_subtitles = []
    lip_evals = {"CHOLESTEROL_TOTAL": col_clin_tr}

    # LDL, HDL, TG y Ratios forman el perfil lipídico estándar
    f, l, c_tr = build_fila("LDL", "LDL", ldl, "mg/dL", ldl_alt, 0, es_historico=ldl_hist, fecha_origen=ldl_date, es_principal=True, tipo_parametro="principal")
    lip_filas.append(f); lip_subtitles.append(l); lip_evals["LDL"] = c_tr

    f, l, c_tr = build_fila("HDL", "HDL", hdl, "mg/dL", hdl_alt, 0, es_historico=hdl_hist, fecha_origen=hdl_date, es_principal=False, tipo_parametro="secundario")
    lip_filas.append(f); lip_subtitles.append(l); lip_evals["HDL"] = c_tr

    f, l, c_tr = build_fila("TRIGLYCERIDES", "TG", tg, "mg/dL", tg_alt, 0, es_historico=tg_hist, fecha_origen=tg_date, es_principal=False, tipo_parametro="secundario")
    lip_filas.append(f); lip_subtitles.append(l); lip_evals["TRIGLYCERIDES"] = c_tr

    f, l, c_tr = build_fila("RATIO_COL_HDL", "Col/HDL", ratio_col_hdl, "", r_col_hdl_alt, 2, es_historico=ratio_col_hdl_hist, fecha_origen=ratio_col_hdl_date, es_principal=True, tipo_parametro="principal")
    lip_filas.append(f); lip_subtitles.append(l); lip_evals["RATIO_COL_HDL"] = c_tr

    f, l, c_tr = build_fila("RATIO_LDL_HDL", "LDL/HDL", ratio_ldl_hdl, "", r_ldl_hdl_alt, 2, es_historico=ratio_ldl_hdl_hist, fecha_origen=ratio_ldl_hdl_date, es_principal=False, tipo_parametro="secundario")
    lip_filas.append(f); lip_subtitles.append(l); lip_evals["RATIO_LDL_HDL"] = c_tr

    f, l, c_tr = build_fila("RATIO_TG_HDL", "TG/HDL", ratio_tg_hdl, "", tg_hdl_alt, 2, es_historico=ratio_tg_hdl_hist, fecha_origen=ratio_tg_hdl_date, es_principal=False, tipo_parametro="secundario")
    lip_filas.append(f); lip_subtitles.append(l); lip_evals["RATIO_TG_HDL"] = c_tr

    if apob != "-":
        f, l, c_tr = build_fila("APOB", "ApoB", apob, "mg/dL", apob_alt, 0, es_historico=apob_hist, fecha_origen=apob_date, es_principal=True, tipo_parametro="principal")
        lip_filas.append(f); lip_subtitles.append(l); lip_evals["APOB"] = c_tr
    if lpa != "-":
        f, l, c_tr = build_fila("LPA", "Lp(a)", lpa, "mg/dL", lpa_alt, 0, es_historico=lpa_hist, fecha_origen=lpa_date, es_principal=False, tipo_parametro="secundario")
        lip_filas.append(f); lip_subtitles.append(l); lip_evals["LPA"] = c_tr

    lip_main_sym, lip_notas = asignar_notas_pie_tarjeta(col_t_hist, col_t_date, lip_filas, ultimo_informe.fecha)
    lip_t_state, lip_t_badge, lip_t_cls = evaluar_tendencia_global_tarjeta(lip_evals, "perfil_lipidico")

    card_lipidos = KpiCard(
        id="perfil_lipidico",
        title="Perfil Lipídico",
        tag=lipid_tag,
        tag_class=lipid_tag_cls,
        main_label="Colesterol Total",
        main_value=fmt(col_t),
        unit="mg/dL",
        main_value_class="text-rose-600 font-semibold" if col_alt else "text-slate-900 font-semibold",
        is_altered=col_alt,
        main_var_symbol=col_v_sym,
        main_var_delta=col_v_delta,
        main_trend_symbol=col_tr_sym,
        main_clinical_trend=col_clin_tr,
        main_is_historical=col_t_hist,
        main_fecha_origen=col_t_date,
        main_footnote_symbol=lip_main_sym,
        subtitle_1=lip_subtitles[0] if len(lip_subtitles) > 0 else "",
        subtitle_2=lip_subtitles[1] if len(lip_subtitles) > 1 else "",
        subtitle_3=lip_subtitles[2] if len(lip_subtitles) > 2 else "",
        subtitles=lip_subtitles,
        filas=lip_filas,
        badge_text=lipid_badge,
        badge_class=lipid_badge_cls,
        trend_global=lip_t_state,
        trend_badge_text=lip_t_badge,
        trend_badge_class=lip_t_cls,
        notas_pie=lip_notas
    )

    # =========================================================================
    # 3. FUNCIÓN RENAL (Creatinina, Urea, Ác. Úrico, eGFR, Albuminuria...)
    # =========================================================================
    creat, creat_date, creat_hist = get_analyte_meta("CREATININE", "-")
    urea, urea_date, urea_hist = get_analyte_meta("UREA", "-")
    urico, urico_date, urico_hist = get_analyte_meta("URIC_ACID", "-")
    egfr, egfr_date, egfr_hist = get_analyte_meta("EGFR", "-")
    uacr, uacr_date, uacr_hist = get_analyte_meta("UACR", "-")
    prot_u, prot_u_date, prot_u_hist = get_analyte_meta("PROTEIN_URINE", "-")

    creat_num = parse_num(creat)
    urico_num = parse_num(urico)
    urea_num = parse_num(urea)
    uacr_num = parse_num(uacr)

    # Cálculo dinámico de eGFR (CKD-EPI 2021) teniendo en cuenta la edad a la fecha de la analítica
    if (egfr == "-" or not egfr) and creat_num:
        edad_anios = None
        if paciente and paciente.fecha_nacimiento:
            fn_d = parse_date_safe(paciente.fecha_nacimiento)
            ref_fecha_str = creat_date or ultimo_informe.fecha
            inf_ref_d = parse_date_safe(ref_fecha_str)
            if fn_d and inf_ref_d:
                edad_anios = inf_ref_d.year - fn_d.year - ((inf_ref_d.month, inf_ref_d.day) < (fn_d.month, fn_d.day))
            else:
                e_str = calcular_edad(paciente.fecha_nacimiento)
                if e_str and e_str != "-":
                    edad_anios = e_str.split()[0]
        sexo_p = paciente.sexo if paciente else "Masculino"
        c_calc = calcular_egfr(creat_num, edad_anios, sexo_p)
        if c_calc is not None:
            egfr = str(c_calc)
            egfr_date = creat_date
            egfr_hist = creat_hist

    egfr_num = parse_num(egfr)

    creat_alt = check_is_altered("CREATININE", creat, fallback_ref="0.60 - 1.20")
    egfr_alt = check_is_altered("EGFR", egfr, fallback_ref="> 60.0")
    urea_alt = check_is_altered("UREA", urea, fallback_ref="17.0 - 49.2")
    urico_alt = check_is_altered("URIC_ACID", urico, fallback_ref="3.0 - 7.0")
    uacr_alt = check_is_altered("UACR", uacr, fallback_ref="< 30.0")

    renal_atencion = bool((creat_num and creat_num >= 1.4) or (egfr_num and egfr_num < 60.0) or (urico_num and urico_num >= 8.5))
    renal_seguimiento = bool(creat_alt or egfr_alt or urea_alt or urico_alt or uacr_alt)
    renal_badge, renal_badge_cls, renal_tag, renal_tag_cls = get_clean_badge(renal_atencion, renal_seguimiento)

    creat_v_sym, creat_v_delta, creat_tr_sym, creat_clin_tr = get_analyte_trend_info("CREATININE", creat)
    ren_filas = []
    ren_subtitles = []
    ren_evals = {"CREATININE": creat_clin_tr}

    # eGFR, Urea y Ác. Úrico forman el perfil renal estándar
    f, l, c_tr = build_fila("EGFR", "eGFR", egfr, "mL/min", egfr_alt, 1, es_historico=egfr_hist, fecha_origen=egfr_date, es_principal=True, tipo_parametro="principal")
    ren_filas.append(f); ren_subtitles.append(l); ren_evals["EGFR"] = c_tr

    f, l, c_tr = build_fila("UREA", "Urea", urea, "mg/dL", urea_alt, 0, es_historico=urea_hist, fecha_origen=urea_date, es_principal=False, tipo_parametro="secundario")
    ren_filas.append(f); ren_subtitles.append(l); ren_evals["UREA"] = c_tr

    f, l, c_tr = build_fila("URIC_ACID", "Ác. Úrico", urico, "mg/dL", urico_alt, 1, es_historico=urico_hist, fecha_origen=urico_date, es_principal=False, tipo_parametro="secundario")
    ren_filas.append(f); ren_subtitles.append(l); ren_evals["URIC_ACID"] = c_tr
    if uacr != "-":
        f, l, c_tr = build_fila("UACR", "uACR", uacr, "mg/g", uacr_alt, 1, es_historico=uacr_hist, fecha_origen=uacr_date, es_principal=False, tipo_parametro="secundario")
        ren_filas.append(f); ren_subtitles.append(l); ren_evals["UACR"] = c_tr
    elif prot_u != "-":
        f = AnalitoFila(label="Albúmina orina", val=prot_u, unit="", es_historico=prot_u_hist, fecha_origen=prot_u_date, es_principal=False, tipo_parametro="secundario")
        ren_filas.append(f)
        ren_subtitles.append(f"Albúmina orina: {prot_u}")

    ren_main_sym, ren_notas = asignar_notas_pie_tarjeta(creat_hist, creat_date, ren_filas, ultimo_informe.fecha)
    ren_t_state, ren_t_badge, ren_t_cls = evaluar_tendencia_global_tarjeta(ren_evals, "funcion_renal")

    card_renal = KpiCard(
        id="funcion_renal",
        title="Función Renal",
        tag=renal_tag,
        tag_class=renal_tag_cls,
        main_label="Creatinina sérica",
        main_value=fmt(creat, 2),
        unit="mg/dL",
        main_value_class="text-rose-600 font-semibold" if creat_alt else "text-slate-900 font-semibold",
        is_altered=creat_alt,
        main_var_symbol=creat_v_sym,
        main_var_delta=creat_v_delta,
        main_trend_symbol=creat_tr_sym,
        main_clinical_trend=creat_clin_tr,
        main_is_historical=creat_hist,
        main_fecha_origen=creat_date,
        main_footnote_symbol=ren_main_sym,
        subtitle_1=ren_subtitles[0] if len(ren_subtitles) > 0 else "",
        subtitle_2=ren_subtitles[1] if len(ren_subtitles) > 1 else "",
        subtitle_3=ren_subtitles[2] if len(ren_subtitles) > 2 else "",
        subtitles=ren_subtitles,
        filas=ren_filas,
        badge_text=renal_badge,
        badge_class=renal_badge_cls,
        trend_global=ren_t_state,
        trend_badge_text=ren_t_badge,
        trend_badge_class=ren_t_cls,
        notas_pie=ren_notas
    )

    # =========================================================================
    # 4. FUNCIÓN HEPÁTICA (ALT, AST, GGT, FA, Bilirrubina, Albúmina, TP/INR)
    # =========================================================================
    alt, alt_date, alt_hist = get_analyte_meta("GPT_ALT", "-")
    ast, ast_date, ast_hist = get_analyte_meta("GOT_AST", "-")
    ggt, ggt_date, ggt_hist = get_analyte_meta("GGT", "-")
    fa, fa_date, fa_hist = get_analyte_meta("FOSFATASA_ALCALINA", "-")
    bili, bili_date, bili_hist = get_analyte_meta("BILIRRUBINA_TOTAL", "-")
    alb, alb_date, alb_hist = get_analyte_meta("ALBUMINA", "-")
    inr, inr_date, inr_hist = get_analyte_meta("INR", "-")
    tp, tp_date, tp_hist = get_analyte_meta("TIEMPO_PROTROMBINA", "-")

    alt_num = parse_num(alt)
    ast_num = parse_num(ast)
    ggt_num = parse_num(ggt)
    fa_num = parse_num(fa)
    bili_num = parse_num(bili)
    alb_num = parse_num(alb)

    tp_num = parse_num(tp)
    inr_num = parse_num(inr)

    alt_alt = check_is_altered("GPT_ALT", alt, fallback_ref="< 55.0")
    ast_alt = check_is_altered("GOT_AST", ast, fallback_ref="< 45.0")
    ggt_alt = check_is_altered("GGT", ggt, fallback_ref="< 78.0")
    fa_alt = check_is_altered("FOSFATASA_ALCALINA", fa, fallback_ref="< 126.0")
    bili_alt = check_is_altered("BILIRRUBINA_TOTAL", bili, fallback_ref="< 1.2")
    alb_alt = check_is_altered("ALBUMINA", alb, fallback_ref="3.5 - 5.2")
    tp_alt = check_is_altered("TIEMPO_PROTROMBINA", tp, fallback_ref="10.0 - 14.5")
    inr_alt = check_is_altered("INR", inr, fallback_ref="0.8 - 1.2")

    hep_atencion = bool(
        (alt_num and alt_num >= 90.0)
        or (ast_num and ast_num >= 80.0)
        or (ggt_num and ggt_num >= 120.0)
        or (bili_num and bili_num >= 2.0)
        or (alb_num and alb_num < 3.0)
        or (inr_num and inr_num >= 1.5)
        or (tp_num and tp_num >= 16.0)
    )
    hep_seguimiento = bool(alt_alt or ast_alt or ggt_alt or fa_alt or bili_alt or alb_alt or tp_alt or inr_alt)
    hep_badge, hep_badge_cls, hep_tag, hep_tag_cls = get_clean_badge(hep_atencion, hep_seguimiento)

    main_hep_cod = "GPT_ALT" if alt != "-" else "GOT_AST"
    main_hep_val = alt if alt != "-" else ast
    main_hep_date = alt_date if alt != "-" else ast_date
    main_hep_hist = alt_hist if alt != "-" else ast_hist
    hep_v_sym, hep_v_delta, hep_tr_sym, hep_clin_tr = get_analyte_trend_info(main_hep_cod, main_hep_val)
    hep_filas = []
    hep_subtitles = []
    hep_evals = {main_hep_cod: hep_clin_tr}

    # Perfil hepático estándar
    f, l, c_tr = build_fila("GOT_AST", "GOT/AST", ast, "U/L", ast_alt, 0, es_historico=ast_hist, fecha_origen=ast_date, es_principal=True, tipo_parametro="principal")
    hep_filas.append(f); hep_subtitles.append(l); hep_evals["GOT_AST"] = c_tr

    f, l, c_tr = build_fila("GGT", "GGT", ggt, "U/L", ggt_alt, 0, es_historico=ggt_hist, fecha_origen=ggt_date, es_principal=False, tipo_parametro="secundario")
    hep_filas.append(f); hep_subtitles.append(l); hep_evals["GGT"] = c_tr

    f, l, c_tr = build_fila("FOSFATASA_ALCALINA", "Fosf. Alcalina", fa, "U/L", fa_alt, 0, es_historico=fa_hist, fecha_origen=fa_date, es_principal=False, tipo_parametro="secundario")
    hep_filas.append(f); hep_subtitles.append(l); hep_evals["FOSFATASA_ALCALINA"] = c_tr

    f, l, c_tr = build_fila("BILIRRUBINA_TOTAL", "Bilirrubina", bili, "mg/dL", bili_alt, 1, es_historico=bili_hist, fecha_origen=bili_date, es_principal=False, tipo_parametro="secundario")
    hep_filas.append(f); hep_subtitles.append(l); hep_evals["BILIRRUBINA_TOTAL"] = c_tr

    f, l, c_tr = build_fila("ALBUMINA", "Albúmina", alb, "g/dL", alb_alt, 1, es_historico=alb_hist, fecha_origen=alb_date, es_principal=False, tipo_parametro="secundario")
    hep_filas.append(f); hep_subtitles.append(l); hep_evals["ALBUMINA"] = c_tr

    f, l, c_tr = build_fila("TIEMPO_PROTROMBINA", "Tiempo Protrombina", tp, "s", tp_alt, 1, es_historico=tp_hist, fecha_origen=tp_date, es_principal=False, tipo_parametro="secundario")
    hep_filas.append(f); hep_subtitles.append(l); hep_evals["TIEMPO_PROTROMBINA"] = c_tr

    f, l, c_tr = build_fila("INR", "INR", inr, "", inr_alt, 2, es_historico=inr_hist, fecha_origen=inr_date, es_principal=False, tipo_parametro="secundario")
    hep_filas.append(f); hep_subtitles.append(l); hep_evals["INR"] = c_tr

    hep_main_sym, hep_notas = asignar_notas_pie_tarjeta(main_hep_hist, main_hep_date, hep_filas, ultimo_informe.fecha)
    hep_t_state, hep_t_badge, hep_t_cls = evaluar_tendencia_global_tarjeta(hep_evals, "funcion_hepatica")

    card_hepatica = KpiCard(
        id="funcion_hepatica",
        title="Función Hepática",
        tag=hep_tag,
        tag_class=hep_tag_cls,
        main_label="GPT / ALT",
        main_value=fmt(alt) if alt != "-" else fmt(ast),
        unit="U/L",
        main_value_class="text-rose-600 font-semibold" if (alt_alt if alt != "-" else ast_alt) else "text-slate-900 font-semibold",
        is_altered=(alt_alt if alt != "-" else ast_alt),
        main_var_symbol=hep_v_sym,
        main_var_delta=hep_v_delta,
        main_trend_symbol=hep_tr_sym,
        main_clinical_trend=hep_clin_tr,
        main_is_historical=main_hep_hist,
        main_fecha_origen=main_hep_date,
        main_footnote_symbol=hep_main_sym,
        subtitle_1=hep_subtitles[0] if len(hep_subtitles) > 0 else "",
        subtitle_2=hep_subtitles[1] if len(hep_subtitles) > 1 else "",
        subtitle_3=hep_subtitles[2] if len(hep_subtitles) > 2 else "",
        subtitles=hep_subtitles,
        filas=hep_filas,
        badge_text=hep_badge,
        badge_class=hep_badge_cls,
        trend_global=hep_t_state,
        trend_badge_text=hep_t_badge,
        trend_badge_class=hep_t_cls,
        notas_pie=hep_notas
    )

    # =========================================================================
    # 5. HEMOGRAMA / HIERRO (Hb, Hto, VCM, Leucocitos, Plaquetas, Ferritina...)
    # =========================================================================
    hb, hb_date, hb_hist = get_analyte_meta("HEMOGLOBINA", "-")
    hto, hto_date, hto_hist = get_analyte_meta("HEMATOCRITO", "-")
    vcm, vcm_date, vcm_hist = get_analyte_meta("VCM", "-")
    leuc, leuc_date, leuc_hist = get_analyte_meta("LEUCOCITOS", "-")
    plaq, plaq_date, plaq_hist = get_analyte_meta("PLAQUETAS", "-")
    ferr, ferr_date, ferr_hist = get_analyte_meta("FERRITINA", "-")
    hierro, hierro_date, hierro_hist = get_analyte_meta("HIERRO", "-")

    hb_num = parse_num(hb)
    hto_num = parse_num(hto)
    vcm_num = parse_num(vcm)
    leuc_num = parse_num(leuc)
    plaq_num = parse_num(plaq)
    ferr_num = parse_num(ferr)
    hierro_num = parse_num(hierro)

    hb_alt = check_is_altered("HEMOGLOBINA", hb, fallback_ref="13.0 - 18.0")
    hto_alt = check_is_altered("HEMATOCRITO", hto, fallback_ref="40.0 - 52.0")
    vcm_alt = check_is_altered("VCM", vcm, fallback_ref="80.0 - 100.0")
    leuc_alt = check_is_altered("LEUCOCITOS", leuc, fallback_ref="4.0 - 11.0")
    plaq_alt = check_is_altered("PLAQUETAS", plaq, fallback_ref="140.0 - 450.0")
    ferr_alt = check_is_altered("FERRITINA", ferr, fallback_ref="30.0 - 300.0")
    hierro_alt = check_is_altered("HIERRO", hierro, fallback_ref="59.0 - 160.0")

    hemo_atencion = bool((hb_num and (hb_num < 11.5 or hb_num > 18.5)) or (plaq_num and (plaq_num < 100 or plaq_num > 600)) or (leuc_num and (leuc_num < 3.0 or leuc_num > 14.0)))
    hemo_seguimiento = bool(hb_alt or hto_alt or vcm_alt or leuc_alt or plaq_alt or ferr_alt or hierro_alt)
    hemo_badge, hemo_badge_cls, hemo_tag, hemo_tag_cls = get_clean_badge(hemo_atencion, hemo_seguimiento)

    hb_v_sym, hb_v_delta, hb_tr_sym, hb_clin_tr = get_analyte_trend_info("HEMOGLOBINA", hb)
    hemo_filas = []
    hemo_subtitles = []
    hemo_evals = {"HEMOGLOBINA": hb_clin_tr}

    # Parámetros corpusculares y leucocitarios básicos del hemograma
    f, l, c_tr = build_fila("HEMATOCRITO", "Hto", hto, "%", hto_alt, 1, es_historico=hto_hist, fecha_origen=hto_date, es_principal=True, tipo_parametro="principal")
    hemo_filas.append(f); hemo_subtitles.append(l); hemo_evals["HEMATOCRITO"] = c_tr

    f, l, c_tr = build_fila("VCM", "VCM", vcm, "fL", vcm_alt, 1, es_historico=vcm_hist, fecha_origen=vcm_date, es_principal=False, tipo_parametro="secundario")
    hemo_filas.append(f); hemo_subtitles.append(l); hemo_evals["VCM"] = c_tr

    f, l, c_tr = build_fila("LEUCOCITOS", "Leucos", leuc, "mil/µL", leuc_alt, 2, es_historico=leuc_hist, fecha_origen=leuc_date, es_principal=False, tipo_parametro="secundario")
    hemo_filas.append(f); hemo_subtitles.append(l); hemo_evals["LEUCOCITOS"] = c_tr

    f, l, c_tr = build_fila("PLAQUETAS", "Plaquetas", plaq, "mil/µL", plaq_alt, 0, es_historico=plaq_hist, fecha_origen=plaq_date, es_principal=False, tipo_parametro="secundario")
    hemo_filas.append(f); hemo_subtitles.append(l); hemo_evals["PLAQUETAS"] = c_tr
    if ferr != "-":
        f, l, c_tr = build_fila("FERRITINA", "Ferritina", ferr, "ng/mL", ferr_alt, 0, es_historico=ferr_hist, fecha_origen=ferr_date, es_principal=True, tipo_parametro="principal")
        hemo_filas.append(f); hemo_subtitles.append(l); hemo_evals["FERRITINA"] = c_tr
    if hierro != "-":
        f, l, c_tr = build_fila("HIERRO", "Hierro", hierro, "µg/dL", hierro_alt, 0, es_historico=hierro_hist, fecha_origen=hierro_date, es_principal=False, tipo_parametro="secundario")
        hemo_filas.append(f); hemo_subtitles.append(l); hemo_evals["HIERRO"] = c_tr

    hemo_main_sym, hemo_notas = asignar_notas_pie_tarjeta(hb_hist, hb_date, hemo_filas, ultimo_informe.fecha)
    hemo_t_state, hemo_t_badge, hemo_t_cls = evaluar_tendencia_global_tarjeta(hemo_evals, "hemograma_hierro")

    card_hemograma = KpiCard(
        id="hemograma_hierro",
        title="Hemograma / Hierro",
        tag=hemo_tag,
        tag_class=hemo_tag_cls,
        main_label="Hemoglobina (Hb)",
        main_value=fmt(hb, 1),
        unit="g/dL",
        main_value_class="text-rose-600 font-semibold" if hb_alt else "text-slate-900 font-semibold",
        is_altered=hb_alt,
        main_var_symbol=hb_v_sym,
        main_var_delta=hb_v_delta,
        main_trend_symbol=hb_tr_sym,
        main_clinical_trend=hb_clin_tr,
        main_is_historical=hb_hist,
        main_fecha_origen=hb_date,
        main_footnote_symbol=hemo_main_sym,
        subtitle_1=hemo_subtitles[0] if len(hemo_subtitles) > 0 else "",
        subtitle_2=hemo_subtitles[1] if len(hemo_subtitles) > 1 else "",
        subtitle_3=hemo_subtitles[2] if len(hemo_subtitles) > 2 else "",
        subtitles=hemo_subtitles,
        filas=hemo_filas,
        badge_text=hemo_badge,
        badge_class=hemo_badge_cls,
        trend_global=hemo_t_state,
        trend_badge_text=hemo_t_badge,
        trend_badge_class=hemo_t_cls,
        notas_pie=hemo_notas
    )

    # =========================================================================
    # 6. TIROIDES (TSH, T4L, T4T, T3T, T3L)
    # =========================================================================
    tsh, tsh_date, tsh_hist = get_analyte_meta("TSH", "-")
    t4l, t4l_date, t4l_hist = get_analyte_meta("T4_LIBRE", "-")
    t4t, t4t_date, t4t_hist = get_analyte_meta("T4_TOTAL", "-")
    t3t, t3t_date, t3t_hist = get_analyte_meta("T3_TOTAL", "-")
    t3l, t3l_date, t3l_hist = get_analyte_meta("T3_LIBRE", "-")
    anti_tpo, anti_tpo_date, anti_tpo_hist = get_analyte_meta("ANTI_TPO", "-")
    anti_tg, anti_tg_date, anti_tg_hist = get_analyte_meta("ANTI_TG", "-")
    trab, trab_date, trab_hist = get_analyte_meta("TRAB", "-")

    tsh_num = parse_num(tsh)
    t4l_num = parse_num(t4l)
    t4t_num = parse_num(t4t)
    t3t_num = parse_num(t3t)
    t3l_num = parse_num(t3l)

    tsh_alt = check_is_altered("TSH", tsh, fallback_ref="0.27 - 4.29")
    t4l_alt = check_is_altered("T4_LIBRE", t4l, fallback_ref="0.71 - 1.85")
    t4t_alt = check_is_altered("T4_TOTAL", t4t, fallback_ref="5.1 - 14.1") if t4t != "-" else False
    t3t_alt = check_is_altered("T3_TOTAL", t3t, fallback_ref="0.80 - 2.00") if t3t != "-" else False
    t3l_alt = check_is_altered("T3_LIBRE", t3l, fallback_ref="2.0 - 4.4")

    # TSH, T4 total y T4 libre son los analitos principales que determinan el estado funcional del tiroides.
    # T3 total, T3 libre y anticuerpos tienen carácter secundario o complementario.
    t4_anormal = bool(t4l_alt or t4t_alt)
    tsh_atencion = bool(
        (tsh_num and (tsh_num >= 10.0 or tsh_num <= 0.1))
        or (tsh_alt and t4_anormal and (tsh_num and (tsh_num >= 5.0 or tsh_num <= 0.2)))
    )
    tsh_seguimiento = bool(tsh_alt or t4_anormal)
    tsh_badge, tsh_badge_cls, tsh_tag, tsh_tag_cls = get_clean_badge(tsh_atencion, tsh_seguimiento)

    tsh_v_sym, tsh_v_delta, tsh_tr_sym, tsh_clin_tr = get_analyte_trend_info("TSH", tsh)
    tsh_filas = []
    tsh_subtitles = []
    tsh_evals = {"TSH": tsh_clin_tr}

    # 1. T4 Total (parámetro principal solicitado por especialistas)
    if t4t != "-":
        f, l, c_tr = build_fila("T4_TOTAL", "T4 Total", t4t, "µg/dL", t4t_alt, 2, es_historico=t4t_hist, fecha_origen=t4t_date, es_principal=True, tipo_parametro="principal")
        tsh_filas.append(f); tsh_subtitles.append(l); tsh_evals["T4_TOTAL"] = c_tr

    # 2. T4 Libre (parámetro principal acompañante de TSH)
    if t4l != "-" or t4t == "-":
        f, l, c_tr = build_fila("T4_LIBRE", "T4 Libre", t4l, "ng/dL", t4l_alt, 2, es_historico=t4l_hist, fecha_origen=t4l_date, es_principal=True, tipo_parametro="principal")
        tsh_filas.append(f); tsh_subtitles.append(l); tsh_evals["T4_LIBRE"] = c_tr
        t4l_tr_sym = f.trend_symbol
        t4l_clin_tr = c_tr
    else:
        t4l_tr_sym = None
        t4l_clin_tr = None

    # 3. T3 Total (parámetro solicitado por especialistas)
    if t3t != "-":
        f, l, c_tr = build_fila("T3_TOTAL", "T3 Total", t3t, "ng/mL", t3t_alt, 2, es_historico=t3t_hist, fecha_origen=t3t_date, es_principal=False, tipo_parametro="secundario")
        tsh_filas.append(f); tsh_subtitles.append(l); tsh_evals["T3_TOTAL"] = c_tr

    # 4. T3 Libre (analito secundario complementario)
    if t3l != "-" or t3t == "-":
        f, l, c_tr = build_fila("T3_LIBRE", "T3 Libre", t3l, "pg/mL", t3l_alt, 2, es_historico=t3l_hist, fecha_origen=t3l_date, es_principal=False, tipo_parametro="secundario")
        tsh_filas.append(f); tsh_subtitles.append(l); tsh_evals["T3_LIBRE"] = c_tr
        t3l_tr_sym = f.trend_symbol
        t3l_clin_tr = c_tr
    else:
        t3l_tr_sym = None
        t3l_clin_tr = None

    # Determinaciones complementarias: Anticuerpos anti-TPO y Anticuerpos antirreceptor de TSH (TRAb)
    anti_tpo_alt = check_is_altered("ANTI_TPO", anti_tpo, fallback_ref="< 34.0") if anti_tpo != "-" else False
    f, l, c_tr = build_fila("ANTI_TPO", "Anticuerpos anti-TPO", anti_tpo, "UI/mL", anti_tpo_alt, 1, es_historico=anti_tpo_hist, fecha_origen=anti_tpo_date, es_principal=False, tipo_parametro="complementario")
    tsh_filas.append(f); tsh_subtitles.append(l); tsh_evals["ANTI_TPO"] = c_tr

    trab_alt = check_is_altered("TRAB", trab, fallback_ref="< 1.75") if trab != "-" else False
    f, l, c_tr = build_fila("TRAB", "Anticuerpos antirreceptor de TSH (TRAb)", trab, "UI/L", trab_alt, 2, es_historico=trab_hist, fecha_origen=trab_date, es_principal=False, tipo_parametro="complementario")
    tsh_filas.append(f); tsh_subtitles.append(l); tsh_evals["TRAB"] = c_tr

    if anti_tg != "-":
        anti_tg_alt = check_is_altered("ANTI_TG", anti_tg, fallback_ref="< 115.0")
        f, l, c_tr = build_fila("ANTI_TG", "Anticuerpos anti-TG", anti_tg, "UI/mL", anti_tg_alt, 1, es_historico=anti_tg_hist, fecha_origen=anti_tg_date, es_principal=False, tipo_parametro="complementario")
        tsh_filas.append(f); tsh_subtitles.append(l); tsh_evals["ANTI_TG"] = c_tr

    tsh_main_sym, tsh_notas = asignar_notas_pie_tarjeta(tsh_hist, tsh_date, tsh_filas, ultimo_informe.fecha)
    tsh_context = {
        "tsh_num": tsh_num,
        "tsh_sym": tsh_tr_sym,
        "tsh_clin": tsh_clin_tr,
        "tsh_alt": tsh_alt,
        "t4l_num": t4l_num,
        "t4l_sym": t4l_tr_sym,
        "t4l_clin": t4l_clin_tr,
        "t4l_alt": t4l_alt,
        "t3l_num": t3l_num,
        "t3l_sym": t3l_tr_sym,
        "t3l_clin": t3l_clin_tr,
        "t3l_alt": t3l_alt
    }
    tsh_t_state, tsh_t_badge, tsh_t_cls = evaluar_tendencia_global_tarjeta(tsh_evals, "tiroides", contexto_clinico=tsh_context)

    card_tiroides = KpiCard(
        id="tiroides",
        title="Función Tiroidea",
        tag=tsh_tag,
        tag_class=tsh_tag_cls,
        main_label="Hormona TSH",
        main_value=fmt(tsh, 2),
        unit="µUI/mL",
        main_value_class="text-rose-600 font-semibold" if tsh_alt else "text-slate-900 font-semibold",
        is_altered=tsh_alt,
        main_var_symbol=tsh_v_sym,
        main_var_delta=tsh_v_delta,
        main_trend_symbol=tsh_tr_sym,
        main_clinical_trend=tsh_clin_tr,
        main_is_historical=tsh_hist,
        main_fecha_origen=tsh_date,
        main_footnote_symbol=tsh_main_sym,
        subtitle_1=tsh_subtitles[0] if len(tsh_subtitles) > 0 else "",
        subtitle_2=tsh_subtitles[1] if len(tsh_subtitles) > 1 else "",
        subtitle_3=tsh_subtitles[2] if len(tsh_subtitles) > 2 else "",
        subtitles=tsh_subtitles,
        filas=tsh_filas,
        badge_text=tsh_badge,
        badge_class=tsh_badge_cls,
        trend_global=tsh_t_state,
        trend_badge_text=tsh_t_badge,
        trend_badge_class=tsh_t_cls,
        notas_pie=tsh_notas
    )

    kpis = [card_metabolismo, card_lipidos, card_renal, card_hepatica, card_hemograma, card_tiroides]

    # =========================================================================
    # OTROS VALORES DE INTERÉS (SECCIONES DINÁMICAS A ANCHO COMPLETO)
    # =========================================================================
    otros_valores: List[OtrosValoresSeccion] = []

    # A) PRÓSTATA: Solo varones con determinación de PSA
    sexo_p = (paciente.sexo or "").strip().lower() if paciente else ""
    es_varon = sexo_p in ["masculino", "varon", "varón", "hombre", "m"] or (sexo_p not in ["femenino", "mujer", "f"])
    psa_t = get_v("PSA_TOTAL", "-")
    psa_f = get_v("PSA_FREE", "-")

    if es_varon and (psa_t != "-" or psa_f != "-"):
        psa_num = parse_num(psa_t)
        psa_f_num = parse_num(psa_f)
        ratio_psa_calc = None
        if psa_num and psa_f_num and psa_num > 0:
            ratio_psa_calc = round((psa_f_num / psa_num) * 100)
        else:
            r_psa_stored = get_v("RATIO_PSA_L_T", "-")
            if r_psa_stored != "-":
                ratio_psa_calc = round(parse_num(r_psa_stored) * (100 if parse_num(r_psa_stored) < 1 else 1))

        psa_alt = check_is_altered("PSA_TOTAL", psa_t, fallback_ref="< 4.0")
        psa_seg = bool(psa_num and psa_num > 2.5) or (ratio_psa_calc is not None and ratio_psa_calc < 20)
        psa_b_text, psa_b_cls, _, _ = get_clean_badge(psa_alt, psa_seg)

        p_items = []
        if psa_t != "-":
            p_items.append(MetricaSimple(label="PSA Total", val=fmt(psa_t, 2), unit="ng/mL", is_altered=psa_alt or psa_seg))
        if psa_f != "-":
            p_items.append(MetricaSimple(label="PSA Libre", val=fmt(psa_f, 2), unit="ng/mL", is_altered=check_is_altered("PSA_FREE", psa_f)))
        if ratio_psa_calc is not None:
            p_items.append(MetricaSimple(label="Ratio PSA Libre / Total", val=f"{ratio_psa_calc}%", unit="%", is_altered=(ratio_psa_calc < 20)))

        otros_valores.append(OtrosValoresSeccion(
            id="prostata",
            titulo="Salud Prostática (Urología)",
            icono="🩺",
            badge_text=psa_b_text,
            badge_class=psa_b_cls,
            items=p_items,
            nota=""
        ))

    # B) VITAMINA D / METABOLISMO ÓSEO (25-OH Vitamina D, Calcio, Fósforo, PTH)
    vitd = get_v("VITAMIN_D", "-")
    calcio = get_v("CALCIO_TOTAL", "-")
    fosforo = get_v("FOSFORO", "-")
    pth = get_v("PTH_INTACTA", "-")

    if vitd != "-" or calcio != "-" or fosforo != "-" or pth != "-":
        vitd_num = parse_num(vitd)
        ca_num = parse_num(calcio)
        p_num = parse_num(fosforo)
        pth_num = parse_num(pth)

        vitd_def = bool(vitd_num and vitd_num < 15.0)
        vitd_ins = check_is_altered("VITAMIN_D", vitd, fallback_ref="> 30.0")
        ca_alt = check_is_altered("CALCIO_TOTAL", calcio, fallback_ref="8.2 - 10.6")
        p_alt = check_is_altered("FOSFORO", fosforo, fallback_ref="2.5 - 5.0")
        pth_alt = check_is_altered("PTH_INTACTA", pth, fallback_ref="14.5 - 87.1")

        vitd_atencion = vitd_def or (ca_num and (ca_num < 7.5 or ca_num > 11.5))
        vitd_seguimiento = vitd_ins or ca_alt or p_alt or pth_alt
        vitd_b_text, vitd_b_cls, _, _ = get_clean_badge(vitd_atencion, vitd_seguimiento)

        v_items = []
        if vitd != "-":
            v_items.append(MetricaSimple(label="25-OH Vitamina D", val=fmt(vitd, 1), unit="ng/mL", is_altered=vitd_ins))
        if calcio != "-":
            v_items.append(MetricaSimple(label="Calcio Total", val=fmt(calcio, 1), unit="mg/dL", is_altered=ca_alt))
        if fosforo != "-":
            v_items.append(MetricaSimple(label="Fósforo", val=fmt(fosforo, 1), unit="mg/dL", is_altered=p_alt))
        if pth != "-":
            v_items.append(MetricaSimple(label="PTH Intacta", val=fmt(pth, 1), unit="pg/mL", is_altered=pth_alt))

        otros_valores.append(OtrosValoresSeccion(
            id="metabolismo_oseo",
            titulo="Vitamina D y Metabolismo Óseo",
            icono="☀️",
            badge_text=vitd_b_text,
            badge_class=vitd_b_cls,
            items=v_items,
            nota=""
        ))

    # C) INFLAMACIÓN / AUTOINMUNIDAD (PCR, VSG, Factor Reumatoide, Anti-CCP, ANA)
    pcr = get_v("PROTEINA_C_REACTIVA", "-")
    vsg = get_v("VSG_1H", "-")
    fr = get_v("FACTOR_REUMATOIDE", "-")
    anti_ccp = get_v("ANTI_CCP", "-")
    ana = get_v("ANA", "-")

    if pcr != "-" or vsg != "-" or fr != "-" or anti_ccp != "-" or ana != "-":
        pcr_num = parse_num(pcr)
        vsg_num = parse_num(vsg)
        fr_num = parse_num(fr)
        anti_ccp_num = parse_num(anti_ccp)

        pcr_alt = check_is_altered("PROTEINA_C_REACTIVA", pcr, fallback_ref="< 0.5")
        vsg_alt = check_is_altered("VSG_1H", vsg, fallback_ref="< 10")
        fr_alt = check_is_altered("FACTOR_REUMATOIDE", fr, fallback_ref="< 30")
        anti_ccp_alt = check_is_altered("ANTI_CCP", anti_ccp, fallback_ref="< 7.0")
        ana_alt = check_is_altered("ANA", ana)

        inf_atencion = bool((pcr_num and pcr_num >= 2.0) or (anti_ccp_num and anti_ccp_num >= 10.0) or ana_alt)
        inf_seguimiento = pcr_alt or vsg_alt or fr_alt or anti_ccp_alt or ana_alt
        inf_b_text, inf_b_cls, _, _ = get_clean_badge(inf_atencion, inf_seguimiento)

        inf_items = []
        if pcr != "-":
            inf_items.append(MetricaSimple(label="Proteína C Reactiva (PCR)", val=fmt(pcr, 2), unit="mg/dL", is_altered=pcr_alt))
        if vsg != "-":
            inf_items.append(MetricaSimple(label="VSG 1ª Hora", val=fmt(vsg), unit="mm", is_altered=vsg_alt))
        if fr != "-":
            inf_items.append(MetricaSimple(label="Factor Reumatoide", val=fmt(fr), unit="UI/mL", is_altered=fr_alt))
        if anti_ccp != "-":
            inf_items.append(MetricaSimple(label="Anticuerpos Anti-CCP", val=fmt(anti_ccp, 1), unit="UI/mL", is_altered=anti_ccp_alt))
        if ana != "-":
            inf_items.append(MetricaSimple(label="Anticuerpos Anti-Nucleares (ANA)", val=str(ana), unit="", is_altered=ana_alt))

        otros_valores.append(OtrosValoresSeccion(
            id="inflamacion",
            titulo="Marcadores Inflamatorios y Autoinmunidad",
            icono="🛡️",
            badge_text=inf_b_text,
            badge_class=inf_b_cls,
            items=inf_items,
            nota=""
        ))

    # D) VITAMINAS Y MICRONUTRIENTES (B12, Folato)
    b12 = get_v("VITAMINA_B12", "-")
    fol = get_v("ACIDO_FOLICO", "-")

    if b12 != "-" or fol != "-":
        b12_num = parse_num(b12)
        fol_num = parse_num(fol)

        b12_alt = check_is_altered("VITAMINA_B12", b12, fallback_ref="> 200")
        fol_alt = check_is_altered("ACIDO_FOLICO", fol, fallback_ref="> 4.0")

        vit_seguimiento = b12_alt or fol_alt
        vit_b_text, vit_b_cls, _, _ = get_clean_badge(False, vit_seguimiento)

        vit_items = []
        if b12 != "-":
            vit_items.append(MetricaSimple(label="Vitamina B12", val=fmt(b12), unit="pg/mL", is_altered=b12_alt))
        if fol != "-":
            vit_items.append(MetricaSimple(label="Ácido Fólico", val=fmt(fol, 1), unit="ng/mL", is_altered=fol_alt))

        otros_valores.append(OtrosValoresSeccion(
            id="vitaminas",
            titulo="Vitaminas y Micronutrientes",
            icono="💊",
            badge_text=vit_b_text,
            badge_class=vit_b_cls,
            items=vit_items,
            nota=""
        ))

    # E) OTROS MARCADORES (ej. Tumorales si constan)
    cea = get_v("CEA", "-")
    ca19 = get_v("CA_19_9", "-")
    ca125 = get_v("CA_125_II", "-")

    if cea != "-" or ca19 != "-" or ca125 != "-":
        cea_num = parse_num(cea)
        ca19_num = parse_num(ca19)
        ca125_num = parse_num(ca125)

        cea_alt = check_is_altered("CEA", cea, fallback_ref="< 5.0")
        ca19_alt = check_is_altered("CA_19_9", ca19, fallback_ref="< 34.0")
        ca125_alt = check_is_altered("CA_125_II", ca125, fallback_ref="< 35.0")

        tm_items = []
        if cea != "-":
            tm_items.append(MetricaSimple(label="CEA", val=fmt(cea, 1), unit="ng/mL", is_altered=cea_alt))
        if ca19 != "-":
            tm_items.append(MetricaSimple(label="CA 19-9", val=fmt(ca19, 1), unit="UI/mL", is_altered=ca19_alt))
        if ca125 != "-":
            tm_items.append(MetricaSimple(label="CA 125 II", val=fmt(ca125, 1), unit="UI/mL", is_altered=ca125_alt))

        tm_b_text, tm_b_cls, _, _ = get_clean_badge(False, cea_alt or ca19_alt or ca125_alt)

        otros_valores.append(OtrosValoresSeccion(
            id="otros_marcadores",
            titulo="Otros Marcadores Especiales",
            icono="🔬",
            badge_text=tm_b_text,
            badge_class=tm_b_cls,
            items=tm_items,
            nota=""
        ))

    return DashboardSummaryResponse(
        paciente={
            "nombre": (paciente.nombre_completo if paciente and paciente.nombre_completo else "").strip(),
            "nacimiento": (paciente.fecha_nacimiento if paciente and paciente.fecha_nacimiento else "-"),
            "edad": calcular_edad(paciente.fecha_nacimiento) if paciente and paciente.fecha_nacimiento else "-",
            "dni": (paciente.dni if paciente and paciente.dni else "-"),
            "sexo": (paciente.sexo if paciente and paciente.sexo else "No especificado")
        },
        total_controles=total_controles,
        periodo_historico=periodo,
        ultima_fecha=ultima_fecha,
        dictamen_global=ultimo_informe.dictamen_global or "Favorable",
        dictamen_subtitulo=ultimo_informe.observaciones_ia or "Parámetros analizados por el sistema",
        kpis=kpis,
        otros_valores=otros_valores,
        motor_llm_info=motor_info,
        app_version=__version__
    )

@router.get("/paciente", response_model=PacienteInfo)
def get_paciente(db: Session = Depends(get_db)):
    """
    Obtiene los datos del paciente registrado en la aplicación.
    """
    paciente = db.query(Paciente).first()
    if not paciente:
        return PacienteInfo(
            id=None,
            nombre_completo="",
            fecha_nacimiento=None,
            dni=None,
            sexo="No especificado",
            edad="-"
        )
    return PacienteInfo(
        id=paciente.id,
        nombre_completo=paciente.nombre_completo or "",
        fecha_nacimiento=paciente.fecha_nacimiento,
        dni=paciente.dni,
        sexo=paciente.sexo if paciente.sexo in ["Masculino", "Femenino"] else "No especificado",
        edad=calcular_edad(paciente.fecha_nacimiento)
    )

@router.put("/paciente", response_model=PacienteInfo)
def update_paciente(payload: PacienteUpdateRequest, db: Session = Depends(get_db)):
    """
    Actualiza la ficha de datos personales del paciente.
    """
    paciente = db.query(Paciente).first()
    if not paciente:
        paciente = Paciente(
            nombre_completo=(payload.nombre_completo or "").strip()
        )
        db.add(paciente)

    paciente.nombre_completo = (payload.nombre_completo or "").strip()
    paciente.fecha_nacimiento = payload.fecha_nacimiento.strip() if payload.fecha_nacimiento else None
    paciente.dni = payload.dni.strip() if payload.dni else None
    paciente.sexo = payload.sexo.strip() if payload.sexo in ["Masculino", "Femenino"] else "No especificado"

    db.commit()
    db.refresh(paciente)

    return PacienteInfo(
        id=paciente.id,
        nombre_completo=paciente.nombre_completo or "",
        fecha_nacimiento=paciente.fecha_nacimiento,
        dni=paciente.dni,
        sexo=paciente.sexo or "No especificado",
        edad=calcular_edad(paciente.fecha_nacimiento)
    )

@router.get("/tables", response_model=TablesResponse)
def get_tables(db: Session = Depends(get_db)):
    """
    Devuelve los datos estructurados para las tablas de Bioquímica,
    Hemograma, Coagulación y Enzimas e Iones.
    """
    informes = db.query(Informe).order_by(Informe.fecha.asc()).all()
    dates = [inf.etiqueta_corta for inf in informes]
    informe_ids = [inf.id for inf in informes]
    
    # Identificar índices de los controles dentro de los últimos 18 meses (respecto a la última analítica)
    recent_indices = []
    if informes:
        try:
            from datetime import datetime, timedelta
            ultima_fecha_dt = datetime.strptime(informes[-1].fecha, "%Y-%m-%d").date()
            cutoff_18m = ultima_fecha_dt - timedelta(days=548)  # ~18 meses
            recent_indices = [
                idx for idx, inf in enumerate(informes)
                if datetime.strptime(inf.fecha, "%Y-%m-%d").date() >= cutoff_18m
            ]
        except Exception:
            recent_indices = [idx for idx, inf in enumerate(informes) if idx >= max(0, len(informes) - 3)]
    if not recent_indices and informes:
        recent_indices = [len(informes) - 1]

    analitos = db.query(Analito).order_by(Analito.orden.asc(), Analito.id.asc()).all()
    
    bio_rows = []
    for a in analitos:
        meds = db.query(Medicion).filter_by(analito_id=a.id).all()
        if not meds:
            continue
        med_obj_by_inf = {m.informe_id: m for m in meds}
        
        vals = []
        cells = []
        for inf_id in informe_ids:
            if inf_id in med_obj_by_inf:
                m = med_obj_by_inf[inf_id]
                v = m.valor_numerico if m.valor_numerico is not None else m.valor_texto
                r = (m.ref_texto or a.ref_texto_defecto or "").strip()
                eval_st = evaluar_estado_semaforo(m.valor_numerico, r) if m.valor_numerico is not None else "Normal"
                if eval_st in ["Alto", "Bajo"]:
                    st = eval_st
                elif m.estado_semaforo and m.estado_semaforo != "Normal":
                    st = m.estado_semaforo
                else:
                    st = eval_st
                is_alt = st in ["Alto", "Bajo", "Atencion", "Alerta", "Alérgeno"]
                vals.append(v)
                cells.append(TableCell(val=v, ref=r, status=st, is_altered=is_alt))
            else:
                vals.append(None)
                cells.append(TableCell(val=None, ref="", status="Normal", is_altered=False))
        
        # Calcular promedio reciente (últimos 18 meses)
        recent_vals = [vals[i] for i in recent_indices if i < len(vals)]
        num_vals_recent = [v for v in recent_vals if isinstance(v, (int, float))]
        avg_recent = f"{sum(num_vals_recent) / len(num_vals_recent):.1f}" if num_vals_recent else "-"
        
        # Ajustes de decimales específicos
        if a.codigo in ["CREATININE", "TSH", "PSA_TOTAL", "PSA_FREE", "RATIO_PSA_L_T", "RATIO_COL_HDL", "RATIO_LDL_HDL", "RATIO_TG_HDL"]:
            if num_vals_recent:
                avg_recent = f"{sum(num_vals_recent) / len(num_vals_recent):.2f}"

        bio_rows.append(TableRow(
            name=a.nombre_visible,
            unit=a.unidad_estandar,
            ref=a.ref_texto_defecto or "",
            vals=vals,
            cells=cells,
            recentAvg=avg_recent,
            avg=avg_recent,
            group=get_analito_group(a.codigo)
        ))

    # Si eGFR no vino explícito del laboratorio en ninguna analítica, generar la fila calculada
    if not any(r.name in ["Filtrado Glomerular (eGFR)", "eGFR"] for r in bio_rows):
        creat_row = next((r for r in bio_rows if r.name == "Creatinina"), None)
        if creat_row and any(v is not None for v in creat_row.vals):
            paciente = db.query(Paciente).first()
            sexo_p = paciente.sexo if paciente else "Masculino"
            fn_d = parse_date_safe(paciente.fecha_nacimiento) if paciente and paciente.fecha_nacimiento else None

            egfr_vals = []
            egfr_cells = []
            for idx, inf in enumerate(informes):
                c_val = creat_row.vals[idx] if idx < len(creat_row.vals) else None
                if c_val is not None:
                    inf_d = parse_date_safe(inf.fecha)
                    edad_inf = 50
                    if fn_d and inf_d:
                        edad_inf = inf_d.year - fn_d.year - ((inf_d.month, inf_d.day) < (fn_d.month, fn_d.day))
                    egfr_calc = calcular_egfr(float(c_val), edad_inf, sexo_p)
                    if egfr_calc is not None:
                        is_alt = egfr_calc < 60.0
                        st = "Bajo" if is_alt else "Normal"
                        egfr_vals.append(egfr_calc)
                        egfr_cells.append(TableCell(val=egfr_calc, ref="> 60 mL/min/1.73m²", status=st, is_altered=is_alt))
                    else:
                        egfr_vals.append(None)
                        egfr_cells.append(TableCell(val=None, ref="", status="Normal", is_altered=False))
                else:
                    egfr_vals.append(None)
                    egfr_cells.append(TableCell(val=None, ref="", status="Normal", is_altered=False))

            recent_egfr = [egfr_vals[i] for i in recent_indices if i < len(egfr_vals) and egfr_vals[i] is not None]
            avg_recent_egfr = f"{sum(recent_egfr) / len(recent_egfr):.1f}" if recent_egfr else "-"

            egfr_table_row = TableRow(
                name="Filtrado Glomerular (eGFR)",
                unit="mL/min/1.73m²",
                ref="> 60 mL/min/1.73m²",
                vals=egfr_vals,
                cells=egfr_cells,
                recentAvg=avg_recent_egfr,
                avg=avg_recent_egfr,
                group="🧪 Función Renal y Depuración"
            )
            creat_idx = bio_rows.index(creat_row)
            bio_rows.insert(creat_idx + 1, egfr_table_row)

    # Paneles de muestra para demostración
    hem_data = [
        ['Hematíes', '10^6/µL', '4.80', '4.85', '4.78', '4.90', '4.82', '4.81', '4.83', '4.82', '4.00 - 5.65', 'Normal'],
        ['Hemoglobina', 'g/dL', '15.2', '15.4', '15.0', '15.3', '15.1', '15.2', '15.3', '15.2', '12.5 - 17.2', 'Óptimo (Normal)'],
        ['Hematocrito', '%', '45.0', '44.8', '45.2', '44.5', '45.1', '44.9', '45.0', '45.0', '37.0 - 49.0', 'Normal'],
        ['Plaquetas', '10^3/µL', '240', '245', '238', '242', '240', '241', '240', '241', '140 - 370', 'Óptimo'],
        ['Leucocitos', '10^3/µL', '5.10', '5.20', '4.90', '5.15', '5.05', '5.08', '5.10', '5.08', '3.60 - 10.50', 'Normal']
    ]

    coag_data = [
        ['Tiempo de Protrombina', 'segundos', '11.5', '11.8', '11.2', '11.4', '11.5', '11.5', '11.5', '11.5', '10.0 - 14.5', 'Normal'],
        ['Índice de Quick', '%', '105', '102', '108', '100', '104', '103', '104', '104', '70 - 130 %', 'Normocoagulado'],
        ['INR', 'ratio', '0.95', '0.98', '0.94', '0.97', '0.96', '0.96', '0.96', '0.96', '0.85 - 1.15', 'Óptimo']
    ]

    enz_data = [
        ['GOT / AST', 'U/L', '22', '24', '20', '23', '21', '22', '22', '22', 'Inf. 40', 'Óptimo'],
        ['GPT / ALT', 'U/L', '21', '23', '19', '22', '20', '21', '21', '21', '10 - 49', 'Óptimo'],
        ['GGT', 'U/L', '18', '16', '17', '15', '16', '16', '16', '16', 'Inf. 60', 'Excelente'],
        ['TSH (Tiroides)', 'µUI/mL', '1.45', '1.80', '1.65', '2.10', '2.20', '1.84', '1.84', '1.84', '0.27 - 4.29', 'Óptimo (Eutiroideo)']
    ]

    informes_meta = [
        {
            "id": inf.id,
            "fecha": inf.fecha,
            "etiqueta_corta": inf.etiqueta_corta,
            "laboratorio": inf.laboratorio or "Desconocido",
            "referencia": inf.referencia or ""
        }
        for inf in informes
    ]

    return TablesResponse(
        dates=dates,
        informes=informes_meta,
        bioquimica=bio_rows,
        hemograma=hem_data,
        coagulacion=coag_data,
        enzimas=enz_data
    )

@router.get("/charts", response_model=ChartsResponse)
def get_charts_data(db: Session = Depends(get_db)):
    """
    Devuelve los datasets para Chart.js configurados para los 8 gráficos visuales.
    """
    informes = db.query(Informe).order_by(Informe.fecha.asc()).all()
    dates = [inf.etiqueta_corta for inf in informes]
    informe_ids = [inf.id for inf in informes]

    def get_series(*codigos: str):
        analitos = db.query(Analito).filter(Analito.codigo.in_(codigos)).all()
        if not analitos:
            return [None] * len(informe_ids)
        a_ids = [a.id for a in analitos]
        meds = db.query(Medicion).filter(Medicion.analito_id.in_(a_ids)).all()
        med_map = {}
        for m in meds:
            if m.valor_numerico is not None:
                med_map[m.informe_id] = m.valor_numerico
        return [med_map.get(i_id, None) for i_id in informe_ids]

    glucosa_vals = get_series("GLUCOSE", "GLUCOSA")
    col_t_vals = get_series("CHOLESTEROL_TOTAL", "COLESTEROL_TOTAL", "COLESTEROL")
    hdl_vals = get_series("HDL", "HDL_COLESTEROL")
    ldl_vals = get_series("LDL", "LDL_COLESTEROL")
    tg_vals = get_series("TRIGLYCERIDES", "TRIGLICERIDOS")
    urea_vals = get_series("UREA")
    creat_vals = get_series("CREATININE", "CREATININA")
    urico_vals = get_series("URIC_ACID", "ACIDO_URICO")
    psa_t_vals = get_series("PSA_TOTAL", "PSA")
    psa_free_vals = get_series("PSA_FREE", "PSA_LIBRE")
    tsh_vals = get_series("TSH")

    # Ratios con fallback calculado dinámicamente si no estaban guardados en BD
    raw_castelli1 = get_series("RATIO_COL_HDL", "COCIENTE_COL_HDL")
    castelli1_vals = []
    for idx, i_id in enumerate(informe_ids):
        val = raw_castelli1[idx]
        if val is None and col_t_vals[idx] is not None and hdl_vals[idx] and hdl_vals[idx] > 0:
            val = round(col_t_vals[idx] / hdl_vals[idx], 2)
        castelli1_vals.append(val)

    raw_castelli2 = get_series("RATIO_LDL_HDL", "COCIENTE_LDL_HDL")
    castelli2_vals = []
    for idx, i_id in enumerate(informe_ids):
        val = raw_castelli2[idx]
        if val is None and ldl_vals[idx] is not None and hdl_vals[idx] and hdl_vals[idx] > 0:
            val = round(ldl_vals[idx] / hdl_vals[idx], 2)
        castelli2_vals.append(val)

    raw_tg_hdl = get_series("RATIO_TG_HDL", "COCIENTE_TG_HDL")
    tg_hdl_vals = []
    for idx, i_id in enumerate(informe_ids):
        val = raw_tg_hdl[idx]
        if val is None and tg_vals[idx] is not None and hdl_vals[idx] and hdl_vals[idx] > 0:
            val = round(tg_vals[idx] / hdl_vals[idx], 2)
        tg_hdl_vals.append(val)

    raw_psa_ratio = get_series("RATIO_PSA_L_T", "RATIO_PSA")
    psa_ratio_vals = []
    for idx, i_id in enumerate(informe_ids):
        val = raw_psa_ratio[idx]
        if val is not None:
            if val <= 1.0:
                val = round(val * 100, 1)
            else:
                val = round(val, 1)
        elif psa_free_vals[idx] is not None and psa_t_vals[idx] and psa_t_vals[idx] > 0:
            val = round((psa_free_vals[idx] / psa_t_vals[idx]) * 100, 1)
        psa_ratio_vals.append(val)

    return ChartsResponse(
        glucosa=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(
                    label="Glucosa Basal (mg/dL)",
                    data=glucosa_vals,
                    borderColor="#2563eb",
                    backgroundColor="rgba(37, 99, 235, 0.1)",
                    borderWidth=2.5,
                    fill=True,
                    yAxisID="y"
                )
            ]
        ),
        lipidos=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="Colesterol Total", data=col_t_vals, borderColor="#2563eb", borderWidth=2.5, yAxisID="y"),
                ChartDataset(label="LDL-Colesterol", data=ldl_vals, borderColor="#f59e0b", borderWidth=2.5, yAxisID="y"),
                ChartDataset(label="HDL-Colesterol", data=hdl_vals, borderColor="#10b981", borderWidth=2.0, yAxisID="y"),
                ChartDataset(label="Triglicéridos", data=tg_vals, borderColor="#8b5cf6", borderWidth=1.5, yAxisID="y")
            ]
        ),
        castelli=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="Castelli I: Col.T / HDL (Ref < 5.0)", data=castelli1_vals, borderColor="#8b5cf6", backgroundColor="rgba(139, 92, 246, 0.1)", borderWidth=2.5, yAxisID="y"),
                ChartDataset(label="Castelli II: LDL / HDL (Ref < 4.3)", data=castelli2_vals, borderColor="#ec4899", backgroundColor="rgba(236, 72, 153, 0.1)", borderWidth=2.5, yAxisID="y")
            ]
        ),
        ratios_tg=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(
                    label="Triglicéridos / HDL (Ref < 2.0)",
                    data=tg_hdl_vals,
                    borderColor="#06b6d4",
                    backgroundColor="rgba(6, 182, 212, 0.15)",
                    borderWidth=2.5,
                    fill=True,
                    yAxisID="y"
                )
            ]
        ),
        renal=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="Urea (mg/dL)", data=urea_vals, borderColor="#3b82f6", borderWidth=2.0, yAxisID="y"),
                ChartDataset(label="Creatinina (mg/dL)", data=creat_vals, borderColor="#8b5cf6", borderWidth=2.0, yAxisID="y1")
            ]
        ),
        urico=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="Ácido Úrico (mg/dL)", data=urico_vals, borderColor="#059669", backgroundColor="rgba(5, 150, 105, 0.1)", borderWidth=2.5, fill=True, yAxisID="y")
            ]
        ),
        psa=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="PSA Total (ng/mL)", data=psa_t_vals, borderColor="#8b5cf6", borderWidth=2.5, yAxisID="y"),
                ChartDataset(label="Ratio PSA L/T (%)", data=psa_ratio_vals, borderColor="#10b981", borderWidth=2.0, yAxisID="y1")
            ]
        ),
        tsh=ChartConfig(
            labels=dates,
            datasets=[
                ChartDataset(label="TSH (µUI/mL)", data=tsh_vals, borderColor="#0284c7", backgroundColor="rgba(2, 132, 199, 0.1)", borderWidth=2.0, fill=True, yAxisID="y")
            ]
        )
    )

@router.get("/files", response_model=List[AuditFileItem])
def get_audit_files(db: Session = Depends(get_db)):
    """
    Devuelve el inventario completo de archivos de analíticas subidos al sistema.
    """
    informes = db.query(Informe).order_by(Informe.fecha.desc(), Informe.id.desc()).all()
    res = []
    for inf in informes:
        res.append(AuditFileItem(
            id=inf.id,
            fecha=inf.fecha,
            etiqueta_corta=inf.etiqueta_corta,
            laboratorio=inf.laboratorio or "Desconocido",
            facultativo=inf.facultativo or "No especificado",
            referencia=inf.referencia or "Sin ref.",
            archivo_pdf=inf.archivo_pdf,
            total_mediciones=len(inf.mediciones),
            dictamen_global=inf.dictamen_global or "Sin dictamen",
            created_at=inf.created_at.strftime("%Y-%m-%d %H:%M") if inf.created_at else None
        ))
    return res

@router.delete("/files/{informe_id}")
def delete_audit_file(informe_id: int, db: Session = Depends(get_db)):
    """
    Elimina una analítica y sus mediciones asociadas de la base de datos.
    """
    informe = db.query(Informe).filter_by(id=informe_id).first()
    if not informe:
        raise HTTPException(status_code=404, detail="Analítica no encontrada")

    if informe.archivo_pdf:
        pdf_path = settings.paths.uploads_dir / informe.archivo_pdf
        if pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass

    db.delete(informe)
    db.commit()
    return {"status": "success", "message": f"Analítica ID {informe_id} eliminada correctamente"}

@router.get("/catalog")
def get_canonical_catalog():
    """
    Devuelve el catálogo canónico estructurado y agrupado por especialidad clínica
    para alimentar los selectores de analitos y evitar inconsistencias en la base de datos.
    """
    from app.services.analito_normalizer import CANONICAL_CATALOG
    grouped = {}
    for code, item in CANONICAL_CATALOG.items():
        if item.get("es_ratio") or code.startswith("RATIO_"):
            continue
        g = item.get("grupo", "Otras Determinaciones")
        grouped.setdefault(g, []).append({
            "codigo": code,
            "nombre": item["nombre"],
            "unidad": item.get("unidad", ""),
            "ref": item.get("ref", "")
        })
    return grouped

@router.get("/informes/{informe_id}", response_model=InformeDetailResponse)
def get_informe_detail(informe_id: int, db: Session = Depends(get_db)):
    """
    Devuelve los metadatos completos y todas las mediciones de un informe específico para su edición.
    """
    informe = db.query(Informe).filter_by(id=informe_id).first()
    if not informe:
        raise HTTPException(status_code=404, detail="Analítica no encontrada")

    mediciones_db = (
        db.query(Medicion)
        .join(Analito, Medicion.analito_id == Analito.id)
        .filter(Medicion.informe_id == informe.id)
        .order_by(Analito.orden.asc(), Analito.nombre_visible.asc(), Medicion.id.asc())
        .all()
    )

    ratio_codes = {
        "RATIO_COL_HDL", "RATIO_LDL_HDL", "RATIO_TG_HDL",
        "RATIO_LDL_COL", "RATIO_HDL_COL", "RATIO_TG_COL", "RATIO_PSA_L_T"
    }

    mediciones_list = []
    for m in mediciones_db:
        codigo = m.analito.codigo if m.analito else ""
        nombre = m.analito.nombre_visible if m.analito else "Desconocido"
        val = m.valor_numerico if m.valor_numerico is not None else (m.valor_texto or "")
        mediciones_list.append(MedicionDetail(
            id=m.id,
            codigo=codigo,
            nombre=nombre,
            valor=val,
            unidad=m.unidad or (m.analito.unidad_estandar if m.analito else ""),
            rango_referencia=m.ref_texto or (m.analito.ref_texto_defecto if m.analito else ""),
            estado_estimado=m.estado_semaforo or "Normal",
            es_ratio=(codigo in ratio_codes)
        ))

    return InformeDetailResponse(
        id=informe.id,
        fecha=informe.fecha,
        etiqueta_corta=informe.etiqueta_corta,
        laboratorio=informe.laboratorio or "",
        facultativo=informe.facultativo or "",
        referencia=informe.referencia or "",
        dictamen_global=informe.dictamen_global or "",
        archivo_pdf=informe.archivo_pdf,
        mediciones=mediciones_list
    )

@router.put("/informes/{informe_id}")
def update_informe(informe_id: int, req: InformeUpdateRequest, db: Session = Depends(get_db)):
    """
    Actualiza los metadatos y mediciones de un informe ya guardado en la base de datos.
    Recalcula automáticamente los ratios dependientes (Castelli, TG/HDL, PSA, etc.).
    """
    informe = db.query(Informe).filter_by(id=informe_id).first()
    if not informe:
        raise HTTPException(status_code=404, detail="Analítica no encontrada")

    # 1. Actualizar metadatos del informe
    informe.fecha = req.fecha
    partes_fecha = req.fecha.split("-")
    if len(partes_fecha) == 3:
        informe.etiqueta_corta = f"{partes_fecha[2]}/{partes_fecha[1]}/{partes_fecha[0][2:]}"
    else:
        informe.etiqueta_corta = req.fecha

    informe.laboratorio = req.laboratorio
    informe.facultativo = req.facultativo or "No especificado"
    informe.referencia = req.referencia
    informe.dictamen_global = req.dictamen_global or "Control favorable"

    # 2. Borrar mediciones previas asociadas a este informe para sincronización limpia
    db.query(Medicion).filter_by(informe_id=informe.id).delete()
    db.flush()

    # 3. Procesar mediciones del request
    mediciones_dict = {}
    analitos_procesados = {}

    ratio_codes = {
        "RATIO_COL_HDL", "RATIO_LDL_HDL", "RATIO_TG_HDL",
        "RATIO_LDL_COL", "RATIO_HDL_COL", "RATIO_TG_COL", "RATIO_PSA_L_T"
    }

    for item in req.mediciones:
        if not item.nombre or not item.nombre.strip():
            continue

        # Si el usuario no modificó manualmente un ratio calculado, se recalculará automáticamente abajo
        if item.codigo in ratio_codes and item.es_ratio:
            continue

        code_key, norm_nombre, norm_cat, norm_unit = normalize_analito(
            item.nombre,
            unidad=item.unidad,
            valor=item.valor,
            codigo_sugerido=item.codigo
        )

        analito = db.query(Analito).filter_by(codigo=code_key).first()
        if not analito:
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

        num_val, clean_val, std_unit, std_ref = standardize_medicion(
            code_key, item.valor, item.unidad, item.rango_referencia
        )

        ref_final = std_ref or item.rango_referencia
        calc_st = evaluar_estado_semaforo(num_val, ref_final) if num_val is not None else "Normal"
        est_final = calc_st if calc_st in ["Alto", "Bajo"] else (getattr(item, "estado_estimado", None) or "Normal")

        if code_key in analitos_procesados:
            med_existente = analitos_procesados[code_key]
            if med_existente.valor_numerico is None and num_val is not None:
                med_existente.valor_numerico = num_val
                med_existente.valor_texto = None
                med_existente.unidad = std_unit or norm_unit
                med_existente.ref_texto = ref_final
                med_existente.estado_semaforo = est_final
                mediciones_dict[code_key] = num_val
            continue

        med = Medicion(
            informe_id=informe.id,
            analito_id=analito.id,
            valor_numerico=num_val,
            valor_texto=clean_val if num_val is None else None,
            unidad=std_unit or norm_unit,
            ref_texto=ref_final,
            estado_semaforo=est_final
        )
        db.add(med)
        db.flush()
        analitos_procesados[code_key] = med

        if num_val is not None:
            mediciones_dict[code_key] = num_val

    # 4. Recalcular ratios automáticos derivados y guardarlos
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
    return {
        "status": "success",
        "message": f"Analítica del {informe.fecha} actualizada correctamente.",
        "informe_id": informe.id
    }


