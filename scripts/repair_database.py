import sqlite3
from pathlib import Path

DB_PATH = Path("data/analiticas.db")

def repair():
    if not DB_PATH.exists():
        print(f"Error: {DB_PATH} no existe.")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    print("Iniciando reparación y saneamiento de analiticas.db...")

    # 1. Asegurar analitos canónicos en la tabla analitos
    canonical_defs = [
        ("GLUCOSE", "Glucosa Basal", "bioquimica", "mg/dL", "60 - 100", 1),
        ("HBA1C", "HbA1c", "bioquimica", "%", "< 5.7", 2),
        ("CHOLESTEROL_TOTAL", "Colesterol Total", "bioquimica", "mg/dL", "< 200", 3),
        ("HDL", "HDL-Colesterol", "bioquimica", "mg/dL", "> 40", 4),
        ("LDL", "LDL-Colesterol", "bioquimica", "mg/dL", "< 116 (SEA)", 5),
        ("TRIGLYCERIDES", "Triglicéridos", "bioquimica", "mg/dL", "< 150", 6),
        ("RATIO_COL_HDL", "Cociente Col/HDL", "bioquimica", "ratio", "< 4.5", 7),
        ("RATIO_LDL_HDL", "Cociente LDL/HDL", "bioquimica", "ratio", "< 3.0", 8),
        ("RATIO_LDL_COL", "Ratio LDL / Col. Total", "bioquimica", "ratio", "< 0.65", 9),
        ("RATIO_HDL_COL", "Ratio HDL / Col. Total", "bioquimica", "ratio", "> 0.20", 10),
        ("RATIO_TG_COL", "Ratio TG / Col. Total", "bioquimica", "ratio", "< 0.50", 11),
        ("RATIO_PSA_L_T", "Ratio PSA Libre/Total", "bioquimica", "%", "> 20 %", 12),
        ("CREATININE", "Creatinina", "bioquimica", "mg/dL", "0.70 - 1.20", 13),
        ("UREA", "Urea", "bioquimica", "mg/dL", "15 - 45", 14),
        ("URIC_ACID", "Ácido Úrico", "bioquimica", "mg/dL", "3.5 - 7.2", 15),
        ("PSA_TOTAL", "PSA Total", "bioquimica", "ng/mL", "< 4.0", 16),
        ("PSA_FREE", "PSA Libre", "bioquimica", "ng/mL", "-", 17),
        ("TSH", "TSH", "bioquimica", "µUI/mL", "0.27 - 4.29", 18),
        ("T4_LIBRE", "T4 Libre", "bioquimica", "ng/dL", "0.71 - 1.85", 19),
        ("VITAMIN_D", "25-OH Vitamina D", "bioquimica", "ng/mL", "30 - 96", 20),
        ("GLUCOSE_URINE", "Glucosa (Orina)", "orina", "Cualitativo", "Negativo", 21),
        ("PROTEIN_URINE", "Proteínas / Albúmina (Orina)", "orina", "Cualitativo", "Negativo", 22),
    ]

    for cod, nom, cat, uni, ref, orden in canonical_defs:
        cursor.execute("SELECT id FROM analitos WHERE codigo = ?", (cod,))
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                "INSERT INTO analitos (codigo, nombre_visible, categoria, unidad_estandar, ref_texto_defecto, orden) VALUES (?, ?, ?, ?, ?, ?)",
                (cod, nom, cat, uni, ref, orden)
            )
            print(f"  + Analito insertado: {cod} ({nom})")
        else:
            cursor.execute(
                "UPDATE analitos SET nombre_visible = ?, categoria = ?, unidad_estandar = ? WHERE id = ?",
                (nom, cat, uni, row[0])
            )

    conn.commit()

    # Mapeo rápido de código a id
    analito_id_map = {row[0]: row[1] for row in cursor.execute("SELECT codigo, id FROM analitos")}

    def set_medicion(informe_id: int, cod: str, val_num, val_txt, uni: str, ref: str):
        a_id = analito_id_map.get(cod)
        if not a_id:
            print(f"Error: no se encontró id para analito {cod}")
            return
        
        # Eliminar mediciones duplicadas o previas para este informe y analito
        cursor.execute("DELETE FROM mediciones WHERE informe_id = ? AND analito_id = ?", (informe_id, a_id))
        
        cursor.execute(
            """INSERT INTO mediciones (informe_id, analito_id, valor_numerico, valor_texto, unidad, ref_texto)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (informe_id, a_id, val_num, val_txt, uni, ref)
        )
        print(f"  [Informe {informe_id}] {cod}: num={val_num}, txt={val_txt}, uni={uni}")

    # --- REPARACIÓN INFORME 4 (06/10/2017) ---
    print("\nSaneando Informe 4 (2017-10-06)...")
    set_medicion(4, "GLUCOSE", 88.0, None, "mg/dL", "60 - 110")
    set_medicion(4, "GLUCOSE_URINE", None, "Negativo", "Cualitativo", "Negativo")
    set_medicion(4, "CHOLESTEROL_TOTAL", 188.0, None, "mg/dL", "< 200")
    set_medicion(4, "HDL", 48.9, None, "mg/dL", "> 40")
    set_medicion(4, "LDL", 119.0, None, "mg/dL", "< 130")
    set_medicion(4, "TRIGLYCERIDES", 100.0, None, "mg/dL", "< 200")
    set_medicion(4, "RATIO_COL_HDL", 3.84, None, "ratio", "< 4.5")
    set_medicion(4, "RATIO_LDL_HDL", 2.43, None, "ratio", "< 3.0")
    set_medicion(4, "RATIO_LDL_COL", 0.63, None, "ratio", "< 0.65")
    set_medicion(4, "RATIO_HDL_COL", 0.26, None, "ratio", "> 0.20")
    set_medicion(4, "RATIO_TG_COL", 0.53, None, "ratio", "< 0.50")
    set_medicion(4, "HBA1C", 5.2, None, "%", "< 5.6")
    set_medicion(4, "PSA_TOTAL", 0.82, None, "ng/mL", "< 4")
    set_medicion(4, "TSH", 1.65, None, "µUI/mL", "0.4 - 3.7")
    set_medicion(4, "T4_LIBRE", 1.08, None, "ng/dL", "0.71 - 1.85")
    set_medicion(4, "VITAMIN_D", 37.4, None, "ng/mL", "30 - 96")

    # --- REPARACIÓN INFORME 5 (27/09/2018) ---
    print("\nSaneando Informe 5 (2018-09-27)...")
    set_medicion(5, "GLUCOSE", 86.0, None, "mg/dL", "60 - 110")
    set_medicion(5, "GLUCOSE_URINE", None, "Negativo", "Cualitativo", "Negativo")
    set_medicion(5, "CHOLESTEROL_TOTAL", 180.0, None, "mg/dL", "< 200")
    set_medicion(5, "HDL", 42.0, None, "mg/dL", "> 40")
    set_medicion(5, "LDL", 113.0, None, "mg/dL", "< 130")
    set_medicion(5, "TRIGLYCERIDES", 126.0, None, "mg/dL", "< 150")
    set_medicion(5, "RATIO_COL_HDL", 4.29, None, "ratio", "< 4.5")
    set_medicion(5, "RATIO_LDL_HDL", 2.69, None, "ratio", "< 3.0")
    set_medicion(5, "RATIO_LDL_COL", 0.63, None, "ratio", "< 0.65")
    set_medicion(5, "RATIO_HDL_COL", 0.23, None, "ratio", "> 0.20")
    set_medicion(5, "RATIO_TG_COL", 0.70, None, "ratio", "< 0.50")
    set_medicion(5, "HBA1C", 5.6, None, "%", "< 5.6")
    set_medicion(5, "UREA", 35.0, None, "mg/dL", "17 - 51")
    set_medicion(5, "CREATININE", 0.98, None, "mg/dL", "0.73 - 1.18")
    set_medicion(5, "URIC_ACID", 8.0, None, "mg/dL", "3.5 - 7.2")
    set_medicion(5, "PSA_TOTAL", 0.80, None, "ng/mL", "< 4")
    set_medicion(5, "TSH", 1.23, None, "µUI/mL", "0.4 - 3.7")
    set_medicion(5, "T4_LIBRE", 1.03, None, "ng/dL", "0.71 - 1.85")
    set_medicion(5, "VITAMIN_D", 37.6, None, "ng/mL", "30 - 96")

    # Eliminar cualquier ratio de orina residual o erróneo en los informes
    cursor.execute("""
        DELETE FROM mediciones
        WHERE analito_id IN (SELECT id FROM analitos WHERE codigo IN ('RATIO_COL_HDL', 'RATIO_LDL_HDL', 'RATIO_LDL_COL', 'RATIO_HDL_COL', 'RATIO_TG_COL'))
        AND valor_numerico > 50
    """)

    conn.commit()
    conn.close()
    print("\n¡Base de datos reparada con éxito!")

if __name__ == "__main__":
    repair()
