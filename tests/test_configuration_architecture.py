"""Pruebas aisladas de las nuevas rutas y preferencias de instalación."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_support import initialize_test_environment

initialize_test_environment()

from app.paths import AppPaths
from app.services.configuration_service import ConfigurationService
from app.services.secret_store import SecretStatus


class TestPersistentPaths(unittest.TestCase):
    def test_all_persistent_paths_share_one_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = AppPaths(Path(temporary))
            paths.ensure_directories()

            self.assertEqual(paths.database_file, Path(temporary) / "data" / "analiticas.db")
            self.assertEqual(paths.uploads_dir, Path(temporary) / "data" / "uploads")
            self.assertEqual(paths.inbox_dir, Path(temporary) / "inbox")
            self.assertTrue(paths.config_dir.is_dir())
            self.assertTrue(paths.logs_dir.is_dir())


class TestConfigurationService(unittest.TestCase):
    def test_preferences_are_persisted_without_exposing_secrets(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = AppPaths(Path(temporary))
            paths.ensure_directories()
            fake_settings = SimpleNamespace(
                paths=paths,
                API_KEY1=None,
                API_KEY2=None,
                API_KEY3=None,
                GEMINI_API_KEY="",
                GEMINI_MODEL="gemini-flash-lite-latest",
                LLM_PROVIDER="gemini",
                LLM_PROVIDER1=None,
                LLM_PROVIDER2=None,
                LLM_PROVIDER3=None,
                MODEL1=None,
                MODEL2=None,
                MODEL3=None,
            )
            fake_secret_store = SimpleNamespace(
                status=lambda _: SecretStatus(True, "keyring", False),
                get_secret=lambda _: "should-never-be-returned",
            )
            service = ConfigurationService()
            with patch("app.services.configuration_service.settings", fake_settings), patch(
                "app.services.configuration_service.secret_store", fake_secret_store
            ):
                result = service.update_ai_config({"model": "gemini-test", "provider": "gemini"})
                public = service.get_ai_config()

            self.assertEqual(result["model"], "gemini-test")
            self.assertTrue(public["credential_configured"])
            self.assertNotIn("should-never-be-returned", str(public))
            self.assertIn('"model": "gemini-test"', paths.config_file.read_text(encoding="utf-8"))
