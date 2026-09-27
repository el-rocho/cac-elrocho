"""Evalúa el extractor RegEx contra los informes ya confirmados.

La base original se abre exclusivamente en lectura. Por cada informe cuyo PDF
esté disponible, se ejecuta el mismo extractor de contingencia que usa la
aplicación y se guardan tanto sus mediciones como la comparación en otra base
SQLite. No modifica informes, PDFs ni la configuración de slots LLM.

Ejemplo (desde la raíz del repositorio):

    .\\venv-win\\Scripts\\python.exe scripts\\comparar_extraccion_regex.py --overwrite
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.services.llm_service import generate_mock_extraction  # noqa: E402
from app.services.parser import extract_text_from_pdf  # noqa: E402


DEFAULT_SOURCE_DB = REPOSITORY_ROOT / "data" / "analiticas.db"
DEFAULT_PDF_DIR = REPOSITORY_ROOT / "data" / "uploads"
DEFAULT_OUTPUT_DB = REPOSITORY_ROOT / "data" / "comparativa_regex.db"
DEFAULT_REPORT = REPOSITORY_ROOT / "data" / "comparativa_regex.json"

# Variantes históricas que representan el mismo analito. El extractor no debe
# recibir una penalización por elegir una de estas dos etiquetas canónicas.
CODE_ALIASES = {
    "ALBUMINA": "ALBUMINA_SERICA",
    "EGFR": "EGFR_CKD_EPI",
    "TIEMPO_DE_TROMBOPLASTINA_PARCI": "TTPA",
}

# Estos valores se crean al confirmar una analítica a partir de otras
# mediciones. No son una obligación del extractor de PDF salvo que se solicite
# explícitamente --include-derived.
DERIVED_CODES = {
    "RATIO_COL_HDL",
    "RATIO_LDL_HDL",
    "RATIO_TG_HDL",
    "RATIO_LDL_COL",
    "RATIO_HDL_COL",
    "RATIO_TG_COL",
    "RATIO_PSA_L_T",
}


SCHEMA = """
CREATE TABLE regex_runs (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    source_db TEXT NOT NULL,
    pdf_dir TEXT NOT NULL,
    tolerance REAL NOT NULL
);
CREATE TABLE regex_informes (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES regex_runs(id),
    informe_id INTEGER NOT NULL,
    fecha TEXT,
    laboratorio TEXT,
    archivo_pdf TEXT,
    estado TEXT NOT NULL,
    detalle TEXT
);
CREATE TABLE regex_fuentes_pdf (
    id INTEGER PRIMARY KEY,
    regex_informe_id INTEGER NOT NULL REFERENCES regex_informes(id),
    archivo_pdf TEXT NOT NULL
);
CREATE TABLE regex_mediciones (
    id INTEGER PRIMARY KEY,
    regex_informe_id INTEGER NOT NULL REFERENCES regex_informes(id),
    codigo TEXT,
    nombre TEXT NOT NULL,
    valor TEXT NOT NULL,
    unidad TEXT,
    rango_referencia TEXT
);
CREATE TABLE comparacion_mediciones (
    id INTEGER PRIMARY KEY,
    regex_informe_id INTEGER NOT NULL REFERENCES regex_informes(id),
    codigo TEXT NOT NULL,
    esperado_valor TEXT,
    esperado_unidad TEXT,
    esperado_referencia TEXT,
    regex_valor TEXT,
    regex_unidad TEXT,
    regex_referencia TEXT,
    estado TEXT NOT NULL,
    valor_correcto INTEGER,
    unidad_correcta INTEGER,
    referencia_correcta INTEGER
);
CREATE TABLE evidencias_fallo_regex (
    id INTEGER PRIMARY KEY,
    comparacion_id INTEGER NOT NULL REFERENCES comparacion_mediciones(id),
    termino_busqueda TEXT,
    contexto_pdf TEXT,
    creado_en TEXT NOT NULL
);
CREATE INDEX idx_regex_informes_run ON regex_informes(run_id);
CREATE INDEX idx_regex_fuentes_informe ON regex_fuentes_pdf(regex_informe_id);
CREATE INDEX idx_comparacion_estado ON comparacion_mediciones(estado);
CREATE INDEX idx_evidencias_comparacion ON evidencias_fallo_regex(comparacion_id);
"""


def open_source_database(path: Path) -> sqlite3.Connection:
    """Abre la base confirmada en modo SQLite de solo lectura."""
    if not path.is_file():
        raise FileNotFoundError(f"No existe la base fuente: {path}")
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def resolve_validated_pdfs(pdf_dir: Path, report_date: str) -> list[Path]:
    """Asocia un informe a todos los PDFs validados de su misma fecha.

    La base puede consolidar varias peticiones en un informe. En ese caso los
    PDFs válidos se unen como una única entrada de texto antes de ejecutar las
    reglas, sin apoyarse en el nombre histórico ``archivo_pdf`` de la app.
    """
    return sorted(path for path in pdf_dir.glob(f"{report_date}*.pdf") if path.is_file())


def normalizar_texto(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().replace("µ", "u").split())


def valor_numerico(value: Any) -> float | None:
    try:
        clean = str(value).strip().replace(",", ".")
        return float(clean) if clean else None
    except (TypeError, ValueError):
        return None


def valores_iguales(expected: Any, extracted: Any, tolerance: float) -> bool:
    expected_number = valor_numerico(expected)
    extracted_number = valor_numerico(extracted)
    if expected_number is not None and extracted_number is not None:
        return math.isclose(expected_number, extracted_number, rel_tol=tolerance, abs_tol=tolerance)
    return normalizar_texto(expected) == normalizar_texto(extracted)


def codigo_comparable(code: str | None) -> str:
    """Devuelve un código estable para comparar históricos y extracción."""
    code = (code or "").strip().upper()
    return CODE_ALIASES.get(code, code)


def contexto_del_pdf(text: str, terms: Iterable[str], radius: int = 180) -> tuple[str | None, str | None]:
    """Devuelve un fragmento local alrededor del primer nombre de analito hallado."""
    for term in terms:
        term = (term or "").strip()
        if not term:
            continue
        match = re.search(re.escape(term), text, flags=re.IGNORECASE)
        if match:
            start = max(0, match.start() - radius)
            end = min(len(text), match.end() + radius)
            # Mantiene las filas reconocibles sin inflar la base con páginas completas.
            return term, " ".join(text[start:end].split())
    return None, None


def expected_measurements(source: sqlite3.Connection, informe_id: int) -> dict[str, dict[str, Any]]:
    rows = source.execute(
        """
        SELECT a.codigo, a.nombre_visible, m.valor_numerico, m.valor_texto, m.unidad, m.ref_texto
        FROM mediciones AS m
        JOIN analitos AS a ON a.id = m.analito_id
        WHERE m.informe_id = ?
        """,
        (informe_id,),
    )
    result: dict[str, dict[str, Any]] = {}
    for code, name, numeric_value, text_value, unit, reference in rows:
        # La interfaz guarda el valor numérico cuando existe; el texto cubre
        # resultados cualitativos (p. ej. "Negativo").
        result[code] = {
            "valor": text_value if text_value not in (None, "") else numeric_value,
            "nombre": name,
            "unidad": unit,
            "referencia": reference,
        }
    return result


def insert_comparisons(
    output: sqlite3.Connection,
    regex_informe_id: int,
    expected: dict[str, dict[str, Any]],
    extracted: Iterable[Any],
    tolerance: float,
    include_derived: bool,
    source_text: str,
) -> Counter[str]:
    by_code = {
        codigo_comparable(measurement.codigo): measurement
        for measurement in extracted
        if measurement.codigo
        and (include_derived or codigo_comparable(measurement.codigo) not in DERIVED_CODES)
    }
    expected = {
        codigo_comparable(code): target
        for code, target in expected.items()
        if include_derived or codigo_comparable(code) not in DERIVED_CODES
    }
    statuses: Counter[str] = Counter()
    for code in sorted(set(expected) | set(by_code)):
        target = expected.get(code)
        actual = by_code.get(code)
        if target is None:
            state = "falso_positivo"
            value_ok = unit_ok = reference_ok = None
        elif actual is None:
            state = "no_detectado"
            value_ok = unit_ok = reference_ok = None
        else:
            value_ok = valores_iguales(target["valor"], actual.valor, tolerance)
            unit_ok = normalizar_texto(target["unidad"]) == normalizar_texto(actual.unidad)
            # Un rango vacío de la base no es evidencia de error del extractor.
            reference_ok = (
                None
                if not normalizar_texto(target["referencia"])
                else normalizar_texto(target["referencia"]) == normalizar_texto(actual.rango_referencia)
            )
            state = "correcto" if value_ok and unit_ok else "discrepancia"

        statuses[state] += 1
        comparison_id = output.execute(
            """
            INSERT INTO comparacion_mediciones (
                regex_informe_id, codigo, esperado_valor, esperado_unidad,
                esperado_referencia, regex_valor, regex_unidad,
                regex_referencia, estado, valor_correcto, unidad_correcta,
                referencia_correcta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                regex_informe_id,
                code,
                None if target is None else str(target["valor"] or ""),
                None if target is None else target["unidad"],
                None if target is None else target["referencia"],
                None if actual is None else actual.valor,
                None if actual is None else actual.unidad,
                None if actual is None else actual.rango_referencia,
                state,
                value_ok,
                unit_ok,
                reference_ok,
            ),
        ).lastrowid
        if state != "correcto":
            search_term, context = contexto_del_pdf(
                source_text,
                [
                    "" if target is None else target.get("nombre", ""),
                    "" if actual is None else actual.nombre,
                ],
            )
            output.execute(
                """INSERT INTO evidencias_fallo_regex
                   (comparacion_id, termino_busqueda, contexto_pdf, creado_en)
                   VALUES (?, ?, ?, ?)""",
                (comparison_id, search_term, context, datetime.now(timezone.utc).isoformat()),
            )
    return statuses


