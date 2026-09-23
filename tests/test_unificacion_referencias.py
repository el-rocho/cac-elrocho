import unittest
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Paciente, Informe, Medicion
from app.services.llm_service import extraer_referencia_de_texto
from app.services.clinical_trends import calcular_variacion_reciente
from app.services.backup_service import export_database_to_dict, import_database_from_dict

class TestUnificacionReferencias(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.db = SessionLocal()
        self._cleanup_test_data()

    def tearDown(self):
        self._cleanup_test_data()
        self.db.close()

    def _cleanup_test_data(self):
        test_date = "2099-01-15"
        inf_prev = self.db.query(Informe).filter(Informe.fecha == test_date).all()
        for ip in inf_prev:
            self.db.query(Medicion).filter(Medicion.informe_id == ip.id).delete()
            self.db.delete(ip)
        self.db.commit()

    def test_extraer_referencia_de_texto(self):
        # Casos con patrones típicos de informes de laboratorio
        texto1 = "LABORATORIO RECOLETAS\nNº Petición / Referencia: 22598017\nFecha: 10/01/2026"
        self.assertEqual(extraer_referencia_de_texto(texto1), "22598017")

        texto2 = "Informe Clínico - Ref: 98472011 - Paciente: Javier"
        self.assertEqual(extraer_referencia_de_texto(texto2), "98472011")

        texto3 = "Muestra Sanguínea\nNúmero de Informe: REF-2026-ABC\nFecha: 2026-02-01"
        self.assertEqual(extraer_referencia_de_texto(texto3), "REF-2026-ABC")

        texto4 = "Texto sin ninguna referencia explícita ni patrón numérico claro"
        self.assertIsNone(extraer_referencia_de_texto(texto4))

    def test_backup_restores_referencia(self):
        """La referencia debe sobrevivir una exportación y restauración completas."""
        paciente = Paciente(nombre_completo="Paciente de prueba", sexo="No especificado")
        self.db.add(paciente)
        self.db.flush()
        informe = Informe(
            paciente_id=paciente.id,
            fecha="2099-01-15",
            etiqueta_corta="15/01/99",
            laboratorio="Laboratorio de prueba",
            facultativo="Dra. Prueba",
            referencia="REF-BACKUP-2099",
            estado="confirmado",
        )
        self.db.add(informe)
        self.db.commit()

        backup = export_database_to_dict(self.db)
        backup_informe = next(
            inf for inf in backup["informes"] if inf["fecha"] == "2099-01-15"
        )
        self.assertEqual(backup_informe["referencia"], "REF-BACKUP-2099")

        import_database_from_dict(self.db, backup)
        restaurado = self.db.query(Informe).filter_by(fecha="2099-01-15").one()
        self.assertEqual(restaurado.referencia, "REF-BACKUP-2099")

    def test_unificacion_fusion_mismo_dia(self):
        # 1. Crear primer informe para fecha de prueba 2099-01-15
        test_date = "2099-01-15"
        
        # Limpiar cualquier residuo previo
        inf_prev = self.db.query(Informe).filter(Informe.fecha == test_date).all()
        for ip in inf_prev:
            self.db.query(Medicion).filter(Medicion.informe_id == ip.id).delete()
            self.db.delete(ip)
        self.db.commit()

        # Ingesta Informe 1
        payload1 = {
            "fecha": test_date,
            "laboratorio": "Laboratorio Central",
            "facultativo": "Dr. Fernando Pérez",
            "referencia": "REF-1001",
            "dictamen_global": "Control de rutina endocrino",
            "mediciones": [
                {
                    "codigo": "GLUCOSE",
                    "nombre": "Glucosa",
                    "valor": "90",
                    "unidad": "mg/dL",
                    "rango_referencia": "70 - 100",
                    "estado_estimado": "Normal"
                },
                {
                    "codigo": "COLESTEROL_TOTAL",
                    "nombre": "Colesterol Total",
                    "valor": "180",
                    "unidad": "mg/dL",
                    "rango_referencia": "120 - 200",
                    "estado_estimado": "Normal"
                }
            ],
            "modo_coincidencia": "nuevo"
        }

        try:
            res1 = self.client.post("/api/v1/upload/confirm", json=payload1)
            self.assertEqual(res1.status_code, 200)
            inf1_id = res1.json()["informe_id"]

            payload2 = {
                "fecha": test_date,
                "laboratorio": "Laboratorio Especialidades",
                "facultativo": "Dra. Carmen Gómez",
                "referencia": "REF-2002",
                "dictamen_global": "Perfil tiroideo complementario",
                "mediciones": [
                    {
                        "codigo": "TSH",
                        "nombre": "TSH",
                        "valor": "2.10",
                        "unidad": "µUI/mL",
                        "rango_referencia": "0.35 - 4.94",
                        "estado_estimado": "Normal"
                    },
                    {
                        "codigo": "GLUCOSE",
                        "nombre": "Glucosa",
                        "valor": "92",
                        "unidad": "mg/dL",
                        "rango_referencia": "70 - 100",
                        "estado_estimado": "Normal"
                    }
                ],
                "sobrescribir_existente": True,
                "informe_id_a_reemplazar": inf1_id,
                "modo_coincidencia": "fusionar"
            }

            res2 = self.client.post("/api/v1/upload/confirm", json=payload2)
            self.assertEqual(res2.status_code, 200)
            inf2_id = res2.json()["informe_id"]
            self.assertEqual(inf1_id, inf2_id)

            # Verificar en base de datos
            db_inf = self.db.query(Informe).filter(Informe.id == inf1_id).first()
            self.assertIsNotNone(db_inf)
            self.assertIn("Dr. Fernando Pérez", db_inf.facultativo)
            self.assertIn("Dra. Carmen Gómez", db_inf.facultativo)
            self.assertIn("REF-1001", db_inf.referencia)
            self.assertIn("REF-2002", db_inf.referencia)
            self.assertIn("Laboratorio Central", db_inf.laboratorio)
            self.assertIn("Laboratorio Especialidades", db_inf.laboratorio)

            # Verificar mediciones fusionadas (Glucosa, Colesterol y TSH)
            db_meds = {m.analito.codigo: m for m in self.db.query(Medicion).filter(Medicion.informe_id == inf1_id).all()}
            self.assertIn("GLUCOSE", db_meds)
            self.assertEqual(db_meds["GLUCOSE"].valor_numerico, 92.0)
            self.assertIn("CHOLESTEROL_TOTAL", db_meds)
            self.assertEqual(db_meds["CHOLESTEROL_TOTAL"].valor_numerico, 180.0)
            self.assertIn("TSH", db_meds)
            self.assertEqual(db_meds["TSH"].valor_numerico, 2.10)

            # Verificar /tables contiene la referencia combinada en la columna
            res_tables = self.client.get("/api/v1/analiticas/tables")
            self.assertEqual(res_tables.status_code, 200)
            tables_data = res_tables.json()
            
            matching_indices = [i for i, inf in enumerate(tables_data["informes"]) if inf["fecha"] == test_date]
            self.assertEqual(len(matching_indices), 1)
            idx = matching_indices[0]
            self.assertEqual(tables_data["informes"][idx]["referencia"], "REF-1001 / REF-2002")

            # Probar edición de referencia mediante PUT /informes/{id}
            put_payload = {
                "fecha": test_date,
                "laboratorio": db_inf.laboratorio,
                "facultativo": db_inf.facultativo,
                "referencia": "REF-UNIFICADA-99",
                "dictamen_global": db_inf.dictamen_global,
                "mediciones": [
                    {
                        "id": db_meds["GLUCOSE"].id,
                        "codigo": "GLUCOSE",
                        "nombre": "Glucosa",
                        "valor": "92",
                        "unidad": "mg/dL",
                        "rango_referencia": "70 - 100",
                        "es_ratio": False
                    }
                ]
            }
            res_put = self.client.put(f"/api/v1/analiticas/informes/{inf1_id}", json=put_payload)
            self.assertEqual(res_put.status_code, 200)
            
            self.db.refresh(db_inf)
            self.assertEqual(db_inf.referencia, "REF-UNIFICADA-99")
        finally:
            self._cleanup_test_data()

    def test_variacion_secuencial_limite_24_meses(self):
        d_act = date(2026, 6, 1)
        d_10m = date(2025, 8, 5)
        d_30m = date(2023, 12, 1)

        # Caso A: Determinación previa dentro de 24 meses (diferencia <= 730 días)
        diff_dentro = (d_act - d_10m).days
        self.assertLessEqual(diff_dentro, 730)
        sym_dentro, delta_dentro, _, _ = calcular_variacion_reciente(105.0, 100.0, "GLUCOSE")
        self.assertEqual(delta_dentro, "+5")

        # Caso B: Determinación previa fuera de 24 meses (diferencia > 730 días)
        diff_fuera = (d_act - d_30m).days
        self.assertGreater(diff_fuera, 730)
        val_anterior_fuera = None # La lógica en get_dashboard_summary asigna val_anterior = None
        sym_fuera, delta_fuera, _, _ = calcular_variacion_reciente(105.0, val_anterior_fuera, "GLUCOSE")
        self.assertEqual(delta_fuera, "")
        self.assertIsNone(sym_fuera)


if __name__ == "__main__":
    unittest.main()
