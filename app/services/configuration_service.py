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
        "slots": [
            {"provider": "none", "model": "", "enabled": False},
            {"provider": "none", "model": "", "enabled": False},
            {"provider": "none", "model": "", "enabled": False},
        ],
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

    def _configured_slots(self) -> list[Dict[str, Any]]:
        raw_ai = self._read_file().get("ai", {})
        configured = self.get_config()["ai"].get("slots", [])
        if not isinstance(configured, list):
            configured = []
        # Migración en lectura del único modelo de versiones anteriores. Las
        # claves continúan en SecretStore y su migración a slot 1 es también
        # transparente, por lo que no se escriben secretos en config.json.
        if isinstance(raw_ai, dict) and not isinstance(raw_ai.get("slots"), list):
            legacy_provider = raw_ai.get("provider")
            legacy_model = str(raw_ai.get("model") or "").strip()
            if legacy_provider in {"gemini", "none"}:
                configured = [
                    {
                        "provider": legacy_provider,
                        "model": legacy_model,
                        "enabled": legacy_provider == "gemini" and bool(legacy_model),
                    },
                    *DEFAULT_CONFIG["ai"]["slots"][1:],
                ]
        slots = []
        for index, default in enumerate(DEFAULT_CONFIG["ai"]["slots"], start=1):
            candidate = configured[index - 1] if index <= len(configured) and isinstance(configured[index - 1], dict) else {}
            slots.append({
                "slot": index,
                "provider": candidate.get("provider", default["provider"]),
                "model": candidate.get("model", default["model"]),
                "enabled": bool(candidate.get("enabled", default["enabled"])),
            })
        return slots

    def get_ai_config(self) -> Dict[str, Any]:
        ai = self.get_config()["ai"]
        slots = []
        for slot in self._configured_slots():
            status = secret_store.status(f"gemini_api_key_{slot['slot']}")
            slots.append({
                **slot,
                "credential_configured": status.configured,
                "credential_source": status.source,
                "credential_managed_by_environment": status.managed_by_environment,
            })
        primary = slots[0]
        return {
            **ai,
            "slots": slots,
            # Campos conservados para clientes de versiones previas.
            "provider": primary["provider"],
            "model": primary["model"],
            "credential_configured": primary["credential_configured"],
            "credential_source": primary["credential_source"],
            "managed_by_environment": False,
            "credential_managed_by_environment": primary["credential_managed_by_environment"],
        }

    @staticmethod
    def _empty_slot(index: int) -> Dict[str, Any]:
        return {"slot": index, "provider": "none", "model": "", "enabled": False}

    def _normalize_slots(self, slots: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
        """Normaliza las preferencias de los slots sin borrar su configuración.

        La clave se guarda mediante una petición independiente. Por ello, al
        guardar primero el modelo y después la clave no podemos convertir el
        slot a ``none``: se perdería el modelo y ya no habría forma de asociar
        la credencial recién guardada al slot. La ejecución real sigue
        requiriendo clave en :meth:`get_configured_llm_slots`.
        """
        normalized = []
        for index, slot in enumerate(slots, start=1):
            provider = slot.get("provider")
            model = str(slot.get("model") or "").strip()
            if provider == "gemini" and model:
                normalized.append({
                    "slot": index,
                    "provider": "gemini",
                    "model": model,
                    "enabled": bool(slot.get("enabled")),
                })
            else:
                normalized.append(self._empty_slot(index))
        return normalized

    def update_ai_config(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {"slots", "provider", "model", "fallback_enabled", "local_endpoint", "local_model"}
        invalid = set(changes) - allowed
        if invalid:
            raise ValueError("Se intentó modificar una preferencia no permitida.")
        slots = changes.get("slots")
        if slots is not None:
            if len(slots) != 3:
                raise ValueError("Deben configurarse exactamente tres slots de IA.")
            for index, slot in enumerate(slots, start=1):
                if slot.get("provider") not in {"gemini", "none"}:
                    raise ValueError(f"El proveedor del slot {index} no es válido.")
        # Compatibilidad con la API antigua: sus campos afectan exclusivamente
        # al primer slot hasta que todos los clientes usen `slots`.
        if "provider" in changes or "model" in changes:
            slots = self._configured_slots()
            slots[0].update({key: changes[key] for key in ("provider", "model") if key in changes})
            slots[0]["enabled"] = slots[0]["provider"] == "gemini" and bool(str(slots[0]["model"]).strip())
            changes["slots"] = slots
            changes.pop("provider", None)
            changes.pop("model", None)
        if "slots" in changes:
            changes["slots"] = self._normalize_slots(changes["slots"])
        config = self.get_config()
        config["ai"].update(changes)
        if "slots" in changes:
            # La configuración multi-slot reemplaza los campos heredados.
            config["ai"].pop("provider", None)
            config["ai"].pop("model", None)
        self._write_file(config)
        return self.get_ai_config()

    def get_configured_llm_slots(self) -> list[Dict[str, Any]]:
        return [
            {**slot, "api_key": secret_store.get_secret(f"gemini_api_key_{slot['slot']}") or ""}
            for slot in self._configured_slots()
            if slot["enabled"] and slot["provider"] == "gemini"
        ]


configuration_service = ConfigurationService()
