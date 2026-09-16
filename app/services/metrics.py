from typing import Optional, Dict, Any, List

def calculate_ratios(mediciones_dict: Dict[str, float]) -> Dict[str, float]:
    """
    Calcula de forma automática los cocientes analíticos a partir de los valores basales.
    """
    ratios = {}
    col_total = mediciones_dict.get("CHOLESTEROL_TOTAL")
    hdl = mediciones_dict.get("HDL")
    ldl = mediciones_dict.get("LDL")
    tg = mediciones_dict.get("TRIGLYCERIDES")
    psa_t = mediciones_dict.get("PSA_TOTAL")
    psa_l = mediciones_dict.get("PSA_FREE")

    # Castelli I (Col Total / HDL) - solo si ambos son concentraciones séricas plausibles
    if col_total and hdl and hdl > 10 and col_total > 50:
        ratios["RATIO_COL_HDL"] = round(col_total / hdl, 2)

    # Castelli II (LDL / HDL)
    if ldl and hdl and hdl > 10 and ldl > 20:
        ratios["RATIO_LDL_HDL"] = round(ldl / hdl, 2)

    # Triglicéridos / HDL (Marcador de resistencia insulínica y aterogenia SEA)
    if tg and hdl and hdl > 10 and tg > 10:
        ratios["RATIO_TG_HDL"] = round(tg / hdl, 2)

    # Ratio LDL / Col Total
    if ldl and col_total and col_total > 50:
        ratios["RATIO_LDL_COL"] = round(ldl / col_total, 2)

    # Ratio HDL / Col Total
    if hdl and col_total and col_total > 50:
        ratios["RATIO_HDL_COL"] = round(hdl / col_total, 2)

    # Ratio TG / Col Total
    if tg and col_total and col_total > 50:
        ratios["RATIO_TG_COL"] = round(tg / col_total, 2)

    # Ratio PSA Libre / PSA Total
    if psa_t and psa_l and psa_t > 0:
        ratios["RATIO_PSA_L_T"] = round(psa_l / psa_t, 3)

    return ratios

