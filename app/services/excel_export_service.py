"""Servicio de exportación de informes clínicos a formato Microsoft Excel (.xlsx)."""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.api.analiticas import (
    _query_informes_filtered,
    get_charts_data,
    get_dashboard_summary,
    get_tables,
)
from app.services.analito_normalizer import evaluar_estado_semaforo, parse_reference_bounds


# Paleta corporativa inspirada en la interfaz web (Tailwind Slate / Blue / Emerald / Amber / Rose)
COLOR_SLATE_900 = "0F172A"
COLOR_SLATE_800 = "1E293B"
COLOR_SLATE_700 = "334155"
COLOR_SLATE_600 = "475569"
COLOR_SLATE_500 = "64748B"
COLOR_SLATE_200 = "E2E8F0"
COLOR_SLATE_100 = "F1F5F9"
COLOR_SLATE_50 = "F8FAFC"

COLOR_BLUE_800 = "1E40AF"
COLOR_BLUE_700 = "1D4ED8"
COLOR_BLUE_600 = "2563EB"
COLOR_BLUE_100 = "DBEAFE"
COLOR_BLUE_50 = "EFF6FF"

COLOR_INDIGO_900 = "312E81"
COLOR_EMERALD_800 = "065F46"
COLOR_EMERALD_700 = "047857"
COLOR_EMERALD_100 = "D1FAE5"
COLOR_EMERALD_50 = "ECFDF5"

COLOR_AMBER_900 = "78350F"
COLOR_AMBER_800 = "92400E"
COLOR_AMBER_200 = "FDE68A"
COLOR_AMBER_100 = "FEF3C7"
COLOR_AMBER_50 = "FFFBEB"

COLOR_ROSE_800 = "9F1239"
COLOR_ROSE_700 = "BE123C"
COLOR_ROSE_200 = "FECDD3"
COLOR_ROSE_100 = "FFE4E6"
COLOR_ROSE_50 = "FFF1F2"

COLOR_WHITE = "FFFFFF"

THIN_BORDER_SIDE = Side(style="thin", color=COLOR_SLATE_200)
MED_BORDER_SIDE = Side(style="medium", color="94A3B8")
CARD_BORDER = Border(
    left=THIN_BORDER_SIDE,
    right=THIN_BORDER_SIDE,
    top=THIN_BORDER_SIDE,
    bottom=THIN_BORDER_SIDE,
)


def _try_float(val: Any) -> Optional[float]:
    if val is None or val == "" or val == "-":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None


def _evaluate_borderline(val_num: Optional[float], ref_str: Optional[str], name: str = "") -> Optional[str]:
    """Replica el modelo híbrido de zona límite (borderline) de la tabla de Historial."""
    if val_num is None:
        return None
    clean_name = (name or "").strip().lower()

    if clean_name == "hba1c" or "hemoglobina glicada" in clean_name or "glicosilada" in clean_name:
        if 5.4 <= val_num < 5.7:
            return "Límite preventivo prediabetes (5.4% - 5.6%)"
        return None
    if "ifcc" in clean_name:
        if 36.0 <= val_num < 39.0:
            return "Límite preventivo prediabetes (36 - 38.9 mmol/mol)"
        return None
    if clean_name in {"glucosa", "glucosa basal"} or "glicemia" in clean_name:
        if val_num >= 95.0:
            return "Sobrepasa umbral ADA (>100 mg/dL)" if val_num > 100.0 else "Próximo al límite ADA (95 - 100 mg/dL)"
        return None
    if "vitamina d" in clean_name or "25-oh" in clean_name:
        if 20.0 <= val_num < 30.0:
            return "Insuficiencia / Límite de normalidad (20 - 29 ng/mL)"
        return None
    if "triglicéridos / hdl" in clean_name or "ratio tg/hdl" in clean_name or clean_name == "tg/hdl":
        if 1.5 <= val_num <= 2.0:
            return "Límite de riesgo cardiometabólico (1.5 - 2.0)"
        return None
    if "castelli ii" in clean_name or "ldl/hdl" in clean_name or clean_name == "cociente ldl/hdl":
        if 3.0 <= val_num <= 4.3:
            return "Límite intermedio riesgo vascular (3.0 - 4.3)"
        return None
    if "castelli i" in clean_name or "col/hdl" in clean_name or clean_name == "cociente col/hdl":
        if 4.0 <= val_num <= 5.0:
            return "Límite intermedio riesgo vascular (4.0 - 5.0)"
        return None

    low, high = parse_reference_bounds(ref_str)
    if low is None and high is None:
        return None

    if low is not None and high is not None:
        w = high - low
        if w <= 0 or val_num < low - 1e-5 or val_num > high + 1e-5:
            return None
        delta = 0.10 * w
        if val_num >= high - delta:
            return f"Próximo al límite superior ({high})"
        if val_num <= low + delta:
            return f"Próximo al límite inferior ({low})"
        return None

    if high is not None and low is None:
        if val_num > high + 1e-5:
            return None
        delta = 0.10 * high
        if val_num >= high - delta:
            return f"Próximo al límite superior ({high})"
        return None

    if low is not None and high is None:
        if val_num < low - 1e-5:
            return None
        delta = 0.15 * low
        if val_num <= low + delta:
            return f"Próximo al límite inferior ({low})"
        return None

    return None


def _badge_colors(badge_text: str) -> Tuple[str, str]:
    """Devuelve (bg_hex, fg_hex) según el texto de insignia clínica."""
    txt = (badge_text or "").lower()
    if "atención" in txt or "atencion" in txt or "🔴" in txt or "desfavorable" in txt:
        return COLOR_ROSE_100, COLOR_ROSE_800
    if "seguimiento" in txt or "🟡" in txt or "límite" in txt or "limite" in txt:
        return COLOR_AMBER_100, COLOR_AMBER_900
    if "normal" in txt or "🟢" in txt or "favorable" in txt:
        return COLOR_EMERALD_100, COLOR_EMERALD_800
    return COLOR_SLATE_100, COLOR_SLATE_700


