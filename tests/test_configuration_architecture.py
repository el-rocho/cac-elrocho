"""Pruebas aisladas de las nuevas rutas y preferencias de instalación."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_support import initialize_test_environment

initialize_test_environment()

from app.paths import AppPaths
from app.services.configuration_service import ConfigurationService
from app.services.secret_store import SecretStatus, SecretStore


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
    def test_new_installation_starts_with_three_disabled_empty_slots(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = AppPaths(Path(temporary))
            paths.ensure_directories()
            fake_settings = SimpleNamespace(paths=paths)
            fake_secret_store = SimpleNamespace(status=lambda _: SecretStatus(False, None, False))
            service = ConfigurationService()
            with patch("app.services.configuration_service.settings", fake_settings), patch(
                "app.services.configuration_service.secret_store", fake_secret_store
            ):
                slots = service.get_ai_config()["slots"]

            self.assertEqual([slot["provider"] for slot in slots], ["none", "none", "none"])
            self.assertEqual([slot["model"] for slot in slots], ["", "", ""])
            self.assertEqual([slot["enabled"] for slot in slots], [False, False, False])

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

    def test_three_slots_are_persisted_and_resolved_in_priority_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = AppPaths(Path(temporary))
            paths.ensure_directories()
            fake_settings = SimpleNamespace(paths=paths)
            fake_secret_store = SimpleNamespace(
                status=lambda _: SecretStatus(True, "keyring", False),
                get_secret=lambda name: f"key-{name[-1]}",
            )
            service = ConfigurationService()
            slots = [
                {"provider": "gemini", "model": "principal", "enabled": True},
                {"provider": "gemini", "model": "respaldo", "enabled": True},
                {"provider": "gemini", "model": "razonamiento", "enabled": True},
            ]
            with patch("app.services.configuration_service.settings", fake_settings), patch(
                "app.services.configuration_service.secret_store", fake_secret_store
            ):
                public = service.update_ai_config({"slots": slots})
                resolved = service.get_configured_llm_slots()

            self.assertEqual([slot["model"] for slot in public["slots"]], ["principal", "respaldo", "razonamiento"])
            self.assertEqual([slot["slot"] for slot in resolved], [1, 2, 3])
            self.assertEqual([slot["api_key"] for slot in resolved], ["key-1", "key-2", "key-3"])
            stored = paths.config_file.read_text(encoding="utf-8")
            self.assertIn('"principal"', stored)
            self.assertNotIn("key-1", stored)

    def test_file_store_is_used_when_keyring_is_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = AppPaths(Path(temporary))
            paths.ensure_directories()
            store = SecretStore()
            with patch("app.services.secret_store.settings", SimpleNamespace(paths=paths)), patch.object(
                store, "_keyring", return_value=None
            ), patch.object(store, "_file_store_enabled", return_value=True), patch.object(
                store, "_prefer_file_store", return_value=False
            ):
                store.set_secret("gemini_api_key_2", "slot-two-secret")
                self.assertEqual(store.get_secret("gemini_api_key_2"), "slot-two-secret")
                self.assertEqual(store.status("gemini_api_key_2").source, "protected_file")
                raw_credentials = (paths.config_dir / "llm-credentials.json").read_text(encoding="utf-8")
                self.assertNotIn("slot-two-secret", raw_credentials)
                if os.name == "nt":
                    self.assertIn('"dpapi:', raw_credentials)
                store.delete_secret("gemini_api_key_2")
                self.assertIsNone(store.get_secret("gemini_api_key_2"))

            credentials_file = paths.config_dir / "llm-credentials.json"
            self.assertTrue(credentials_file.exists())
            self.assertNotIn("slot-two-secret", paths.config_file.read_text(encoding="utf-8") if paths.config_file.exists() else "")

    def test_legacy_single_model_configuration_migrates_to_slot_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = AppPaths(Path(temporary))
            paths.ensure_directories()
            paths.config_file.write_text(
                '{"ai": {"provider": "gemini", "model": "gemini-legacy"}}', encoding="utf-8"
            )
            fake_settings = SimpleNamespace(paths=paths)
            fake_secret_store = SimpleNamespace(status=lambda _: SecretStatus(True, "keyring", False))
            service = ConfigurationService()
            with patch("app.services.configuration_service.settings", fake_settings), patch(
                "app.services.configuration_service.secret_store", fake_secret_store
            ):
                slots = service.get_ai_config()["slots"]

            self.assertEqual(slots[0]["provider"], "gemini")
            self.assertEqual(slots[0]["model"], "gemini-legacy")
            self.assertTrue(slots[0]["enabled"])
            self.assertEqual([slot["provider"] for slot in slots[1:]], ["none", "none"])

    def test_slots_without_credential_keep_their_model_until_the_key_is_saved(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = AppPaths(Path(temporary))
            paths.ensure_directories()
            fake_settings = SimpleNamespace(paths=paths)
            fake_secret_store = SimpleNamespace(
                status=lambda name: SecretStatus(name == "gemini_api_key_1", "keyring", False)
            )
            service = ConfigurationService()
            requested_slots = [
                {"provider": "gemini", "model": "configured", "enabled": True},
                {"provider": "gemini", "model": "missing-token", "enabled": True},
                {"provider": "gemini", "model": "", "enabled": True},
            ]
            with patch("app.services.configuration_service.settings", fake_settings), patch(
                "app.services.configuration_service.secret_store", fake_secret_store
            ):
                saved = service.update_ai_config({"slots": requested_slots})

            self.assertEqual(saved["slots"][0]["provider"], "gemini")
            self.assertEqual([slot["provider"] for slot in saved["slots"]], ["gemini", "gemini", "none"])
            self.assertTrue(saved["slots"][1]["enabled"])
            self.assertEqual(saved["slots"][1]["model"], "missing-token")
            self.assertEqual(saved["slots"][2]["model"], "")
