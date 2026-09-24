"""Preferencias persistentes, sin secretos, de una instalación."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from app.config import settings
from app.services.secret_store import secret_store


logger = logging.getLogger(__name__)

DEFAULT_CONFIG: Dict[str, Any] = {
    "ai": {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "fallback_enabled": True,
        "local_endpoint": "",
        "local_model": "",
    }
}


class ConfigurationService:
    def _read_file(self) -> Dict[str, Any]:
        path = settings.paths.config_file
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("No se pudo leer la configuración persistida: %s", exc)
            return {}

    def _write_file(self, value: Dict[str, Any]) -> None:
        path = settings.paths.config_file
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix="config-", suffix=".json", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temporary:
                json.dump(value, temporary, ensure_ascii=False, indent=2, sort_keys=True)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, path)
        except Exception:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            finally:
                raise

    @staticmethod
    def _merge(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = deepcopy(default)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = ConfigurationService._merge(result[key], value)
            else:
                result[key] = value
        return result

    def get_config(self) -> Dict[str, Any]:
        return self._merge(DEFAULT_CONFIG, self._read_file())

    def _environment_slots(self) -> list[Dict[str, Any]]:
        slots = []
        for index in (1, 2, 3):
            provider = getattr(settings, f"LLM_PROVIDER{index}", None)
            api_key = getattr(settings, f"API_KEY{index}", None)
            model = getattr(settings, f"MODEL{index}", None)
            if provider or api_key or model:
                cleaned_key = (api_key or "").strip()
                if cleaned_key.startswith("tu_clave_de_"):
                    cleaned_key = ""
                slots.append({
                    "slot": index,
                    "provider": (provider or "gemini").strip().lower(),
                    "api_key": cleaned_key,
                    "model": (model or "").strip(),
                })
        if slots:
            return slots
        if settings.GEMINI_API_KEY:
            return [{
                "slot": 1,
                "provider": settings.LLM_PROVIDER.lower(),
                "api_key": settings.GEMINI_API_KEY,
                "model": settings.GEMINI_MODEL,
            }]
        return []

    def is_ai_managed_by_environment(self) -> bool:
        return bool(self._environment_slots())

    def get_ai_config(self) -> Dict[str, Any]:
        env_slots = self._environment_slots()
        secret_status = secret_store.status("gemini_api_key")
        if env_slots:
            primary = env_slots[0]
            environment_has_credential = any(bool(slot["api_key"]) for slot in env_slots)
            return {
                "provider": primary["provider"],
                "model": primary["model"],
                "fallback_enabled": True,
                "local_endpoint": "",
                "local_model": "",
                "credential_configured": environment_has_credential or secret_status.configured,
                "credential_source": "environment" if environment_has_credential else secret_status.source,
                "managed_by_environment": True,
                "credential_managed_by_environment": environment_has_credential,
            }
        ai = self.get_config()["ai"]
        return {
            **ai,
            "credential_configured": secret_status.configured,
            "credential_source": secret_status.source,
            "managed_by_environment": secret_status.managed_by_environment,
            "credential_managed_by_environment": secret_status.managed_by_environment,
        }

    def update_ai_config(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        if self.is_ai_managed_by_environment():
            raise ValueError("La configuración de IA está administrada mediante variables de entorno.")
        allowed = {"provider", "model", "fallback_enabled", "local_endpoint", "local_model"}
        invalid = set(changes) - allowed
        if invalid:
            raise ValueError("Se intentó modificar una preferencia no permitida.")
        if "provider" in changes and changes["provider"] not in {"gemini", "none"}:
            raise ValueError("El proveedor de IA no es válido.")
        config = self.get_config()
        config["ai"].update(changes)
        self._write_file(config)
        return self.get_ai_config()

    def get_configured_llm_slots(self) -> list[Dict[str, Any]]:
        environment_slots = self._environment_slots()
        if environment_slots:
            stored_key = secret_store.get_secret("gemini_api_key") or ""
            return [
                {**slot, "api_key": slot["api_key"] or stored_key}
                if slot["provider"] == "gemini" else slot
                for slot in environment_slots
            ]
        ai = self.get_config()["ai"]
        if ai["provider"] != "gemini":
            return []
        return [{
            "slot": 1,
            "provider": "gemini",
            "api_key": secret_store.get_secret("gemini_api_key") or "",
            "model": ai["model"],
        }]


configuration_service = ConfigurationService()