def _trend_label_es(clinical_trend: Optional[str], trend_symbol: Optional[str] = None) -> str:
    mapping = {
        "FAVORABLE": "Favorable",
        "DESFAVORABLE": "Desfavorable",
        "ESTABLE": "Estable",
    }
    base = mapping.get(clinical_trend or "", "No evaluable")
    if trend_symbol and base != "No evaluable":
        return f"{trend_symbol} {base}"
    return base


def _format_date_es(date_str: Optional[str]) -> str:
    if not date_str or date_str == "-":
        return "-"
    parts = str(date_str).strip().split("-")
    if len(parts) == 3:
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return str(date_str)


# Definición ordenada de los gráficos de la Pestaña 3
CHART_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "key": "glucosa",
        "title": "Evolución del metabolismo glucídico",
        "category": "Metabolismo glucídico",
        "y_title": "Glucosa (mg/dL)",
        "y1_title": "HbA1c (%)",
    },
    {
        "key": "insulina_homa",
        "title": "Insulina y resistencia a la insulina",
        "category": "Metabolismo glucídico",
        "y_title": "Insulina (µUI/mL)",
        "y1_title": "HOMA-IR",
        "require_all_datasets": True,
    },
    {
        "key": "lipidos",
        "title": "Evolución del perfil lipídico",
        "category": "Perfil lipídico",
        "y_title": "mg/dL",
    },
    {
        "key": "castelli",
        "title": "Índices aterogénicos (Castelli I y II)",
        "category": "Perfil lipídico",
        "y_title": "Cociente",
    },
    {
        "key": "ratios_tg",
        "title": "Cociente Triglicéridos / HDL",
        "category": "Perfil lipídico",
        "y_title": "Ratio TG/HDL",
    },
    {
        "key": "apob_non_hdl",
        "title": "Apolipoproteína B y Colesterol no-HDL",
        "category": "Perfil lipídico",
        "y_title": "ApoB (mg/dL)",
        "y1_title": "No-HDL (mg/dL)",
    },
    {
        "key": "renal",
        "title": "Evolución de la función renal",
        "category": "Función renal",
        "y_title": "Creatinina (mg/dL)",
        "y1_title": "eGFR (mL/min/1.73 m²)",
    },
    {
        "key": "renal_metabolites",
        "title": "Metabolitos renales",
        "category": "Función renal",
        "y_title": "Urea (mg/dL)",
        "y1_title": "Ácido úrico (mg/dL)",
    },
    {
        "key": "albuminuria",
        "title": "Albuminuria (ACR)",
        "category": "Función renal",
        "y_title": "ACR (mg/g)",
    },
    {
        "key": "hepatic_enzymes",
        "title": "Evolución de las enzimas hepáticas",
        "category": "Función hepática",
        "y_title": "Enzimas (U/L)",
    },
    {
        "key": "hepatic_synthesis",
        "title": "Bilirrubina y función de síntesis hepática",
        "category": "Función hepática",
        "y_title": "Bilirrubina (mg/dL)",
        "y1_title": "Albúmina (g/dL) / INR",
    },
    {
        "key": "red_series",
        "title": "Serie roja (Hemoglobina, Hematocrito, VCM)",
        "category": "Hemograma / hierro",
        "y_title": "Hemoglobina (g/dL)",
        "y1_title": "Hematocrito (%) / VCM (fL)",
    },
    {
        "key": "white_platelets",
        "title": "Serie blanca y plaquetas",
        "category": "Hemograma / hierro",
        "y_title": "Leucocitos (×10³/µL)",
        "y1_title": "Plaquetas (×10³/µL)",
    },
    {
        "key": "iron_metabolism",
        "title": "Metabolismo del hierro",
        "category": "Hemograma / hierro",
        "y_title": "Ferritina (ng/mL)",
        "y1_title": "Hierro sérico (µg/dL)",
    },
    {
        "key": "psa",
        "title": "Evolución de marcadores prostáticos",
        "category": "Otros marcadores",
        "y_title": "PSA total y libre (ng/mL)",
        "y1_title": "Ratio PSA L/T (%)",
    },
    {
        "key": "bone_metabolism",
        "title": "Vitamina D y metabolismo óseo",
        "category": "Otros marcadores",
        "y_title": "Vitamina D (ng/mL)",
        "y1_title": "Calcio (mg/dL) / PTH (pg/mL)",
    },
    {
        "key": "inflammation",
        "title": "Marcadores inflamatorios",
        "category": "Otros marcadores",
        "y_title": "PCR (mg/dL)",
        "y1_title": "VSG 1ª hora (mm)",
    },
    {
        "key": "rheumatology",
        "title": "Autoinmunidad reumatológica",
        "category": "Otros marcadores",
        "y_title": "Factor reumatoide (UI/mL)",
        "y1_title": "Anti-CCP (UI/mL)",
    },
    {
        "key": "vitamins",
        "title": "Vitaminas y micronutrientes",
        "category": "Otros marcadores",
        "y_title": "Vitamina B12 (pg/mL)",
        "y1_title": "Ácido fólico (ng/mL)",
    },
    {
        "key": "thyroid_profile",
        "title": "Evolución del perfil tiroideo",
        "category": "Función tiroidea",
        "y_title": "TSH (µUI/mL)",
        "y1_title": "T4 libre (ng/dL) / T3 libre (pg/mL)",
    },
    {
        "key": "thyroid_totals",
        "title": "T4 y T3 totales",
        "category": "Función tiroidea",
        "y_title": "T4 total (µg/dL)",
        "y1_title": "T3 total (ng/mL)",
    },
]