def build_report(output: sqlite3.Connection, run_id: int) -> dict[str, Any]:
    statuses = dict(
        output.execute(
            """SELECT c.estado, COUNT(*) FROM comparacion_mediciones c
               JOIN regex_informes i ON i.id = c.regex_informe_id
               WHERE i.run_id = ? GROUP BY c.estado""",
            (run_id,),
        )
    )
    processed, missing = output.execute(
        """SELECT
             SUM(CASE WHEN estado = 'procesado' THEN 1 ELSE 0 END),
             SUM(CASE WHEN estado = 'pdf_no_encontrado' THEN 1 ELSE 0 END)
           FROM regex_informes WHERE run_id = ?""",
        (run_id,),
    ).fetchone()
    sources = output.execute(
        """SELECT COUNT(*) FROM regex_fuentes_pdf f
           JOIN regex_informes i ON i.id = f.regex_informe_id
           WHERE i.run_id = ?""",
        (run_id,),
    ).fetchone()[0]
    mappings = [
        {"informe_id": report_id, "fecha": report_date, "pdfs": pdfs.split(" | ")}
        for report_id, report_date, pdfs in output.execute(
            """SELECT i.informe_id, i.fecha, GROUP_CONCAT(f.archivo_pdf, ' | ')
               FROM regex_informes i JOIN regex_fuentes_pdf f ON f.regex_informe_id = i.id
               WHERE i.run_id = ? GROUP BY i.id ORDER BY i.fecha, i.informe_id""",
            (run_id,),
        )
    ]
    true_positive = statuses.get("correcto", 0)
    false_positive = statuses.get("falso_positivo", 0)
    false_negative = statuses.get("no_detectado", 0)
    discrepancies = statuses.get("discrepancia", 0)
    detected = true_positive + false_positive + discrepancies
    expected = true_positive + false_negative + discrepancies
    per_analito: dict[str, dict[str, int]] = {}
    for code, state, count in output.execute(
        """SELECT c.codigo, c.estado, COUNT(*) FROM comparacion_mediciones c
           JOIN regex_informes i ON i.id = c.regex_informe_id
           WHERE i.run_id = ? GROUP BY c.codigo, c.estado ORDER BY c.codigo""",
        (run_id,),
    ):
        per_analito.setdefault(code, {})[state] = count
    priorities = [
        {"codigo": code, "laboratorio": laboratory or "Sin laboratorio", "estado": state, "casos": count}
        for code, laboratory, state, count in output.execute(
            """SELECT c.codigo, i.laboratorio, c.estado, COUNT(*) AS casos
               FROM comparacion_mediciones c
               JOIN regex_informes i ON i.id = c.regex_informe_id
               WHERE i.run_id = ? AND c.estado <> 'correcto'
               GROUP BY c.codigo, i.laboratorio, c.estado
               ORDER BY casos DESC, c.estado, c.codigo
               LIMIT 30""",
            (run_id,),
        )
    ]
    return {
        "run_id": run_id,
        "informes_procesados": processed or 0,
        "pdfs_validados_procesados": sources,
        "pdfs_no_encontrados": missing or 0,
        "asociaciones_pdf": mappings,
        "resultados": statuses,
        "cobertura_valor_unidad_correctos": true_positive / expected if expected else None,
        "precision_valor_unidad_correctos": true_positive / detected if detected else None,
        "discrepancias": discrepancies,
        "falsos_positivos": false_positive,
        "no_detectados": false_negative,
        # Permite elegir patrones por impacto: primero los códigos con más
        # no_detectados o discrepancias, sin exponer valores clínicos en JSON.
        "por_analito": per_analito,
        "prioridades": priorities,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB)
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--tolerance", type=float, default=1e-6, help="Tolerancia absoluta y relativa para valores numéricos.")
    parser.add_argument(
        "--include-derived",
        action="store_true",
        help="Incluye ratios calculados automáticamente en la métrica (se excluyen por defecto).",
    )
    parser.add_argument("--overwrite", action="store_true", help="Reemplaza la base e informe de una ejecución anterior.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_db = args.source_db.resolve()
    pdf_dir = args.pdf_dir.resolve()
    output_db = args.output_db.resolve()
    report_path = args.report.resolve()
    if args.tolerance < 0:
        raise ValueError("--tolerance debe ser mayor o igual que cero.")
    if output_db.exists() and not args.overwrite:
        raise FileExistsError(f"Ya existe {output_db}. Use --overwrite para reemplazarlo.")
    if report_path.exists() and not args.overwrite:
        raise FileExistsError(f"Ya existe {report_path}. Use --overwrite para reemplazarlo.")

    output_db.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if args.overwrite:
        output_db.unlink(missing_ok=True)
        report_path.unlink(missing_ok=True)

    source = open_source_database(source_db)
    output = sqlite3.connect(output_db)
    try:
        output.executescript(SCHEMA)
        run_id = output.execute(
            "INSERT INTO regex_runs (started_at, source_db, pdf_dir, tolerance) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), str(source_db), str(pdf_dir), args.tolerance),
        ).lastrowid
        informes = source.execute(
            "SELECT id, fecha, laboratorio, archivo_pdf FROM informes ORDER BY fecha, id"
        ).fetchall()

        for informe_id, date, laboratory, filename in informes:
            pdf_paths = resolve_validated_pdfs(pdf_dir, date)
            if not pdf_paths:
                output.execute(
                    """INSERT INTO regex_informes (run_id, informe_id, fecha, laboratorio, archivo_pdf, estado, detalle)
                       VALUES (?, ?, ?, ?, ?, 'pdf_no_encontrado', ?)""",
                    (run_id, informe_id, date, laboratory, filename, "No hay PDF validado cuyo nombre comience con la fecha del informe."),
                )
                continue

            text = "\n\n".join(
                f"--- ARCHIVO VALIDADO: {pdf_path.name} ---\n{extract_text_from_pdf(pdf_path)}"
                for pdf_path in pdf_paths
            )
            preview = generate_mock_extraction(text, temp_id=f"benchmark-{informe_id}")
            regex_informe_id = output.execute(
                """INSERT INTO regex_informes (run_id, informe_id, fecha, laboratorio, archivo_pdf, estado)
                   VALUES (?, ?, ?, ?, ?, 'procesado')""",
                (run_id, informe_id, date, laboratory, " | ".join(path.name for path in pdf_paths)),
            ).lastrowid
            output.executemany(
                "INSERT INTO regex_fuentes_pdf (regex_informe_id, archivo_pdf) VALUES (?, ?)",
                [(regex_informe_id, path.name) for path in pdf_paths],
            )
            for measurement in preview.mediciones:
                output.execute(
                    """INSERT INTO regex_mediciones
                       (regex_informe_id, codigo, nombre, valor, unidad, rango_referencia)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (regex_informe_id, measurement.codigo, measurement.nombre, measurement.valor,
                     measurement.unidad, measurement.rango_referencia),
                )
            insert_comparisons(
                output,
                regex_informe_id,
                expected_measurements(source, informe_id),
                preview.mediciones,
                args.tolerance,
                args.include_derived,
                text,
            )

        report = build_report(output, run_id)
        report["ratios_derivados_excluidos"] = [] if args.include_derived else sorted(DERIVED_CODES)
        output.commit()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        source.close()
        output.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Base de comparación: {output_db}")
    print(f"Informe resumido: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
