"""Regresiones de migración para bases SQLite de instalaciones existentes."""

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from tests.test_support import initialize_test_environment

initialize_test_environment()

from app.database import migrate_sqlite_schema


class TestSqliteMigrations(unittest.TestCase):
    def test_existing_informes_gain_referencia_without_losing_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            engine = create_engine(f"sqlite:///{Path(temporary) / 'legacy.db'}")
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE informes (id INTEGER PRIMARY KEY, fecha VARCHAR(10))"))
                connection.execute(text("INSERT INTO informes (id, fecha) VALUES (1, '2026-01-01')"))

            migrate_sqlite_schema(engine)
            migrate_sqlite_schema(engine)

            columns = {column["name"] for column in inspect(engine).get_columns("informes")}
            with engine.connect() as connection:
                rows = connection.execute(text("SELECT id, fecha, referencia FROM informes")).all()

            self.assertIn("referencia", columns)
            self.assertEqual(rows, [(1, "2026-01-01", None)])
            engine.dispose()