def _build_resumen_sheet(ws, summary, fecha_inicio: str, fecha_fin: str) -> None:
    ws.views.sheetView[0].showGridLines = True

    # Título principal
    ws.merge_cells("A1:I1")
    title_cell = ws["A1"]
    title_cell.value = "CONTROL DE ANALÍTICAS CLÍNICAS — RESUMEN EJECUTIVO Y TARJETAS KPI"
    title_cell.font = Font(name="Calibri", size=14, bold=True, color=COLOR_WHITE)
    title_cell.fill = PatternFill("solid", fgColor=COLOR_SLATE_800)
    title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 30

    # Ficha del paciente y metadatos del rango
    paciente = summary.paciente or {}
    nombre_pac = paciente.get("nombre") or "Usuario (paciente)"
    edad_pac = paciente.get("edad") or "-"
    sexo_pac = paciente.get("sexo") or "No especificado"
    meta_parts = [nombre_pac]
    if edad_pac and edad_pac != "-":
        meta_parts.append(edad_pac)
    if sexo_pac in ("Masculino", "Femenino"):
        meta_parts.append(sexo_pac)

    ws.merge_cells("A2:D2")
    ws["A2"].value = f"Paciente: {' · '.join(meta_parts)}"
    ws["A2"].font = Font(name="Calibri", size=11, bold=True, color=COLOR_SLATE_900)
    ws["A2"].fill = PatternFill("solid", fgColor=COLOR_SLATE_100)
    ws["A2"].alignment = Alignment(vertical="center", indent=1)

    ws.merge_cells("E2:G2")
    ws["E2"].value = f"Rango analizado: {_format_date_es(fecha_inicio)} a {_format_date_es(fecha_fin)} ({summary.total_controles} controles)"
    ws["E2"].font = Font(name="Calibri", size=10, bold=True, color=COLOR_BLUE_800)
    ws["E2"].fill = PatternFill("solid", fgColor=COLOR_BLUE_50)
    ws["E2"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("H2:I2")
    ws["H2"].value = f"Última analítica: {_format_date_es(summary.ultima_fecha)}"
    ws["H2"].font = Font(name="Calibri", size=10, bold=True, color=COLOR_EMERALD_800)
    ws["H2"].fill = PatternFill("solid", fgColor=COLOR_EMERALD_50)
    ws["H2"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 24

    # Dictamen global
    ws.merge_cells("A3:I3")
    dictamen_txt = summary.dictamen_global or "Control favorable"
    if summary.dictamen_subtitulo and summary.dictamen_subtitulo not in ("Parámetros analizados por el sistema", "-"):
        dictamen_txt = f"{dictamen_txt} — {summary.dictamen_subtitulo}"
    ws["A3"].value = f"Dictamen clínico global: {dictamen_txt}"
    ws["A3"].font = Font(name="Calibri", size=10, italic=True, color=COLOR_SLATE_700)
    ws["A3"].fill = PatternFill("solid", fgColor=COLOR_SLATE_50)
    ws["A3"].alignment = Alignment(vertical="center", indent=1, wrap_text=True)
    ws.row_dimensions[3].height = 26

    for r in (2, 3):
        for c in range(1, 10):
            ws.cell(row=r, column=c).border = CARD_BORDER

    current_row = 5

    # Sección 1: Las 6 Tarjetas KPI Principales
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=9)
    sec_cell = ws.cell(row=current_row, column=1, value="1. TARJETAS KPI PRINCIPALES (VALORES ACTUALES E INDICADORES DE TENDENCIA)")
    sec_cell.font = Font(name="Calibri", size=11, bold=True, color=COLOR_BLUE_800)
    sec_cell.fill = PatternFill("solid", fgColor=COLOR_BLUE_100)
    sec_cell.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[current_row].height = 24
    current_row += 2

    headers_kpi = [
        "Parámetro / Determinación",
        "Jerarquía",
        "Valor Actual",
        "Unidad",
        "Estado",
        "Variación vs. Previo",
        "Tendencia Longitudinal",
        "Origen del Dato",
        "Notas",
    ]

    for kpi in summary.kpis or []:
        # Cabecera de la tarjeta KPI
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=5)
        card_title = ws.cell(row=current_row, column=1, value=f"▪ {kpi.title.upper()}")
        card_title.font = Font(name="Calibri", size=11, bold=True, color=COLOR_WHITE)
        card_title.fill = PatternFill("solid", fgColor=COLOR_SLATE_800)
        card_title.alignment = Alignment(vertical="center", indent=1)

        # Estado global de la tarjeta
        ws.merge_cells(start_row=current_row, start_column=6, end_row=current_row, end_column=7)
        bg_badge, fg_badge = _badge_colors(kpi.badge_text)
        badge_cell = ws.cell(row=current_row, column=6, value=f"Estado: {kpi.badge_text}")
        badge_cell.font = Font(name="Calibri", size=10, bold=True, color=fg_badge)
        badge_cell.fill = PatternFill("solid", fgColor=bg_badge)
        badge_cell.alignment = Alignment(horizontal="center", vertical="center")

        # Tendencia global de la tarjeta
        ws.merge_cells(start_row=current_row, start_column=8, end_row=current_row, end_column=9)
        trend_raw = kpi.trend_badge_text or "No evaluable"
        if trend_raw.upper() == "SIN TENDENCIA":
            trend_raw = "No evaluable"
        bg_tr, fg_tr = _badge_colors(trend_raw)
        trend_cell = ws.cell(row=current_row, column=8, value=f"Tendencia: {trend_raw}")
        trend_cell.font = Font(name="Calibri", size=10, bold=True, color=fg_tr)
        trend_cell.fill = PatternFill("solid", fgColor=bg_tr)
        trend_cell.alignment = Alignment(horizontal="center", vertical="center")

        for c in range(1, 10):
            ws.cell(row=current_row, column=c).border = CARD_BORDER
        ws.row_dimensions[current_row].height = 24
        current_row += 1

        # Subcabecera de columnas de la tarjeta
        for idx_col, h_text in enumerate(headers_kpi, start=1):
            c_hdr = ws.cell(row=current_row, column=idx_col, value=h_text)
            c_hdr.font = Font(name="Calibri", size=9, bold=True, color=COLOR_SLATE_700)
            c_hdr.fill = PatternFill("solid", fgColor=COLOR_SLATE_200)
            c_hdr.alignment = Alignment(
                horizontal="left" if idx_col in (1, 9) else "center",
                vertical="center",
            )
            c_hdr.border = CARD_BORDER
        ws.row_dimensions[current_row].height = 19
        current_row += 1

        # Construir lista unificada de filas de la tarjeta (parámetro principal + filas desglosadas)
        card_rows: List[Dict[str, Any]] = [
            {
                "label": kpi.main_label or kpi.title,
                "tipo": "Principal (Destacado)",
                "val": kpi.main_value,
                "unit": kpi.unit or "",
                "status": kpi.main_display_status or ("Atención" if kpi.is_altered else "Normal"),
                "is_altered": bool(kpi.is_altered),
                "var_delta": kpi.main_var_delta or "-",
                "trend_text": _trend_label_es(kpi.main_clinical_trend, kpi.main_trend_symbol),
                "clinical_trend": kpi.main_clinical_trend,
                "is_hist": bool(kpi.main_is_historical),
                "fecha_origen": kpi.main_fecha_origen,
                "footnote": kpi.main_footnote_symbol or "",
                "is_main": True,
            }
        ]

        for f in kpi.filas or []:
            tipo_map = {
                "principal": "Principal",
                "secundario": "Secundario",
                "complementario": "Complementario",
            }
            card_rows.append(
                {
                    "label": f.label,
                    "tipo": tipo_map.get(f.tipo_parametro or "secundario", "Secundario"),
                    "val": f.val,
                    "unit": f.unit or "",
                    "status": f.display_status or ("Atención" if f.is_altered else "Normal"),
                    "is_altered": bool(f.is_altered),
                    "var_delta": f.var_delta or "-",
                    "trend_text": _trend_label_es(f.clinical_trend, f.trend_symbol),
                    "clinical_trend": f.clinical_trend,
                    "is_hist": bool(f.es_historico),
                    "fecha_origen": f.fecha_origen,
                    "footnote": f.footnote_symbol or "",
                    "is_main": False,
                }
            )

        for r_data in card_rows:
            status_str = r_data["status"]
            symbol = " ▲" if status_str == "Alto" else (" ▼" if status_str == "Bajo" else "")
            status_display = f"{status_str}{symbol}" if status_str != "Normal" else "Normal"

            origen_str = (
                f"Histórico ({_format_date_es(r_data['fecha_origen'])})"
                if r_data["is_hist"] and r_data["fecha_origen"]
                else f"Actual ({_format_date_es(summary.ultima_fecha)})"
            )
            nota_str = (
                f"{r_data['footnote']} Dato de control anterior ({_format_date_es(r_data['fecha_origen'])})"
                if r_data["is_hist"] and r_data["fecha_origen"]
                else ""
            )

            num_val = _try_float(r_data["val"])
            val_cell_value: Any = num_val if num_val is not None else r_data["val"]

            row_values = [
                r_data["label"],
                r_data["tipo"],
                val_cell_value,
                r_data["unit"],
                status_display,
                r_data["var_delta"],
                r_data["trend_text"],
                origen_str,
                nota_str,
            ]

            base_bg = COLOR_AMBER_50 if r_data["is_hist"] else (COLOR_BLUE_50 if r_data["is_main"] else COLOR_WHITE)

            for c_idx, cell_val in enumerate(row_values, start=1):
                cell = ws.cell(row=current_row, column=c_idx, value=cell_val)
                cell.border = CARD_BORDER
                cell.fill = PatternFill("solid", fgColor=base_bg)
                cell.font = Font(
                    name="Calibri",
                    size=10,
                    bold=(r_data["is_main"] or c_idx in (1, 3)),
                    color=COLOR_SLATE_900,
                )
                cell.alignment = Alignment(
                    horizontal="left" if c_idx in (1, 9) else "center",
                    vertical="center",
                )

            # Estilo específico de valor y estado si está alterado o en límite
            val_c = ws.cell(row=current_row, column=3)
            st_c = ws.cell(row=current_row, column=5)
            if r_data["is_altered"] or status_str in ("Alto", "Bajo", "Atención"):
                val_c.font = Font(name="Calibri", size=10, bold=True, color=COLOR_ROSE_800)
                st_c.font = Font(name="Calibri", size=9, bold=True, color=COLOR_ROSE_800)
                st_c.fill = PatternFill("solid", fgColor=COLOR_ROSE_100)
            elif status_str == "Límite":
                val_c.font = Font(name="Calibri", size=10, bold=True, color=COLOR_AMBER_900)
                st_c.font = Font(name="Calibri", size=9, bold=True, color=COLOR_AMBER_900)
                st_c.fill = PatternFill("solid", fgColor=COLOR_AMBER_100)
            else:
                st_c.font = Font(name="Calibri", size=9, bold=False, color=COLOR_EMERALD_800)

            # Estilo de tendencia clínica individual
            tr_c = ws.cell(row=current_row, column=7)
            if r_data["clinical_trend"] == "FAVORABLE":
                tr_c.font = Font(name="Calibri", size=9, bold=True, color=COLOR_EMERALD_800)
                tr_c.fill = PatternFill("solid", fgColor=COLOR_EMERALD_50)
            elif r_data["clinical_trend"] == "DESFAVORABLE":
                tr_c.font = Font(name="Calibri", size=9, bold=True, color=COLOR_ROSE_800)
                tr_c.fill = PatternFill("solid", fgColor=COLOR_ROSE_50)

            ws.row_dimensions[current_row].height = 20
            current_row += 1

        current_row += 1  # Espacio entre tarjetas

    # Sección 2: Séptima Tarjeta — Otros valores de interés clínico
    ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=9)
    otros_hdr = ws.cell(
        row=current_row,
        column=1,
        value="2. OTROS VALORES DE INTERÉS CLÍNICO (PANELES COMPLEMENTARIOS DINÁMICOS)",
    )
    otros_hdr.font = Font(name="Calibri", size=11, bold=True, color=COLOR_BLUE_800)
    otros_hdr.fill = PatternFill("solid", fgColor=COLOR_BLUE_100)
    otros_hdr.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[current_row].height = 24
    current_row += 2

    if summary.otros_valores:
        for seccion in summary.otros_valores:
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=6)
            sec_title = f"{seccion.icono or '🔹'} {seccion.titulo}".strip()
            sc_cell = ws.cell(row=current_row, column=1, value=sec_title)
            sc_cell.font = Font(name="Calibri", size=10, bold=True, color=COLOR_WHITE)
            sc_cell.fill = PatternFill("solid", fgColor=COLOR_SLATE_700)
            sc_cell.alignment = Alignment(vertical="center", indent=1)

            ws.merge_cells(start_row=current_row, start_column=7, end_row=current_row, end_column=9)
            bg_b, fg_b = _badge_colors(seccion.badge_text)
            b_cell = ws.cell(row=current_row, column=7, value=f"Estado del panel: {seccion.badge_text}")
            b_cell.font = Font(name="Calibri", size=10, bold=True, color=fg_b)
            b_cell.fill = PatternFill("solid", fgColor=bg_b)
            b_cell.alignment = Alignment(horizontal="center", vertical="center")

            for c in range(1, 10):
                ws.cell(row=current_row, column=c).border = CARD_BORDER
            ws.row_dimensions[current_row].height = 22
            current_row += 1

            for item in seccion.items:
                ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=3)
                lbl_c = ws.cell(row=current_row, column=1, value=item.label)
                lbl_c.font = Font(name="Calibri", size=10, bold=True, color=COLOR_SLATE_800)
                lbl_c.alignment = Alignment(vertical="center", indent=1)

                num_v = _try_float(item.val)
                val_c = ws.cell(row=current_row, column=4, value=num_v if num_v is not None else item.val)
                val_c.alignment = Alignment(horizontal="center", vertical="center")
                val_c.font = Font(
                    name="Calibri",
                    size=10,
                    bold=True,
                    color=COLOR_ROSE_800 if item.is_altered else COLOR_SLATE_900,
                )

                unit_c = ws.cell(row=current_row, column=5, value=item.unit or "")
                unit_c.alignment = Alignment(horizontal="center", vertical="center")
                unit_c.font = Font(name="Calibri", size=9, color=COLOR_SLATE_600)

                ws.merge_cells(start_row=current_row, start_column=6, end_row=current_row, end_column=9)
                st_txt = "Fuera de rango / Seguimiento" if item.is_altered else "Dentro de referencia"
                st_c = ws.cell(row=current_row, column=6, value=st_txt)
                st_c.alignment = Alignment(horizontal="center", vertical="center")
                st_c.font = Font(
                    name="Calibri",
                    size=9,
                    bold=bool(item.is_altered),
                    color=COLOR_ROSE_800 if item.is_altered else COLOR_EMERALD_800,
                )

                for c in range(1, 10):
                    cell_iter = ws.cell(row=current_row, column=c)
                    cell_iter.border = CARD_BORDER
                    if item.is_altered and c in (4, 6, 7, 8, 9):
                        cell_iter.fill = PatternFill("solid", fgColor=COLOR_ROSE_50)

                ws.row_dimensions[current_row].height = 19
                current_row += 1

            current_row += 1
    else:
        ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=9)
        empty_c = ws.cell(
            row=current_row,
            column=1,
            value="No se registran paneles complementarios especiales en el rango de fechas seleccionado.",
        )
        empty_c.font = Font(name="Calibri", size=10, italic=True, color=COLOR_SLATE_500)
        empty_c.alignment = Alignment(vertical="center", indent=1)

    # Ajustar anchos de columna de la hoja Resumen
    col_widths_resumen = {
        1: 36,
        2: 18,
        3: 15,
        4: 13,
        5: 16,
        6: 18,
        7: 22,
        8: 22,
        9: 34,
    }
    for col_idx, width in col_widths_resumen.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def _build_datos_sheet(ws, tables_data, summary, fecha_inicio: str, fecha_fin: str) -> None:
    ws.views.sheetView[0].showGridLines = True

    dates = tables_data.dates or []
    informes_meta = tables_data.informes or []
    total_cols = 3 + len(dates) + 1

    # Fila 1: Banner superior informativo
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(total_cols, 5))
    title_c = ws.cell(
        row=1,
        column=1,
        value=(
            f"HISTORIAL DE RESULTADOS ANALÍTICOS — "
            f"Rango: {_format_date_es(fecha_inicio)} a {_format_date_es(fecha_fin)} "
            f"({len(dates)} controles)"
        ),
    )
    title_c.font = Font(name="Calibri", size=12, bold=True, color=COLOR_WHITE)
    title_c.fill = PatternFill("solid", fgColor=COLOR_SLATE_800)
    title_c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 26

    # Fila 2: Leyenda de colores
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(total_cols, 5))
    legend_c = ws.cell(
        row=2,
        column=1,
        value="Leyenda:   [ ▲ Alto / ▼ Bajo ] Fondo rojo suave: Fuera del rango de referencia   |   Fondo ámbar suave: En rango pero próximo al límite (10%)",
    )
    legend_c.font = Font(name="Calibri", size=9, italic=True, color=COLOR_SLATE_700)
    legend_c.fill = PatternFill("solid", fgColor=COLOR_SLATE_100)
    legend_c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 20

    # Fila 3: Cabeceras de la tabla (igual que #mainBioTable en Pestaña 2)
    header_row = 3
    fixed_headers = ["Parámetro", "Unidad de medida", "Referencia oficial"]
    for c_idx, h_title in enumerate(fixed_headers, start=1):
        c = ws.cell(row=header_row, column=c_idx, value=h_title)
        c.font = Font(name="Calibri", size=10, bold=True, color=COLOR_WHITE)
        c.fill = PatternFill("solid", fgColor=COLOR_SLATE_800)
        c.alignment = Alignment(horizontal="left" if c_idx == 1 else "center", vertical="center", wrap_text=True)
        c.border = CARD_BORDER

    for idx, d_label in enumerate(dates):
        col_pos = 4 + idx
        inf = informes_meta[idx] if idx < len(informes_meta) else {}
        ref_txt = (inf.get("referencia") or "-") if isinstance(inf, dict) else "-"
        header_val = f"{d_label}\nRef: {ref_txt}"

        bg_hex = COLOR_SLATE_700
        if idx == len(dates) - 1:
            bg_hex = COLOR_EMERALD_800
        elif idx == len(dates) - 2:
            bg_hex = COLOR_INDIGO_900
        elif idx == len(dates) - 3:
            bg_hex = COLOR_BLUE_800

        c = ws.cell(row=header_row, column=col_pos, value=header_val)
        c.font = Font(name="Calibri", size=9, bold=True, color=COLOR_WHITE)
        c.fill = PatternFill("solid", fgColor=bg_hex)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = CARD_BORDER

    avg_col_pos = 4 + len(dates)
    avg_hdr = ws.cell(row=header_row, column=avg_col_pos, value="Promedio 18 meses")
    avg_hdr.font = Font(name="Calibri", size=10, bold=True, color=COLOR_WHITE)
    avg_hdr.fill = PatternFill("solid", fgColor=COLOR_BLUE_800)
    avg_hdr.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    avg_hdr.border = CARD_BORDER
    ws.row_dimensions[header_row].height = 30

    # Inmovilizar las 3 primeras columnas y las 3 filas de cabecera (como las columnas sticky en la web)
    ws.freeze_panes = "D4"

    current_row = 4
    current_group = None

    for row in tables_data.bioquimica or []:
        if row.group and row.group != current_group:
            current_group = row.group
            ws.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=total_cols)
            grp_c = ws.cell(row=current_row, column=1, value=str(row.group).upper())
            grp_c.font = Font(name="Calibri", size=10, bold=True, color=COLOR_SLATE_800)
            grp_c.fill = PatternFill("solid", fgColor=COLOR_SLATE_200)
            grp_c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            for c_i in range(1, total_cols + 1):
                ws.cell(row=current_row, column=c_i).border = CARD_BORDER
            ws.row_dimensions[current_row].height = 22
            current_row += 1

        # Columnas fijas 1..3
        c_name = ws.cell(row=current_row, column=1, value=row.name)
        c_name.font = Font(name="Calibri", size=10, bold=True, color=COLOR_SLATE_900)
        c_name.alignment = Alignment(horizontal="left", vertical="center")
        c_name.border = CARD_BORDER

        c_unit = ws.cell(row=current_row, column=2, value=row.unit or "-")
        c_unit.font = Font(name="Calibri", size=9, color=COLOR_SLATE_600)
        c_unit.alignment = Alignment(horizontal="center", vertical="center")
        c_unit.border = CARD_BORDER

        c_ref = ws.cell(row=current_row, column=3, value=row.ref or "-")
        c_ref.font = Font(name="Calibri", size=9, bold=True, color=COLOR_SLATE_600)
        c_ref.alignment = Alignment(horizontal="center", vertical="center")
        c_ref.border = Border(
            left=THIN_BORDER_SIDE,
            right=MED_BORDER_SIDE,
            top=THIN_BORDER_SIDE,
            bottom=THIN_BORDER_SIDE,
        )

        # Celdas por fecha
        for idx, v in enumerate(row.vals):
            col_pos = 4 + idx
            cell_obj = row.cells[idx] if (row.cells and idx < len(row.cells)) else None
            c_val = ws.cell(row=current_row, column=col_pos)
            c_val.border = CARD_BORDER
            c_val.alignment = Alignment(horizontal="center", vertical="center")

            if v is None or v == "":
                c_val.value = "-"
                c_val.font = Font(name="Calibri", size=9, color="CBD5E1")
                continue

            num_v = _try_float(v)
            c_ref_str = (cell_obj.ref if cell_obj and cell_obj.ref else None) or row.ref or ""
            c_status = (cell_obj.status if cell_obj and cell_obj.status else None) or "Normal"

            if c_status == "Normal" and num_v is not None and c_ref_str:
                calc_st = evaluar_estado_semaforo(num_v, c_ref_str)
                if calc_st != "Normal":
                    c_status = calc_st

            is_altered = bool(
                (cell_obj and cell_obj.is_altered)
                or c_status in ("Alto", "Bajo", "Atencion", "Atención", "Alerta", "Alérgeno")
            )

            if is_altered:
                if c_status not in ("Alto", "Bajo") and num_v is not None and c_ref_str:
                    low_b, _ = parse_reference_bounds(c_ref_str)
                    c_status = "Bajo" if (low_b is not None and num_v < low_b) else "Alto"
                symbol = " ▲" if c_status == "Alto" else (" ▼" if c_status == "Bajo" else "")
                c_val.value = f"{v}{symbol}" if symbol else v
                c_val.font = Font(name="Calibri", size=10, bold=True, color=COLOR_ROSE_800)
                c_val.fill = PatternFill("solid", fgColor=COLOR_ROSE_100)
            else:
                borderline_reason = _evaluate_borderline(num_v, c_ref_str, row.name)
                c_val.value = num_v if num_v is not None else v
                if borderline_reason:
                    c_val.font = Font(name="Calibri", size=10, bold=True, color=COLOR_AMBER_900)
                    c_val.fill = PatternFill("solid", fgColor=COLOR_AMBER_100)
                else:
                    c_val.font = Font(name="Calibri", size=10, color=COLOR_SLATE_800)

        # Columna Promedio 18 meses
        c_avg = ws.cell(row=current_row, column=avg_col_pos)
        c_avg.border = Border(
            left=MED_BORDER_SIDE,
            right=MED_BORDER_SIDE,
            top=THIN_BORDER_SIDE,
            bottom=THIN_BORDER_SIDE,
        )
        c_avg.alignment = Alignment(horizontal="center", vertical="center")

        if row.recentAvg and row.recentAvg != "-":
            num_avg = _try_float(row.recentAvg)
            avg_st = evaluar_estado_semaforo(num_avg, row.ref) if num_avg is not None else "Normal"
            if avg_st in ("Alto", "Bajo"):
                sym = " ▲" if avg_st == "Alto" else " ▼"
                c_avg.value = f"{row.recentAvg}{sym}"
                c_avg.font = Font(name="Calibri", size=10, bold=True, color=COLOR_ROSE_800)
                c_avg.fill = PatternFill("solid", fgColor=COLOR_ROSE_100)
            else:
                borderline_avg = _evaluate_borderline(num_avg, row.ref, row.name)
                c_avg.value = num_avg if num_avg is not None else row.recentAvg
                if borderline_avg:
                    c_avg.font = Font(name="Calibri", size=10, bold=True, color=COLOR_AMBER_900)
                    c_avg.fill = PatternFill("solid", fgColor=COLOR_AMBER_100)
                else:
                    c_avg.font = Font(name="Calibri", size=10, bold=True, color=COLOR_BLUE_800)
                    c_avg.fill = PatternFill("solid", fgColor=COLOR_BLUE_50)
        else:
            c_avg.value = "-"
            c_avg.font = Font(name="Calibri", size=9, color="CBD5E1")
            c_avg.fill = PatternFill("solid", fgColor=COLOR_BLUE_50)

        ws.row_dimensions[current_row].height = 20
        current_row += 1

    # Dimensiones de columnas en Hoja Datos
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 20
    for idx in range(len(dates)):
        ws.column_dimensions[get_column_letter(4 + idx)].width = 14
    ws.column_dimensions[get_column_letter(avg_col_pos)].width = 18


