import unittest
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.services.clinical_trends import (
    calcular_variacion_reciente,
    calcular_tendencia_longitudinal,
    interpretar_tendencia_clinica,
    evaluar_tendencia_global_tarjeta,
    evaluar_tendencia_eje_tiroideo,
    CLINICAL_FAVORABLE,
    CLINICAL_ESTABLE,
    CLINICAL_DESFAVORABLE,
    CLINICAL_MIXTA,
    CLINICAL_SIN_TENDENCIA
)

class TestClinicalTrends(unittest.TestCase):

    def test_regresion_ols_ejemplo_usuario(self):
        # Determinaciones de HbA1c del ejemplo de la especificación
        puntos = [
            (date(2025, 1, 10), 5.3),
            (date(2025, 4, 20), 5.4),
            (date(2025, 11, 15), 5.6),
            (date(2026, 6, 25), 5.8),
        ]
        sym, slope, n = calcular_tendencia_longitudinal(puntos, fecha_referencia=date(2026, 6, 25), cod_analito="HBA1C")
        self.assertEqual(n, 4)
        self.assertEqual(sym, "↗")
        self.assertEqual(round(slope, 2), 0.34)
        
        # Interpretación clínica de HbA1c aumentando
        interp = interpretar_tendencia_clinica("HBA1C", sym, 5.8)
        self.assertEqual(interp, CLINICAL_DESFAVORABLE)

    def test_ventana_temporal_24_meses(self):
        # 1 punto antiguo (hace 3 años) y 3 puntos dentro de los 24 meses
        puntos = [
            (date(2023, 1, 1), 7.0),   # Fuera de ventana (hace > 24m de 2026-06-25)
            (date(2025, 1, 10), 5.3),  # Dentro
            (date(2025, 11, 15), 5.6), # Dentro
            (date(2026, 6, 25), 5.8),  # Dentro
        ]
        sym, slope, n = calcular_tendencia_longitudinal(puntos, fecha_referencia=date(2026, 6, 25), cod_analito="HBA1C")
        self.assertEqual(n, 3) # El punto de 2023 se excluye correctamente
        self.assertEqual(sym, "↗")

    def test_interpretacion_clinica_fisiologica(self):
        # LDL
        self.assertEqual(interpretar_tendencia_clinica("LDL", "↘", 100.0), CLINICAL_FAVORABLE)
        self.assertEqual(interpretar_tendencia_clinica("LDL", "↗", 130.0), CLINICAL_DESFAVORABLE)
        self.assertEqual(interpretar_tendencia_clinica("LDL", "→", 110.0), CLINICAL_ESTABLE)

        # HDL (subir es favorable)
        self.assertEqual(interpretar_tendencia_clinica("HDL", "↗", 55.0), CLINICAL_FAVORABLE)
        self.assertEqual(interpretar_tendencia_clinica("HDL", "↘", 38.0), CLINICAL_DESFAVORABLE)

        # eGFR (subir o mantener es favorable, caer es desfavorable)
        self.assertEqual(interpretar_tendencia_clinica("EGFR", "↗", 95.0), CLINICAL_FAVORABLE)
        self.assertEqual(interpretar_tendencia_clinica("EGFR", "↘", 55.0), CLINICAL_DESFAVORABLE)

        # Hemoglobina (anemia que sube es favorable)
        self.assertEqual(interpretar_tendencia_clinica("HEMOGLOBINA", "↗", 11.0), CLINICAL_FAVORABLE)
        self.assertEqual(interpretar_tendencia_clinica("HEMOGLOBINA", "↘", 11.0), CLINICAL_DESFAVORABLE)

    def test_variacion_reciente_umbrales(self):
        sym, delta_str, delta_num, is_sig = calcular_variacion_reciente(101.0, 95.0, "GLUCOSE")
        self.assertIsNone(sym)
        self.assertEqual(delta_str, "+6")
        self.assertTrue(is_sig)

        sym, delta_str, delta_num, is_sig = calcular_variacion_reciente(101.0, 102.0, "GLUCOSE")
        self.assertIsNone(sym)
        self.assertEqual(delta_str, "")
        self.assertFalse(is_sig)

        sym, delta_str, delta_num, is_sig = calcular_variacion_reciente(5.2, 5.6, "HBA1C")
        self.assertIsNone(sym)
        self.assertEqual(delta_str, "-0.4")
        self.assertTrue(is_sig)

    def test_algoritmo_tendencia_global(self):
        # Caso Mixta
        res, b_text, _ = evaluar_tendencia_global_tarjeta({
            "GLUCOSE": CLINICAL_DESFAVORABLE,
            "HBA1C": CLINICAL_FAVORABLE,
            "RATIO_TG_HDL": CLINICAL_ESTABLE
        }, "metabolismo_glucidico")
        self.assertEqual(res, "mixta")
        self.assertEqual(b_text, CLINICAL_MIXTA)

        # Caso Favorable
        res, b_text, _ = evaluar_tendencia_global_tarjeta({
            "GLUCOSE": CLINICAL_ESTABLE,
            "HBA1C": CLINICAL_FAVORABLE,
            "RATIO_TG_HDL": CLINICAL_DESFAVORABLE
        }, "metabolismo_glucidico")
        self.assertEqual(res, "favorable")
        self.assertEqual(b_text, CLINICAL_FAVORABLE)

        # Caso Principales estables -> secundarios deciden
        res, b_text, _ = evaluar_tendencia_global_tarjeta({
            "GLUCOSE": CLINICAL_ESTABLE,
            "HBA1C": CLINICAL_ESTABLE,
            "RATIO_TG_HDL": CLINICAL_DESFAVORABLE
        }, "metabolismo_glucidico")
        self.assertEqual(res, "desfavorable")
        self.assertEqual(b_text, CLINICAL_DESFAVORABLE)

        # Caso Sin datos suficientes en ventana de 24 meses
        res, b_text, _ = evaluar_tendencia_global_tarjeta({}, "metabolismo_glucidico")
        self.assertEqual(res, "sin_tendencia")
        self.assertEqual(b_text, CLINICAL_SIN_TENDENCIA)

    def test_api_summary_endpoint(self):
        client = TestClient(app)
        response = client.get("/api/v1/analiticas/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("kpis", data)
        self.assertEqual(len(data["kpis"]), 6)

        for kpi in data["kpis"]:
            self.assertIn("filas", kpi)
            self.assertIn("trend_global", kpi)
            self.assertIn("trend_badge_text", kpi)
            self.assertIn("trend_badge_class", kpi)
            self.assertIn("notas_pie", kpi)
            for f in kpi["filas"]:
                self.assertIn("label", f)
                self.assertIn("val", f)
                self.assertIn("var_symbol", f)
                self.assertIn("trend_symbol", f)

    def test_analitos_historicos_y_notas_pie(self):
        client = TestClient(app)
        response = client.get("/api/v1/analiticas/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        kpis_by_title = {k["title"]: k for k in data["kpis"]}

        # Comprobación de analitos históricos y notas al pie:
        # En Hemograma / Hierro, Ferritina o Hierro son históricos y rescatan datos previos con notas al pie
        hemo = kpis_by_title.get("Hemograma / Hierro")
        self.assertIsNotNone(hemo)
        filas_hemo = {f["label"]: f for f in hemo["filas"]}
        self.assertIn("Ferritina", filas_hemo)
        self.assertTrue(filas_hemo["Ferritina"]["es_historico"])
        self.assertIsNotNone(filas_hemo["Ferritina"]["footnote_symbol"])
        self.assertTrue(len(hemo["notas_pie"]) >= 1)
        self.assertEqual(hemo["notas_pie"][0]["simbolo"], filas_hemo["Ferritina"]["footnote_symbol"])

        # Tarjeta Función Tiroidea: T4 Libre está presente (como histórico o actual según el último informe)
        tiroides = kpis_by_title.get("Función Tiroidea")
        self.assertIsNotNone(tiroides)
        filas_tiro = {f["label"]: f for f in tiroides["filas"]}
        self.assertIn("T4 Libre", filas_tiro)
        if filas_tiro["T4 Libre"]["es_historico"]:
            self.assertEqual(len(tiroides["notas_pie"]), 1)
        else:
            self.assertFalse(filas_tiro["T4 Libre"]["es_historico"])
            self.assertTrue(len(filas_tiro["T4 Libre"]["val"]) > 0)

        # Tarjeta Función Hepática:
        # Debe incluir Albúmina, Tiempo Protrombina e INR diferenciados entre sus filas
        hep = kpis_by_title.get("Función Hepática")
        self.assertIsNotNone(hep)
        filas_hep = {f["label"]: f for f in hep["filas"]}
        self.assertIn("Albúmina", filas_hep)
        self.assertIn("Tiempo Protrombina", filas_hep)
        self.assertTrue(len(filas_hep["Tiempo Protrombina"]["val"]) > 0)
        self.assertEqual(filas_hep["Tiempo Protrombina"]["unit"], "s")
        self.assertIn("INR", filas_hep)
        self.assertTrue(len(filas_hep["INR"]["val"]) > 0)

    def test_normalizacion_igg_y_ratio_psa(self):
        """Verifica la correcta normalización del bloque de proteínas séricas (IGG) y Ratio PSA."""
        from app.services.analito_normalizer import normalize_analito, get_analito_group
        
        # Inmunoglobulina IgG (incluyendo errata común de Megalab 'Inmumoglobulina')
        cod_igg1, nom_igg1, cat_igg1, unit_igg1 = normalize_analito("Inmumoglobulina IgG", "mg/dL", "994")
        self.assertEqual(cod_igg1, "IGG")
        self.assertEqual(nom_igg1, "Inmunoglobulina IgG")
        self.assertEqual(cat_igg1, "inmunologia")
        self.assertEqual(unit_igg1, "mg/dL")

        cod_igg2, nom_igg2, _, _ = normalize_analito("Inmunoglobulina IgG", "mg/dL", "994")
        self.assertEqual(cod_igg2, "IGG")

        # Ratio PSA Libre / Total
        cod_ratio, nom_ratio, cat_ratio, unit_ratio = normalize_analito("Ratio PSA-Libre/PSA-total", "", "0.54")
        self.assertEqual(cod_ratio, "RATIO_PSA_L_T")
        self.assertEqual(nom_ratio, "Ratio PSA Libre / Total")
        self.assertEqual(cat_ratio, "bioquimica")

        # Comprobar que PSA Libre y PSA Total no colisionan con el ratio
        cod_psa_l, _, _, _ = normalize_analito("PSA-Fracción Libre", "ng/mL", "0.30")
        self.assertEqual(cod_psa_l, "PSA_FREE")

        cod_psa_t, _, _, _ = normalize_analito("PSA-Antígeno Prostático Específico", "ng/mL", "0.56")
        self.assertEqual(cod_psa_t, "PSA_TOTAL")

        # Grupos clínicos
        self.assertEqual(get_analito_group("IGG"), "🌸 Alergología e Inmunología")
        self.assertEqual(get_analito_group("RATIO_PSA_L_T"), "🔬 Marcadores Tumorales")

    def test_normalizacion_calcio_corregido_y_beta2_microglobulina(self):
        """Verifica la correcta normalización de Calcio Corregido (con Albúmina) y Beta-2 Microglobulina."""
        from app.services.analito_normalizer import normalize_analito, get_analito_group
        
        # Calcio corregido vs Albúmina vs Calcio Total
        cod_calc_corr, nom_calc_corr, cat_cc, unit_cc = normalize_analito("Calcio corregido con Albúmina", "mg/dL", "9.50")
        self.assertEqual(cod_calc_corr, "CALCIO_CORREGIDO")
        self.assertEqual(nom_calc_corr, "Calcio Corregido")
        self.assertEqual(cat_cc, "bioquimica")
        self.assertEqual(unit_cc, "mg/dL")

        cod_alb, nom_alb, cat_alb, unit_alb = normalize_analito("Albúmina", "", "4.5")
        self.assertEqual(cod_alb, "ALBUMINA")
        self.assertEqual(nom_alb, "Albúmina")
        self.assertEqual(cat_alb, "bioquimica")

        cod_calc_tot, nom_calc_tot, _, _ = normalize_analito("Calcio Total", "mg/dL", "9.9")
        self.assertEqual(cod_calc_tot, "CALCIO_TOTAL")

        # Beta-2 Microglobulina suero
        cod_b2m, nom_b2m, cat_b2m, unit_b2m = normalize_analito("Beta-2 Microglobulina suero", "mcg/mL", "1.85")
        self.assertEqual(cod_b2m, "BETA_2_MICROGLOBULINA")
        self.assertEqual(nom_b2m, "Beta-2 Microglobulina")
        self.assertEqual(cat_b2m, "inmunologia")
        self.assertEqual(unit_b2m, "mcg/mL")

        # Grupos clínicos
        self.assertEqual(get_analito_group("CALCIO_CORREGIDO"), "⚡ Enzimas Hepáticas e Iones Séricos")
        self.assertEqual(get_analito_group("BETA_2_MICROGLOBULINA"), "🌸 Alergología e Inmunología")

    def test_normalizacion_autoinmunidad_anti_ccp_y_ana(self):
        """Verifica la correcta normalización de Anticuerpos Anti-CCP y Anticuerpos Anti-Nucleares (ANA)."""
        from app.services.analito_normalizer import normalize_analito, get_analito_group, normalize_valor_numerico

        # Anti-CCP (nombre largo partido en PDF y técnica entre paréntesis)
        cod_ccp, nom_ccp, cat_ccp, unit_ccp = normalize_analito(
            "Anticuerpos Anti-Peptido Ciclico Citrulinado (CCP)", "UI/mL", "1.2"
        )
        self.assertEqual(cod_ccp, "ANTI_CCP")
        self.assertEqual(nom_ccp, "Anticuerpos Anti-CCP")
        self.assertEqual(cat_ccp, "inmunologia")
        self.assertEqual(unit_ccp, "UI/mL")

        # Valor numérico normalizado de Anti-CCP
        num_ccp, clean_ccp = normalize_valor_numerico(cod_ccp, "1.2", unit_ccp)
        self.assertEqual(num_ccp, 1.2)
        self.assertEqual(clean_ccp, "1.2")

        # ANA (valor textual 'No se detectan')
        cod_ana, nom_ana, cat_ana, unit_ana = normalize_analito(
            "Anticuerpos Anti-Nucleares (ANA)", "", "No se detectan"
        )
        self.assertEqual(cod_ana, "ANA")
        self.assertEqual(nom_ana, "Anticuerpos Anti-Nucleares (ANA)")
        self.assertEqual(cat_ana, "inmunologia")

        num_ana, clean_ana = normalize_valor_numerico(cod_ana, "No se detectan", unit_ana)
        self.assertIsNone(num_ana)
        self.assertEqual(clean_ana, "No se detectan")

        # Grupos clínicos
        self.assertEqual(get_analito_group("ANTI_CCP"), "🌸 Alergología e Inmunología")
        self.assertEqual(get_analito_group("ANA"), "🌸 Alergología e Inmunología")

    def test_normalizacion_idh_y_vpm(self):
        """Verifica la normalización de IDH/RDW y VPM, sus sinónimos y su configuración clínica."""
        from app.services.analito_normalizer import normalize_analito, get_analito_group, normalize_valor_numerico
        from app.services.clinical_trends import ANALITO_CONFIG

        # IDH -> RDW
        cod_idh, nom_idh, cat_idh, unit_idh = normalize_analito("IDH", "%", "12.0")
        self.assertEqual(cod_idh, "RDW")
        self.assertEqual(nom_idh, "RDW")
        self.assertEqual(cat_idh, "hemograma")
        self.assertEqual(unit_idh, "%")

        # Sinónimos de RDW
        for alias in ["Índice de Distribución de Hematíes", "IDE", "ADE", "RDW-CV"]:
            cod, nom, cat, _ = normalize_analito(alias, "%", "12.5")
            self.assertEqual(cod, "RDW")
            self.assertEqual(nom, "RDW")
            self.assertEqual(cat, "hemograma")

        # VPM -> VPM
        cod_vpm, nom_vpm, cat_vpm, unit_vpm = normalize_analito("VPM", "fL", "7.3")
        self.assertEqual(cod_vpm, "VPM")
        self.assertEqual(nom_vpm, "VPM")
        self.assertEqual(cat_vpm, "hemograma")
        self.assertEqual(unit_vpm, "fL")

        # Sinónimos de VPM
        for alias in ["Volumen Plaquetar Medio", "MPV"]:
            cod, nom, cat, _ = normalize_analito(alias, "fl", "8.5")
            self.assertEqual(cod, "VPM")
            self.assertEqual(nom, "VPM")
            self.assertEqual(cat, "hemograma")

        # Normalización numérica
        num_idh, clean_idh = normalize_valor_numerico("RDW", "12,0", "%")
        self.assertEqual(num_idh, 12.0)
        self.assertEqual(clean_idh, "12,0")

        num_vpm, clean_vpm = normalize_valor_numerico("VPM", "7.3", "fL")
        self.assertEqual(num_vpm, 7.3)
        self.assertEqual(clean_vpm, "7.3")

        # Grupos clínicos
        self.assertEqual(get_analito_group("RDW"), "🩸 Hemograma y Serie Hematológica")
        self.assertEqual(get_analito_group("VPM"), "🩸 Hemograma y Serie Hematológica")

        # Configuración clínica en ANALITO_CONFIG
        self.assertIn("RDW", ANALITO_CONFIG)
        self.assertIn("VPM", ANALITO_CONFIG)
        self.assertEqual(ANALITO_CONFIG["RDW"]["unit"], "%")
        self.assertEqual(ANALITO_CONFIG["VPM"]["unit"], "fL")

    def test_estandarizacion_unidades_y_rangos(self):
        """Verifica la estandarización matemática de unidades y rangos (linfocitos, leucocitos, hematíes, plaquetas, etc.)."""
        from app.services.analito_normalizer import standardize_medicion
        from app.services.clinical_trends import ANALITO_CONFIG

        # 1. Linfocitos en x10^3/µL convertidos a /µL (e.g. Recoletas 2024-06-22)
        val_num, clean_val, canon_unit, ref_range = standardize_medicion(
            "LINFOCITOS_ABS", "1,59", "10^3/µL", "1.1 - 4.5"
        )
        self.assertEqual(val_num, 1590.0)
        self.assertEqual(clean_val, "1590")
        self.assertEqual(canon_unit, "/µL")
        self.assertIn("1100", ref_range)
        self.assertIn("4500", ref_range)

        # 1b. Linfocitos que ya venían en /µL (e.g. Megalab)
        val_num, clean_val, canon_unit, ref_range = standardize_medicion(
            "LINFOCITOS_ABS", "1740", "/µL", "1100 - 4500"
        )
        self.assertEqual(val_num, 1740.0)
        self.assertEqual(canon_unit, "/µL")
        self.assertEqual(ref_range, "1100 - 4500")

        # 2. Otros diferenciales leucocitarios (Neutrófilos, Monocitos, Eosinófilos, Basófilos)
        val_num, clean_val, canon_unit, _ = standardize_medicion("NEUTROFILOS_ABS", "1.79", "x10^3/µL")
        self.assertEqual(val_num, 1790.0)
        self.assertEqual(canon_unit, "/µL")

        val_num, clean_val, canon_unit, _ = standardize_medicion("MONOCITOS_ABS", "0.27", "10^3/µL")
        self.assertEqual(val_num, 270.0)
        self.assertEqual(canon_unit, "/µL")

        val_num, clean_val, canon_unit, _ = standardize_medicion("EOSINOFILOS_ABS", "0.13", "10^3/µL")
        self.assertEqual(val_num, 130.0)
        self.assertEqual(canon_unit, "/µL")

        val_num, clean_val, canon_unit, _ = standardize_medicion("BASOFILOS_ABS", "0.06", "10^3/µL")
        self.assertEqual(val_num, 60.0)
        self.assertEqual(canon_unit, "/µL")

        # 3. Leucocitos totales (deben estar en x10^3/µL)
        # Si venían en /µL con valor entero 6590
        val_num, clean_val, canon_unit, ref_range = standardize_medicion(
            "LEUCOCITOS", "6590", "/µL", "4000 - 10000"
        )
        self.assertEqual(val_num, 6.59)
        self.assertEqual(clean_val, "6.59")
        self.assertEqual(canon_unit, "x10^3/µL")
        self.assertIn("4", ref_range)
        self.assertIn("10", ref_range)

        # Si ya venían en miles con etiqueta /µL por error del lab (8.63)
        val_num, clean_val, canon_unit, _ = standardize_medicion("LEUCOCITOS", "8.63", "/µL")
        self.assertEqual(val_num, 8.63)
        self.assertEqual(canon_unit, "x10^3/µL")

        # 4. Hematíes con formato español de punto de miles (5.070.000 /µL -> 5.07 x10^6/µL)
        val_num, clean_val, canon_unit, ref_range = standardize_medicion(
            "HEMATIES", "5.070.000", "/µL", "4.600.000 - 6.200.000"
        )
        self.assertEqual(val_num, 5.07)
        self.assertEqual(clean_val, "5.07")
        self.assertEqual(canon_unit, "x10^6/µL")
        self.assertIn("4.6", ref_range)
        self.assertIn("6.2", ref_range)

        # 5. Plaquetas (235000 /µL -> 235 x10^3/µL)
        val_num, clean_val, canon_unit, ref_range = standardize_medicion(
            "PLAQUETAS", "235000", "/µL", "150000 - 450000"
        )
        self.assertEqual(val_num, 235.0)
        self.assertEqual(clean_val, "235")
        self.assertEqual(canon_unit, "x10^3/µL")

        # 6. Proteínas en g/L -> g/dL
        val_num, clean_val, canon_unit, ref_range = standardize_medicion(
            "ALBUMINA", "45", "g/L", "35 - 50"
        )
        self.assertEqual(val_num, 4.5)
        self.assertEqual(clean_val, "4.5")
        self.assertEqual(canon_unit, "g/dL")

        # 7. Configuración clínica de analitos en ANALITO_CONFIG
        self.assertIn("HEMATIES", ANALITO_CONFIG)
        self.assertIn("LINFOCITOS_ABS", ANALITO_CONFIG)
        self.assertIn("NEUTROFILOS_ABS", ANALITO_CONFIG)
        self.assertEqual(ANALITO_CONFIG["LINFOCITOS_ABS"]["unit"], "/µL")
        self.assertEqual(ANALITO_CONFIG["HEMATIES"]["unit"], "x10^6/µL")

    def test_auditoria_rangos_y_tabla_metadatos(self):
        """Verifica el parseo de límites de referencia, evaluación de semáforos y auditoría de rangos."""
        from app.services.analito_normalizer import parse_reference_bounds, evaluar_estado_semaforo

        # 1. Parseo de límites
        self.assertEqual(parse_reference_bounds("17.4 - 49.2"), (17.4, 49.2))
        self.assertEqual(parse_reference_bounds("< 116 mg/dL"), (None, 116.0))
        self.assertEqual(parse_reference_bounds("> 40 mg/dL"), (40.0, None))
        self.assertEqual(parse_reference_bounds("Inf. 40"), (None, 40.0))

        # 2. Evaluación semafórica
        self.assertEqual(evaluar_estado_semaforo(46.7, "17.4 - 49.2"), "Normal")
        self.assertEqual(evaluar_estado_semaforo(49.0, "15 - 45"), "Alto")
        self.assertEqual(evaluar_estado_semaforo(12.0, "17.4 - 49.2"), "Bajo")
        self.assertEqual(evaluar_estado_semaforo(95.0, "< 116"), "Normal")
        self.assertEqual(evaluar_estado_semaforo(120.0, "< 116"), "Alto")

        # 3. Endpoint de detección de auditorías y tabla enriquecida con celdas
        client = TestClient(app)
        res_det = client.post("/api/v1/ai/detectar")
        self.assertEqual(res_det.status_code, 200)
        self.assertTrue(res_det.json()["total_detectados"] > 0)

        res_tables = client.get("/api/v1/analiticas/tables")
        self.assertEqual(res_tables.status_code, 200)
        tables_data = res_tables.json()
        urea_row = next((r for r in tables_data["bioquimica"] if r["name"] == "Urea"), None)
        self.assertIsNotNone(urea_row)
        self.assertEqual(urea_row["ref"], "17.4 - 49.2")
        self.assertIsNotNone(urea_row.get("cells"))
        self.assertEqual(len(urea_row["cells"]), len(urea_row["vals"]))

        # Verificar que la última medición (36.4) es Normal en su celda
        last_cell = urea_row["cells"][-1]
        self.assertEqual(last_cell["val"], 36.4)
        self.assertEqual(last_cell["ref"], "17.4 - 49.2")
        self.assertEqual(last_cell["status"], "Normal")
        self.assertFalse(last_cell["is_altered"])

    def test_evaluacion_unificada_dashboard_kpis(self):
        """Verifica que las tarjetas KPI del dashboard y otros valores se evalúen según el rango del laboratorio."""
        from app.services.analito_normalizer import es_medicion_alterada

        # 1. Pruebas directas de la función unificada
        self.assertFalse(es_medicion_alterada(97.7, "80.0 - 99.0", "Normal"))
        self.assertTrue(es_medicion_alterada(101.5, "80.0 - 99.0", "Normal"))
        self.assertFalse(es_medicion_alterada(46.7, "17.4 - 49.2", "Normal"))
        self.assertTrue(es_medicion_alterada(52.0, "17.4 - 49.2", "Normal"))
        self.assertFalse(es_medicion_alterada(95.0, "< 116", "Optimo"))
        self.assertTrue(es_medicion_alterada(130.0, "< 116", "Alto"))

        # 2. Evaluación a través de la API del dashboard
        client = TestClient(app)
        res = client.get("/api/v1/analiticas/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        kpis = {k["id"]: k for k in data["kpis"]}
        self.assertIn("hemograma_hierro", kpis)
        self.assertIn("funcion_renal", kpis)

        # En la última analítica, VCM es 92.8 y su rango del laboratorio es 80.0 - 99.0
        # No debe aparecer alterado
        card_hemo = kpis["hemograma_hierro"]
        vcm_fila = next((f for f in card_hemo["filas"] if f["codigo"] == "VCM"), None)
        self.assertIsNotNone(vcm_fila)
        self.assertEqual(vcm_fila["val"], "92.8")
        self.assertFalse(vcm_fila["is_altered"], "VCM 92.8 dentro del rango 80-99 no debe estar alterado")

        # En la última analítica, Urea es 46.7 y su rango del laboratorio es 17.4 - 49.2
        card_renal = kpis["funcion_renal"]
        urea_fila = next((f for f in card_renal["filas"] if f["codigo"] == "UREA"), None)
        self.assertIsNotNone(urea_fila)
        self.assertFalse(urea_fila["is_altered"], "Urea 46.7 dentro del rango 17.4 - 49.2 no debe estar alterada")

        # Verificar otros valores (ej. PSA)
        otros = {o["id"]: o for o in data["otros_valores"]}
        if "prostata" in otros:
            psa_items = {i["label"]: i for i in otros["prostata"]["items"]}
            if "PSA Total" in psa_items:
                self.assertFalse(psa_items["PSA Total"]["is_altered"])

    def test_egfr_calculado_edad_analitica(self):
        """Verifica que eGFR se calcule con la edad en la fecha de cada analítica y se refleje en KPI y Tablas."""
        from app.services.analito_normalizer import calcular_edad_en_fecha
        from app.api.analiticas import calcular_egfr

        # 1. Edad exacta a la fecha de la analítica (64 años en 2024-09-17)
        edad_2024 = calcular_edad_en_fecha("1960-07-05", "2024-09-17")
        self.assertEqual(edad_2024, 64)

        # 2. Cálculo CKD-EPI para creatinina 0.95 mg/dL en varón de 64 años
        egfr_calc = calcular_egfr(0.95, edad_2024, "Masculino")
        self.assertEqual(egfr_calc, 89.4)

        # 3. Comprobar que en la tarjeta KPI Función Renal figure con nombre "eGFR" y valor correspondiente a la última analítica
        client = TestClient(app)
        res_sum = client.get("/api/v1/analiticas/summary")
        self.assertEqual(res_sum.status_code, 200)
        kpis = {k["id"]: k for k in res_sum.json()["kpis"]}
        card_renal = kpis["funcion_renal"]
        egfr_fila = next((f for f in card_renal["filas"] if f["codigo"] == "EGFR"), None)
        self.assertIsNotNone(egfr_fila)
        self.assertEqual(egfr_fila["label"], "eGFR")
        self.assertEqual(egfr_fila["val"], "90.5")
        self.assertFalse(egfr_fila["is_altered"])

        # 4. Comprobar que en el Historial de Resultados (Tablas) figure la fila de eGFR con el histórico
        res_tab = client.get("/api/v1/analiticas/tables")
        self.assertEqual(res_tab.status_code, 200)
        tables_data = res_tab.json()
        egfr_row = next((r for r in tables_data["bioquimica"] if "eGFR" in r["name"] or "Filtrado" in r["name"]), None)
        self.assertIsNotNone(egfr_row)
        self.assertEqual(egfr_row["cells"][-1]["val"], 90.5)
        self.assertFalse(egfr_row["cells"][-1]["is_altered"])

    def test_historico_ldl_estados_normales(self):
        client = TestClient(app)
        res = client.get("/api/v1/analiticas/tables")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        ldl_row = next((r for r in data["bioquimica"] if r["name"] == "LDL-Colesterol"), None)
        self.assertIsNotNone(ldl_row)
        # Comprobar que los valores históricos de 119 y 113 no están marcados como alterados
        for cell in ldl_row["cells"]:
            if cell["val"] in [119.0, 113.0]:
                self.assertFalse(cell["is_altered"], f"El valor {cell['val']} no debería estar marcado como alterado con ref {cell['ref']}")
                self.assertEqual(cell["status"], "Óptimo")

    def test_auditoria_mantener_historico_y_estados(self):
        """Verifica los endpoints de mantener rangos históricos y la persistencia de estados de revisión."""
        client = TestClient(app)

        # 1. Asegurar detección de auditorías
        res_det = client.post("/api/v1/ai/detectar")
        self.assertEqual(res_det.status_code, 200)

        # 2. Consultar lista y verificar campos
        res_list = client.get("/api/v1/ai/auditorias")
        self.assertEqual(res_list.status_code, 200)
        items = res_list.json()
        self.assertTrue(len(items) > 0)

        first_audit = items[0]
        self.assertIn("estado", first_audit)
        self.assertIn(first_audit["estado"], ["pendiente", "aplicado", "mantenido"])
        audit_id = first_audit["id"]

        # 3. Mantener rangos históricos
        res_mant = client.post(f"/api/v1/ai/mantener-historico/{audit_id}")
        self.assertEqual(res_mant.status_code, 200)
        mant_data = res_mant.json()
        self.assertEqual(mant_data["status"], "success")
        self.assertEqual(mant_data["estado"], "mantenido")

        # 4. Comprobar que en la lista figure como 'mantenido' y no aplicado
        res_list2 = client.get("/api/v1/ai/auditorias")
        item_updated = next((x for x in res_list2.json() if x["id"] == audit_id), None)
        self.assertIsNotNone(item_updated)
        self.assertEqual(item_updated["estado"], "mantenido")
        self.assertFalse(item_updated["aplicado_en_historico"])

        # 5. Cambiar decisión a aplicar criterio al historial
        res_app = client.post(f"/api/v1/ai/aplicar-criterio/{audit_id}")
        self.assertEqual(res_app.status_code, 200)
        app_data = res_app.json()
        self.assertEqual(app_data["status"], "success")
        self.assertEqual(app_data["estado"], "aplicado")

        res_list3 = client.get("/api/v1/ai/auditorias")
        item_applied = next((x for x in res_list3.json() if x["id"] == audit_id), None)
        self.assertIsNotNone(item_applied)
        self.assertEqual(item_applied["estado"], "aplicado")
        self.assertTrue(item_applied["aplicado_en_historico"])

        # 6. Probar endpoint de mantener todos los pendientes
        res_all_mant = client.post("/api/v1/ai/mantener-todos")
        self.assertEqual(res_all_mant.status_code, 200)
        self.assertEqual(res_all_mant.json()["status"], "success")

        # 7. Limpieza para mantener estado inicial en la base de datos de desarrollo
        from app.database import SessionLocal
        from app.models import AuditoriaRango
        db = SessionLocal()
        try:
            db.query(AuditoriaRango).update({"estado": "pendiente", "aplicado_en_historico": False, "fecha_aplicacion": None})
            db.commit()
        finally:
            db.close()

    def test_tiroides_evaluacion_fisiologica_conjunta(self):
        """Verifica la evaluación fisiológica conjunta de TSH y T4 libre (relación inversa)."""
        # 1. Eutiroideo clínico normal (TSH y T4L en rango con leves fluctuaciones) -> ESTABLE
        state, badge, _ = evaluar_tendencia_eje_tiroideo(
            tsh_num=1.45, tsh_sym="↗", tsh_clin=CLINICAL_ESTABLE, tsh_alt=False,
            t4l_num=1.20, t4l_sym="↘", t4l_clin=CLINICAL_ESTABLE, t4l_alt=False
        )
        self.assertEqual(state, "estable")
        self.assertEqual(badge, CLINICAL_ESTABLE)

        # 2. Deriva recíproca hacia hipotiroidismo (TSH sube / alta, T4L baja / cae) -> DESFAVORABLE
        state, badge, _ = evaluar_tendencia_eje_tiroideo(
            tsh_num=5.80, tsh_sym="↗", tsh_clin=CLINICAL_DESFAVORABLE, tsh_alt=True,
            t4l_num=0.65, t4l_sym="↘", t4l_clin=CLINICAL_DESFAVORABLE, t4l_alt=True
        )
        self.assertEqual(state, "desfavorable")
        self.assertEqual(badge, CLINICAL_DESFAVORABLE)

        # 3. Deriva recíproca hacia hipertiroidismo (TSH suprimida en caída, T4L alta en ascenso) -> DESFAVORABLE
        state, badge, _ = evaluar_tendencia_eje_tiroideo(
            tsh_num=0.08, tsh_sym="↘", tsh_clin=CLINICAL_DESFAVORABLE, tsh_alt=True,
            t4l_num=2.10, t4l_sym="↗", t4l_clin=CLINICAL_DESFAVORABLE, t4l_alt=True
        )
        self.assertEqual(state, "desfavorable")
        self.assertEqual(badge, CLINICAL_DESFAVORABLE)

        # 4. Recuperación de hipotiroidismo hacia eutiroidismo (TSH desciende hacia normal, T4L sube hacia normal) -> FAVORABLE
        state, badge, _ = evaluar_tendencia_eje_tiroideo(
            tsh_num=4.80, tsh_sym="↘", tsh_clin=CLINICAL_FAVORABLE, tsh_alt=True,
            t4l_num=1.10, t4l_sym="↗", t4l_clin=CLINICAL_ESTABLE, t4l_alt=False
        )
        self.assertEqual(state, "favorable")
        self.assertEqual(badge, CLINICAL_FAVORABLE)

        # 5. Discordancia atípica (ambas en la misma dirección fuera de rango) -> MIXTA
        state, badge, _ = evaluar_tendencia_eje_tiroideo(
            tsh_num=5.50, tsh_sym="↗", tsh_clin=CLINICAL_DESFAVORABLE, tsh_alt=True,
            t4l_num=2.20, t4l_sym="↗", t4l_clin=CLINICAL_DESFAVORABLE, t4l_alt=True
        )
        self.assertEqual(state, "mixta")
        self.assertEqual(badge, CLINICAL_MIXTA)

    def test_tiroides_caracter_complementario_t3_y_anticuerpos(self):
        """Verifica que T3 libre y anticuerpos sean complementarios y no determinen valoración desfavorable."""
        # TSH y T4L normales; T3 libre con tendencia desfavorable aislada
        state, badge, _ = evaluar_tendencia_eje_tiroideo(
            tsh_num=1.32, tsh_sym="→", tsh_clin=CLINICAL_ESTABLE, tsh_alt=False,
            t4l_num=1.23, t4l_sym="→", t4l_clin=CLINICAL_ESTABLE, t4l_alt=False,
            t3l_num=1.80, t3l_sym="↘", t3l_clin=CLINICAL_DESFAVORABLE, t3l_alt=True
        )
        # Debe mantenerse ESTABLE, no desfavorable
        self.assertEqual(state, "estable")
        self.assertEqual(badge, CLINICAL_ESTABLE)

        # A través de evaluar_tendencia_global_tarjeta
        evals = {
            "TSH": CLINICAL_ESTABLE,
            "T4_LIBRE": CLINICAL_ESTABLE,
            "T3_LIBRE": CLINICAL_DESFAVORABLE,
            "ANTI_TPO": CLINICAL_DESFAVORABLE
        }
        res_state, res_badge, _ = evaluar_tendencia_global_tarjeta(evals, "tiroides")
        self.assertEqual(res_state, "estable")
        self.assertEqual(res_badge, CLINICAL_ESTABLE)

    def test_jerarquia_analitos_principales_y_secundarios_kpis(self):
        """Verifica que todas las tarjetas expongan es_principal y tipo_parametro en /summary."""
        client = TestClient(app)
        res = client.get("/api/v1/analiticas/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        kpis = {k["id"]: k for k in data["kpis"]}

        # Comprobar tarjeta de tiroides
        tiro = kpis.get("tiroides")
        self.assertIsNotNone(tiro)
        filas_tiro = {f["codigo"]: f for f in tiro["filas"]}

        # T4 Libre debe ser Principal
        self.assertIn("T4_LIBRE", filas_tiro)
        self.assertTrue(filas_tiro["T4_LIBRE"]["es_principal"])
        self.assertEqual(filas_tiro["T4_LIBRE"]["tipo_parametro"], "principal")

        # T3 Libre (si está presente) debe ser Secundario
        if "T3_LIBRE" in filas_tiro:
            self.assertFalse(filas_tiro["T3_LIBRE"]["es_principal"])
            self.assertEqual(filas_tiro["T3_LIBRE"]["tipo_parametro"], "secundario")

        # Comprobar tarjeta de lípidos
        lip = kpis.get("perfil_lipidico")
        self.assertIsNotNone(lip)
        filas_lip = {f["codigo"]: f for f in lip["filas"]}
        self.assertTrue(filas_lip["LDL"]["es_principal"])
        self.assertEqual(filas_lip["LDL"]["tipo_parametro"], "principal")
        self.assertFalse(filas_lip["HDL"]["es_principal"])
        self.assertEqual(filas_lip["HDL"]["tipo_parametro"], "secundario")

        # Comprobar tarjeta renal
        ren = kpis.get("funcion_renal")
        self.assertIsNotNone(ren)
        filas_ren = {f["codigo"]: f for f in ren["filas"]}
        self.assertTrue(filas_ren["EGFR"]["es_principal"])
        self.assertEqual(filas_ren["EGFR"]["tipo_parametro"], "principal")
        self.assertFalse(filas_ren["UREA"]["es_principal"])
        self.assertEqual(filas_ren["UREA"]["tipo_parametro"], "secundario")


if __name__ == "__main__":
    unittest.main()