def get_cell_format(name: str, val: Any) -> Dict[str, str]:
    """
    Replica con exactitud las reglas clínicas y de estilo semafórico
    definidas en el panel de control.
    """
    if val is None or val == "" or val == "-":
        return {"cls": "text-slate-300", "title": "Sin dato"}

    try:
        v = float(str(val).replace(",", ".").split()[0])
    except (ValueError, TypeError):
        return {"cls": "text-slate-800", "title": str(val)}

    # 1. HbA1c
    if name == "HbA1c":
        if v >= 5.7:
            return {"cls": "text-amber-800 bg-amber-100 border border-amber-300 font-bold px-1.5 py-0.5 rounded", "title": "Límite Prediabetes (>5.6%)"}
        if v >= 5.4:
            return {"cls": "text-slate-800 font-medium", "title": "Bueno / En rango"}
        return {"cls": "text-emerald-700 font-semibold", "title": "Óptimo"}

    # 1b. HbA1c (IFCC)
    if name == "HbA1c (IFCC)":
        if v >= 38.8:
            return {"cls": "text-amber-800 bg-amber-100 border border-amber-300 font-bold px-1.5 py-0.5 rounded", "title": "Límite Prediabetes (>=38.8)"}
        return {"cls": "text-emerald-700 font-semibold", "title": "Óptimo"}

    # 2. Glucosa Basal
    if name == "Glucosa Basal":
        if v > 100:
            return {"cls": "text-amber-800 bg-amber-100 border border-amber-300 font-bold px-1.5 py-0.5 rounded", "title": "Ligeramente alto / ADA alterada (>100)"}
        if v >= 96:
            return {"cls": "text-yellow-800 bg-yellow-50 border border-yellow-200 font-semibold px-1.5 py-0.5 rounded", "title": "Bueno / Próximo a 100"}
        return {"cls": "text-emerald-700 font-semibold", "title": "Excelente / Óptimo"}

    # 3. LDL-Colesterol
    if name == "LDL-Colesterol":
        if v > 116:
            return {"cls": "text-amber-800 bg-amber-100 border border-amber-300 font-bold px-1.5 py-0.5 rounded", "title": "Moderado / Sobrepasa ref. SEA (>116)"}
        if v >= 100:
            return {"cls": "text-yellow-800 bg-yellow-50 border border-yellow-200 font-medium px-1.5 py-0.5 rounded", "title": "Bueno / Límite intermedio"}
        return {"cls": "text-emerald-700 font-semibold", "title": "Óptimo"}

    # 4. Colesterol Total
    if name == "Colesterol Total":
        if v > 200:
            return {"cls": "text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded", "title": "Alto (>200)"}
        if v >= 180:
            return {"cls": "text-slate-800 font-bold", "title": "Bueno / Próximo a 200"}
        return {"cls": "text-emerald-700 font-semibold", "title": "Óptimo (<180)"}

    # 5. Cociente LDL/HDL (Castelli II: Ref < 4.3)
    if "Castelli II" in name or name in ["Cociente LDL/HDL", "LDL / HDL"]:
        if v > 4.3:
            return {"cls": "text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded", "title": "Riesgo Alto (>4.3)"}
        if v >= 3.0:
            return {"cls": "text-yellow-800 bg-yellow-50 border border-yellow-200 font-semibold px-1.5 py-0.5 rounded", "title": "Bueno / Límite intermedio"}
        return {"cls": "text-emerald-700 font-semibold", "title": "Óptimo (<3.0)"}

    # 6. Cociente Col/HDL (Castelli I: Ref < 5.0)
    if ("Castelli I" in name and "Castelli II" not in name) or name in ["Cociente Col/HDL", "Colesterol Total / HDL"]:
        if v > 5.0:
            return {"cls": "text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded", "title": "Riesgo Aumentado / Alto (>5.0)"}
        if v >= 4.0:
            return {"cls": "text-yellow-800 bg-yellow-50 border border-yellow-200 font-semibold px-1.5 py-0.5 rounded", "title": "Bueno / Límite (Óptimo <4.0)"}
        return {"cls": "text-emerald-700 font-semibold", "title": "Óptimo (<4.0)"}

    # 6b. Triglicéridos / HDL (Ref < 2.0)
    if name in ["Triglicéridos / HDL", "Cociente TG/HDL", "Ratio TG/HDL"]:
        if v > 2.0:
            return {"cls": "text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded", "title": "Elevado / Resistencia Insulínica (>2.0)"}
        if v >= 1.5:
            return {"cls": "text-yellow-800 bg-yellow-50 border border-yellow-200 font-semibold px-1.5 py-0.5 rounded", "title": "Bueno / Límite"}
        return {"cls": "text-emerald-700 font-semibold", "title": "Óptimo (<1.5)"}

    # 7. Ratio LDL / Col. Total
    if name == "Ratio LDL / Col. Total":
        if v > 0.65:
            return {"cls": "text-amber-800 bg-amber-100 border border-amber-300 font-bold px-1.5 py-0.5 rounded", "title": "Ligeramente Alto (>0.65)"}
        if v == 0.65:
            return {"cls": "text-yellow-800 bg-yellow-50 border border-yellow-200 font-semibold px-1.5 py-0.5 rounded", "title": "En límite exacto (0.65)"}
        return {"cls": "text-emerald-700 font-medium", "title": "Óptimo (<0.65)"}

    # 8. Ratio HDL / Col. Total
    if name == "Ratio HDL / Col. Total":
        if v >= 0.25:
            return {"cls": "text-emerald-700 font-bold", "title": "Excelente / Muy protector (>=25%)"}
        if v >= 0.20:
            return {"cls": "text-emerald-600 font-medium", "title": "Bueno / Protector (>=20%)"}
        return {"cls": "text-amber-800 bg-amber-100 font-bold px-1.5 py-0.5 rounded", "title": "Bajo (<20%)"}

    # 9. Ratio TG / Col. Total
    if name == "Ratio TG / Col. Total":
        if v <= 0.40:
            return {"cls": "text-emerald-700 font-bold", "title": "Excelente (<0.40)"}
        if v <= 0.50:
            return {"cls": "text-emerald-600 font-medium", "title": "Bueno (<0.50)"}
        return {"cls": "text-amber-800 bg-amber-100 font-bold px-1.5 py-0.5 rounded", "title": "Moderado (>0.50)"}

    # 10. Triglicéridos
    if name == "Triglicéridos":
        if v <= 100:
            return {"cls": "text-emerald-700 font-bold", "title": "Excelente (<100)"}
        if v <= 150:
            return {"cls": "text-slate-800 font-medium", "title": "Bueno (<150)"}
        return {"cls": "text-amber-800 bg-amber-100 font-bold px-1.5 py-0.5 rounded", "title": "Alto (>150)"}

    # 11. Urea
    if name == "Urea":
        if v > 49.2:
            return {"cls": "text-amber-800 bg-amber-100 font-bold px-1.5 py-0.5 rounded", "title": "Ligeramente Alto (>49.2)"}
        if v >= 45.0:
            return {"cls": "text-yellow-800 bg-yellow-50 border border-yellow-200 font-medium px-1.5 py-0.5 rounded", "title": "Bueno / Límite superior"}
        return {"cls": "text-emerald-700 font-medium", "title": "Óptimo"}

    # 12. Ácido Úrico
    if name == "Ácido Úrico":
        if v > 7.0:
            return {"cls": "text-amber-800 bg-amber-100 font-bold px-1.5 py-0.5 rounded", "title": "Alto (>7.0)"}
        if v >= 6.5:
            return {"cls": "text-yellow-800 font-medium", "title": "Bueno / Próximo a 7.0"}
        return {"cls": "text-emerald-700 font-medium", "title": "Óptimo"}

    # 13. Vitamina D (25-OH)
    if name == "Vitamina D (25-OH)":
        if v < 20:
            return {"cls": "text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded", "title": "Déficit (<20)"}
        if v < 30:
            return {"cls": "text-amber-800 bg-amber-100 border border-amber-300 font-bold px-1.5 py-0.5 rounded", "title": "Insuficiencia (20-29)"}
        if v <= 35:
            return {"cls": "text-emerald-800 bg-emerald-50 border border-emerald-300 font-semibold px-1.5 py-0.5 rounded", "title": "Bueno / Normalizada en dintel (30-35)"}
        return {"cls": "text-emerald-700 font-bold", "title": "Óptimo (>35)"}

    # 14. Dímero D
    if name == "Dímero D":
        if v > 500:
            return {"cls": "text-rose-800 bg-rose-100 font-bold px-1.5 py-0.5 rounded", "title": "Elevado (>500)"}
        return {"cls": "text-emerald-700 font-medium", "title": "Normal (<500)"}

    # 15. Calcio Total
    if name == "Calcio Total":
        if v > 10.2:
            return {"cls": "text-amber-800 bg-amber-100 font-bold px-1.5 py-0.5 rounded", "title": "Ligeramente Alto (>10.2)"}
        return {"cls": "text-emerald-700 font-medium", "title": "Normal"}

    # 16. T3 Total
    if name == "T3 Total":
        if v < 0.83:
            return {"cls": "text-blue-900 bg-blue-100 border border-blue-300 font-bold px-1.5 py-0.5 rounded", "title": "Ligeramente Bajo (<0.83)"}
        return {"cls": "text-emerald-700 font-medium", "title": "Normal"}

    # 17. BUN
    if name == "BUN":
        if v > 21:
            return {"cls": "text-amber-800 bg-amber-100 font-bold px-1.5 py-0.5 rounded", "title": "Ligeramente Alto (>21)"}

    # 18. PSA
    if name == "PSA Total":
        if v <= 1.0:
            return {"cls": "text-emerald-700 font-bold", "title": "Excelente (<1.0)"}
    if name == "Ratio PSA L/T":
        if v >= 0.25:
            return {"cls": "text-emerald-700 font-bold", "title": "Excelente (>25%)"}

    return {"cls": "text-slate-800", "title": "Normal"}
