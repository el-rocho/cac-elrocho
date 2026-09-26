"""Garantiza que la distribución no lea accidentalmente el .env de desarrollo."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestFrozenConfiguration(unittest.TestCase):
    def test_frozen_app_ignores_dotenv_in_its_working_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            (temporary_path / ".env").write_text("API_KEY1=development-secret\n", encoding="utf-8")
            environment = os.environ.copy()
            environment.pop("API_KEY1", None)
            environment.pop("LLM_PROVIDER1", None)
            environment["PYTHONPATH"] = str(PROJECT_ROOT)
            environment["APP_DATA_DIR"] = str(temporary_path / "data")
            code = textwrap.dedent(
                """
                import sys
                sys.frozen = True
                from app.config import settings
                assert not hasattr(settings, "API_KEY1")
                """
            )
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=temporary,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
