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

        sym, delta_str, delta_num, is_sig = calcular_variacion_reciente(101.0, None, "GLUCOSE")
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
        from app.database import SessionLocal
        from app.models import AuditoriaRango

        # Snapshot de estados previos para no mutar los datos de desarrollo del usuario
        db_snap = SessionLocal()
        snapshot = []
        try:
            snapshot = [
                (a.id, a.estado, a.aplicado_en_historico, a.fecha_aplicacion)
                for a in db_snap.query(AuditoriaRango).all()
            ]
        finally:
            db_snap.close()

        client = TestClient(app)
        try:
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
        finally:
            # Restaurar exactamente el estado original de la base de datos
            db_restore = SessionLocal()
            try:
                for a_id, est, apl, f_app in snapshot:
                    a = db_restore.query(AuditoriaRango).filter_by(id=a_id).first()
                    if a:
                        a.estado = est
                        a.aplicado_en_historico = apl
                        a.fecha_aplicacion = f_app
                db_restore.commit()
            finally:
                db_restore.close()

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


    def test_basofilos_estandarizacion_y_edicion(self):
        """Verifica que los basófilos absolutos (y resto de diferenciales) se estandaricen correctamente sin multiplicarse a 40000."""
        from app.services.analito_normalizer import standardize_medicion, normalize_analito

        # 1. Normalización de analito por nombre
        cod, nom, cat, uni = normalize_analito("Basófilos Absolutos")
        self.assertEqual(cod, "BASOFILOS_ABS")
        self.assertEqual(uni, "/µL")

        cod2, _, _, _ = normalize_analito("Basófilos")
        self.assertEqual(cod2, "BASOFILOS_ABS")

        # 2. Valor 40 en /µL (edición manual o ya en /µL) debe permanecer 40 (¡nunca 40000!)
        num_val, clean_val, std_unit, std_ref = standardize_medicion("BASOFILOS_ABS", "40", "/µL", "0 - 200 /µL")
        self.assertEqual(num_val, 40.0)
        self.assertEqual(clean_val, "40")
        self.assertEqual(std_unit, "/µL")
        self.assertEqual(std_ref, "0 - 200 /µL")

        # 3. Artefacto histórico 40000 en /µL debe recuperarse a 40
        num_val, clean_val, std_unit, _ = standardize_medicion("BASOFILOS_ABS", "40000", "/µL", "0 - 200 /µL")
        self.assertEqual(num_val, 40.0)
        self.assertEqual(clean_val, "40")

        # 4. Valor 0.04 en 10^3/µL (formato del PDF Recoletas) debe convertirse a 40 /µL
        num_val, clean_val, std_unit, std_ref = standardize_medicion("BASOFILOS_ABS", "0.04", "10^3/µL", "0.0 - 0.2")
        self.assertEqual(num_val, 40.0)
        self.assertEqual(clean_val, "40")
        self.assertEqual(std_unit, "/µL")
        self.assertIn("200", std_ref)

        # 5. Valores reales como 50 y 60 en /µL deben conservarse intactos
        num_val50, clean50, _, _ = standardize_medicion("BASOFILOS_ABS", "50", "/µL")
        self.assertEqual(num_val50, 50.0)
        self.assertEqual(clean50, "50")

        num_val60, clean60, _, _ = standardize_medicion("BASOFILOS_ABS", "60", "/µL")
        self.assertEqual(num_val60, 60.0)
        self.assertEqual(clean60, "60")

        # 6. Eosinófilos con valor menor a 50 (ej: 30 /µL) no deben multiplicarse por 1000
        num_eos, clean_eos, _, _ = standardize_medicion("EOSINOFILOS_ABS", "30", "/µL")
        self.assertEqual(num_eos, 30.0)
        self.assertEqual(clean_eos, "30")

        # 7. Homogeneización basada en comparación de rangos de referencia (ref_ratio)
        # 7.1. Basófilos con rango en /L (ratio ~ 0.001): 40000 con ref 0 - 200000 /L -> 40 /µL, 0 - 200 /µL
        num_b_l, clean_b_l, unit_b_l, ref_b_l = standardize_medicion("BASOFILOS_ABS", "40000", "/L", "0 - 200000 /L")
        self.assertEqual(num_b_l, 40.0)
        self.assertEqual(clean_b_l, "40")
        self.assertEqual(unit_b_l, "/µL")
        self.assertIn("200", ref_b_l)

        # 7.2. Leucocitos con rango en /µL (ratio ~ 0.001): 7500 con ref 4000 - 11000 /µL -> 7.50 x10^3/µL
        num_leu, clean_leu, unit_leu, ref_leu = standardize_medicion("LEUCOCITOS", "7500", "/µL", "4000 - 11000 /µL")
        self.assertEqual(num_leu, 7.5)
        self.assertEqual(clean_leu, "7.50")
        self.assertEqual(unit_leu, "x10^3/µL")
        self.assertEqual(ref_leu, "4 - 11 x10^3/µL")

        # 7.3. Hemoglobina con rango en g/L (ratio ~ 0.1): 145 con ref 135 - 180 g/L -> 14.5 g/dL
        num_hb, clean_hb, unit_hb, ref_hb = standardize_medicion("HEMOGLOBINA", "145", "g/L", "135 - 180 g/L")
        self.assertEqual(num_hb, 14.5)
        self.assertEqual(clean_hb, "14.5")
        self.assertEqual(unit_hb, "g/dL")
        self.assertEqual(ref_hb, "13.5 - 18 g/dL")

        # 7.4. Proteínas Totales con rango en g/L (ratio ~ 0.1): 72 con ref 64 - 83 g/L -> 7.2 g/dL
        num_prot, clean_prot, unit_prot, ref_prot = standardize_medicion("PROTEINAS_TOTALES", "72", "g/L", "64 - 83 g/L")
        self.assertEqual(num_prot, 7.2)
        self.assertEqual(clean_prot, "7.2")
        self.assertEqual(unit_prot, "g/dL")
        self.assertEqual(ref_prot, "6.4 - 8.3 g/dL")

    def test_backup_export_import_and_summary(self):
        client = TestClient(app)
        # 1. Obtener summary inicial
        res = client.get("/api/v1/analiticas/summary")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("paciente", data)
        self.assertIn("kpis", data)
        self.assertIn("motor_llm_info", data)
        self.assertIn("total_controles", data)

        # 2. Exportar backup
        res_export = client.get("/api/v1/backup/export")
        self.assertEqual(res_export.status_code, 200)
        backup_content = res_export.content

        # 3. Importar backup
        files = {"file": ("backup.json", backup_content, "application/json")}
        res_import = client.post("/api/v1/backup/import", files=files)
        self.assertEqual(res_import.status_code, 200)

        # 4. Verificar que /summary responde con status 200 tras la importación
        res_after = client.get("/api/v1/analiticas/summary")
        self.assertEqual(res_after.status_code, 200)
        data_after = res_after.json()
        self.assertTrue(len(data_after["kpis"]) > 0)
        self.assertIsNotNone(data_after["paciente"]["nombre"])
        self.assertTrue(data_after["total_controles"] > 0)


if __name__ == "__main__":
    unittest.main()

