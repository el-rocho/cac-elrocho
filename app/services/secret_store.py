"""Almacén de credenciales independiente del backend de IA."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import settings


SERVICE_NAME = "analiticas-clinicas"


@dataclass(frozen=True)
class SecretStatus:
    configured: bool
    source: str | None
    managed_by_environment: bool


class SecretStore:
    """Usa el keyring del sistema cuando está disponible.

    Las credenciales declaradas por entorno son deliberadamente de solo
    lectura: en despliegues administrados el operador conserva el control.
    """

    def _environment_value(self, name: str) -> Optional[str]:
        if name != "gemini_api_key":
            return None
        for value in (settings.API_KEY1, settings.API_KEY2, settings.API_KEY3, settings.GEMINI_API_KEY):
            if value and value.strip() and not value.startswith("tu_clave_de_"):
                return value.strip()
        return None

    @staticmethod
    def _keyring():
        try:
            import keyring
            return keyring
        except Exception:
            return None

    def get_secret(self, name: str) -> Optional[str]:
        environment_value = self._environment_value(name)
        if environment_value:
            return environment_value
        keyring = self._keyring()
        if not keyring:
            return None
        try:
            return keyring.get_password(SERVICE_NAME, name)
        except Exception:
            return None

    def status(self, name: str) -> SecretStatus:
        environment_value = self._environment_value(name)
        if environment_value:
            return SecretStatus(True, "environment", True)
        value = self.get_secret(name)
        return SecretStatus(bool(value), "keyring" if value else None, False)

    def set_secret(self, name: str, value: str) -> None:
        if self._environment_value(name):
            raise ValueError("La credencial está administrada mediante variables de entorno.")
        if not value or not value.strip():
            raise ValueError("La credencial no puede estar vacía.")
        keyring = self._keyring()
        if not keyring:
            raise RuntimeError("No hay un almacén de credenciales disponible en este entorno.")
        try:
            keyring.set_password(SERVICE_NAME, name, value.strip())
        except Exception as exc:
            raise RuntimeError("No se pudo guardar la credencial en el almacén del sistema.") from exc

    def delete_secret(self, name: str) -> None:
        if self._environment_value(name):
            raise ValueError("La credencial está administrada mediante variables de entorno.")
        keyring = self._keyring()
        if not keyring:
            return
        try:
            keyring.delete_password(SERVICE_NAME, name)
        except Exception:
            # Un secreto inexistente equivale a un estado ya eliminado.
            return

    def has_secret(self, name: str) -> bool:
        return self.status(name).configured


secret_store = SecretStore()