def _chart_has_data(config, require_all_datasets: bool = False) -> bool:
    if not config or not config.datasets or not config.labels:
        return False
    if require_all_datasets:
        return all(
            any(v is not None for v in (ds.data or []))
            for ds in config.datasets
        )
    return any(
        any(v is not None for v in (ds.data or []))
        for ds in config.datasets
    )


def _apply_series_styles(chart: LineChart, datasets_meta: List[Any]) -> None:
    palette_fallback = ["2563EB", "DB2777", "10B981", "F59E0B", "7C3AED", "EA580C"]
    for idx, serie in enumerate(chart.series):
        ds = datasets_meta[idx] if idx < len(datasets_meta) else None
        raw_color = (ds.borderColor if ds and ds.borderColor else "").lstrip("#").upper()
        if len(raw_color) != 6:
            raw_color = palette_fallback[idx % len(palette_fallback)]
        serie.graphicalProperties.line.solidFill = raw_color
        serie.graphicalProperties.line.width = 25000  # ~2pt
        serie.smooth = False
        serie.marker.symbol = "circle"
        serie.marker.size = 6
        serie.marker.graphicalProperties.solidFill = raw_color
        serie.marker.graphicalProperties.line.solidFill = raw_color


def _build_graficos_sheet(ws, charts_data, fecha_inicio: str, fecha_fin: str) -> None:
    ws.views.sheetView[0].showGridLines = True

    ws.merge_cells("A1:R1")
    title_c = ws["A1"]
    title_c.value = (
        f"GRÁFICOS EVOLUTIVOS DE ANALÍTICAS CLÍNICAS — "
        f"Rango: {_format_date_es(fecha_inicio)} a {_format_date_es(fecha_fin)}"
    )
    title_c.font = Font(name="Calibri", size=13, bold=True, color=COLOR_WHITE)
    title_c.fill = PatternFill("solid", fgColor=COLOR_SLATE_800)
    title_c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:R2")
    sub_c = ws["A2"]
    sub_c.value = (
        "Gráficos evolutivos generados a partir de las series clínicas de la pestaña «3. Gráficos»."
    )
    sub_c.font = Font(name="Calibri", size=9, italic=True, color=COLOR_SLATE_600)
    sub_c.fill = PatternFill("solid", fgColor=COLOR_SLATE_100)
    sub_c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 20

    # Filtrar únicamente los gráficos con datos en el rango seleccionado
    active_charts: List[Tuple[Dict[str, Any], Any]] = []
    for c_def in CHART_DEFINITIONS:
        cfg = getattr(charts_data, c_def["key"], None)
        if _chart_has_data(cfg, require_all_datasets=bool(c_def.get("require_all_datasets"))):
            active_charts.append((c_def, cfg))

    if not active_charts:
        ws.merge_cells("A4:L4")
        ws["A4"].value = "No hay suficientes datos numéricos para generar gráficos en el rango seleccionado."
        ws["A4"].font = Font(name="Calibri", size=11, italic=True, color=COLOR_SLATE_500)
        return

    # Ajustar ancho uniforme de las columnas visibles para alojar una cuadrícula limpia de 2 gráficos por fila
    for c_idx in range(1, 20):
        ws.column_dimensions[get_column_letter(c_idx)].width = 11

    # Zona auxiliar de tablas de datos de soporte (a partir de la columna Z)
    data_start_col = 26  # Columna Z
    current_data_row = 4

    for idx_chart, (c_def, cfg) in enumerate(active_charts):
        labels = cfg.labels or []
        n_dates = len(labels)

        # Clasificar datasets en eje primario ('y') y eje secundario ('y1' / 'y2')
        primary_ds = [ds for ds in cfg.datasets if (ds.yAxisID or "y") == "y" and any(v is not None for v in (ds.data or []))]
        secondary_ds = [ds for ds in cfg.datasets if (ds.yAxisID or "y") != "y" and any(v is not None for v in (ds.data or []))]

        # Si por algún motivo todos quedaron en secundario, promoverlos a primario
        if not primary_ds and secondary_ds:
            primary_ds, secondary_ds = secondary_ds, []

        ordered_ds = primary_ds + secondary_ds
        if not ordered_ds:
            continue

        table_header_row = current_data_row
        ws.cell(row=table_header_row, column=data_start_col, value="Fecha")

        for ds_idx, ds in enumerate(ordered_ds):
            col_c = data_start_col + 1 + ds_idx
            ws.cell(row=table_header_row, column=col_c, value=ds.label)

        for r_offset, lbl in enumerate(labels, start=1):
            r_num = table_header_row + r_offset
            ws.cell(row=r_num, column=data_start_col, value=lbl)
            for ds_idx, ds in enumerate(ordered_ds):
                col_c = data_start_col + 1 + ds_idx
                val = ds.data[r_offset - 1] if (ds.data and r_offset - 1 < len(ds.data)) else None
                num_val = _try_float(val)
                ws.cell(row=r_num, column=col_c, value=num_val)

        end_data_row = table_header_row + n_dates
        cats_ref = Reference(
            ws,
            min_col=data_start_col,
            min_row=table_header_row + 1,
            max_row=end_data_row,
        )

        # Crear gráfico principal (Eje Y izquierdo)
        chart_primary = LineChart()
        chart_primary.title = f"{c_def['title']} ({c_def['category']})"
        chart_primary.style = 10
        chart_primary.width = 18.5
        chart_primary.height = 10.5
        chart_primary.y_axis.title = c_def.get("y_title") or "Valor"
        chart_primary.x_axis.title = "Fecha de analítica"
        chart_primary.legend.position = "b"
        chart_primary.display_blanks = "span"

        primary_ref = Reference(
            ws,
            min_col=data_start_col + 1,
            min_row=table_header_row,
            max_col=data_start_col + len(primary_ds),
            max_row=end_data_row,
        )
        chart_primary.add_data(primary_ref, titles_from_data=True)
        chart_primary.set_categories(cats_ref)
        _apply_series_styles(chart_primary, primary_ds)

        # Si existen series en eje secundario (ej. HbA1c, eGFR, HOMA-IR, No-HDL, Plaquetas, T4L...), combinar en segundo eje Y
        if secondary_ds:
            chart_secondary = LineChart()
            chart_secondary.y_axis.axId = 200
            chart_secondary.y_axis.title = c_def.get("y1_title") or "Escala secundaria"
            chart_secondary.y_axis.majorGridlines = None
            chart_secondary.display_blanks = "span"

            sec_start_col = data_start_col + 1 + len(primary_ds)
            sec_end_col = sec_start_col + len(secondary_ds) - 1
            sec_ref = Reference(
                ws,
                min_col=sec_start_col,
                min_row=table_header_row,
                max_col=sec_end_col,
                max_row=end_data_row,
            )
            chart_secondary.add_data(sec_ref, titles_from_data=True)
            chart_secondary.set_categories(cats_ref)
            _apply_series_styles(chart_secondary, secondary_ds)

            chart_primary.y_axis.crosses = "autoZero"
            chart_secondary.y_axis.crosses = "max"
            chart_primary += chart_secondary

        # Posicionar en cuadrícula de 2 columnas (Columna A y Columna K, cada fila de gráficos ocupa 21 filas de alto)
        grid_row = idx_chart // 2
        grid_col = idx_chart % 2
        anchor_col_letter = "A" if grid_col == 0 else "K"
        anchor_row_num = 4 + (grid_row * 22)
        ws.add_chart(chart_primary, f"{anchor_col_letter}{anchor_row_num}")

        current_data_row = end_data_row + 3


