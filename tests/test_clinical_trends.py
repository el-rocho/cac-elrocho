import unittest
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.services.clinical_trends import (
    calcular_variacion_reciente,
    calcular_tendencia_longitudinal,
    interpretar_tendencia_clinica,
    evaluar_tendencia_global_tarjeta,
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
            for f in kpi["filas"]:
                self.assertIn("label", f)
                self.assertIn("val", f)
                self.assertIn("var_symbol", f)
                self.assertIn("trend_symbol", f)

if __name__ == "__main__":
    unittest.main()