def generate_clinical_excel_bytes(
    db: Session,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
) -> Tuple[bytes, str, str]:
    """
    Genera un archivo Excel (.xlsx) en memoria con tres hojas:
      1. Resumen (Tarjetas KPI actuales, variaciones, tendencias y otros valores de interés)
      2. Datos (Tabla completa del historial clínico con semáforos y promedios 18m)
      3. Gráficos (Gráficos evolutivos nativos de Excel)

    Retorna (contenido_bytes, fecha_inicio_efectiva, fecha_fin_efectiva).
    """
    if fecha_inicio and fecha_fin and str(fecha_inicio).strip() > str(fecha_fin).strip():
        raise ValueError("La fecha de inicio no puede ser posterior a la fecha de fin.")

    informes = _query_informes_filtered(db, fecha_inicio, fecha_fin)
    if not informes:
        raise ValueError("No existen analíticas registradas dentro del rango de fechas seleccionado.")

    eff_start = informes[0].fecha
    eff_end = informes[-1].fecha

    summary = get_dashboard_summary(fecha_inicio=eff_start, fecha_fin=eff_end, db=db)
    tables_data = get_tables(fecha_inicio=eff_start, fecha_fin=eff_end, db=db)
    charts_data = get_charts_data(fecha_inicio=eff_start, fecha_fin=eff_end, db=db)

    wb = Workbook()

    # 1. Hoja Resumen
    ws_resumen = wb.active
    ws_resumen.title = "Resumen"
    ws_resumen.sheet_properties.tabColor = COLOR_BLUE_600
    _build_resumen_sheet(ws_resumen, summary, eff_start, eff_end)

    # 2. Hoja Datos
    ws_datos = wb.create_sheet(title="Datos")
    ws_datos.sheet_properties.tabColor = COLOR_EMERALD_700
    _build_datos_sheet(ws_datos, tables_data, summary, eff_start, eff_end)

    # 3. Hoja Gráficos
    ws_graficos = wb.create_sheet(title="Gráficos")
    ws_graficos.sheet_properties.tabColor = "7C3AED"
    _build_graficos_sheet(ws_graficos, charts_data, eff_start, eff_end)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue(), eff_start, eff_end
