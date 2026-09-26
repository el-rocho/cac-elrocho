"""Almacén de credenciales independiente del backend de IA."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import ctypes
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

SERVICE_NAME = "analiticas-clinicas"


@dataclass(frozen=True)
class SecretStatus:
    configured: bool
    source: str | None
    managed_by_environment: bool


class SecretStore:
    """Usa el keyring del sistema cuando está disponible.

    Las credenciales nunca se cargan desde archivos de configuración: cada
    slot tiene una entrada independiente en el almacén seguro del sistema.
    """

    @staticmethod
    def _keyring():
        try:
            import keyring
            return keyring
        except Exception:
            return None

    @staticmethod
    def _file_store_enabled() -> bool:
        """El fichero protegido está disponible como respaldo persistente.

        Un contenedor slim no suele disponer de un keyring del sistema. En
        desarrollo local también puede faltar un backend de keyring utilizable.
        """
        return True

    @staticmethod
    def _prefer_file_store() -> bool:
        """Docker usa siempre el volumen persistente, no un keyring efímero."""
        return Path("/.dockerenv").exists()

    @property
    def _credentials_file(self) -> Path:
        return settings.paths.config_dir / "llm-credentials.json"

    @property
    def _file_encryption_key_file(self) -> Path:
        """Clave local para el respaldo cifrado fuera de Windows.

        En Windows DPAPI vincula el secreto al perfil de usuario. En Docker y
        otros sistemas sin DPAPI se conserva una clave Fernet separada, con
        permisos de propietario, para que el fichero de credenciales nunca
        contenga las claves de Gemini en texto plano.
        """
        return settings.paths.config_dir / "llm-credentials.key"

    def _file_encryption_key(self) -> bytes:
        path = self._file_encryption_key_file
        try:
            key = path.read_bytes().strip()
            Fernet(key)
            return key
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            raise RuntimeError("No se pudo leer la clave de protección de credenciales.")

        path.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        descriptor, temporary_name = tempfile.mkstemp(prefix="llm-credentials-", suffix=".key", dir=path.parent)
        try:
            os.chmod(temporary_name, 0o600)
            with os.fdopen(descriptor, "wb") as temporary:
                temporary.write(key)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, path)
            os.chmod(path, 0o600)
            return key
        except Exception:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            finally:
                raise

    def _read_file_store(self) -> dict[str, str]:
        path = self._credentials_file
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                return {}
            secrets: dict[str, str] = {}
            for key, secret in value.items():
                if not isinstance(key, str) or not isinstance(secret, str):
                    continue
                decoded = self._unprotect_value(secret)
                if decoded is not None:
                    secrets[key] = decoded
            return secrets
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _dpapi(value: bytes, protect: bool) -> bytes:
        """Cifra o descifra bytes con el perfil del usuario actual de Windows."""
        class DataBlob(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        buffer = ctypes.create_string_buffer(value)
        source = DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        result = DataBlob()
        crypt32 = ctypes.windll.crypt32
        operation = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        succeeded = operation(
            ctypes.byref(source), None, None, None, None, 0, ctypes.byref(result)
        )
        if not succeeded:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(result.pbData, result.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(result.pbData)

    def _protect_value(self, value: str) -> str:
        """Protege el respaldo local con DPAPI para el usuario de Windows.

        ``chmod(0600)`` no aplica una ACL protectora en Windows. DPAPI está
        disponible en todas las versiones de Windows compatibles y permite que
        el respaldo siga siendo seguro incluso si Credential Manager o keyring
        no están disponibles (incluida una distribución congelada incompleta).
        """
        if os.name == "nt":
            try:
                encrypted = self._dpapi(value.encode("utf-8"), protect=True)
                return "dpapi:" + base64.b64encode(encrypted).decode("ascii")
            except Exception:
                # No se escribe texto plano si DPAPI no puede protegerlo.
                raise RuntimeError("No se pudo proteger la credencial con Windows DPAPI.")
        return "fernet:" + Fernet(self._file_encryption_key()).encrypt(value.encode("utf-8")).decode("ascii")

    def _unprotect_value(self, value: str) -> Optional[str]:
        if value.startswith("fernet:"):
            try:
                return Fernet(self._file_encryption_key()).decrypt(value.removeprefix("fernet:").encode("ascii")).decode("utf-8")
            except (InvalidToken, OSError, ValueError, UnicodeDecodeError):
                return None
        if not value.startswith("dpapi:"):
            # Compatibilidad de lectura para el respaldo creado por versiones
            # anteriores. La siguiente escritura lo migra a DPAPI.
            return value
        if os.name != "nt":
            return None
        try:
            encrypted = base64.b64decode(value.removeprefix("dpapi:"), validate=True)
            plaintext = self._dpapi(encrypted, protect=False)
            return plaintext.decode("utf-8")
        except Exception:
            return None

    def _write_file_store(self, values: dict[str, str]) -> None:
        path = self._credentials_file
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix="llm-credentials-", suffix=".json", dir=path.parent)
        try:
            os.chmod(temporary_name, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
                protected_values = {key: self._protect_value(secret) for key, secret in values.items()}
                json.dump(protected_values, temporary, ensure_ascii=False, indent=2, sort_keys=True)
                temporary.write("\n")
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, path)
            os.chmod(path, 0o600)
        except Exception:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            finally:
                raise

    def _keyring_value(self, name: str) -> Optional[str]:
        keyring = self._keyring()
        if not keyring:
            return None
        try:
            value = keyring.get_password(SERVICE_NAME, name)
            # Migración transparente de la única credencial que usaban las
            # versiones anteriores hacia el slot principal.
            if not value and name == "gemini_api_key_1":
                value = keyring.get_password(SERVICE_NAME, "gemini_api_key")
            return value
        except Exception:
            return None

    def get_secret(self, name: str) -> Optional[str]:
        if self._prefer_file_store():
            return self._read_file_store().get(name) if self._file_store_enabled() else None
        value = self._keyring_value(name)
        if value:
            return value
        return self._read_file_store().get(name) if self._file_store_enabled() else None

    def status(self, name: str) -> SecretStatus:
        if self._prefer_file_store():
            value = self._read_file_store().get(name)
            return SecretStatus(bool(value), "protected_file" if value else None, False)
        if self._keyring_value(name):
            return SecretStatus(True, "keyring", False)
        value = self._read_file_store().get(name) if self._file_store_enabled() else None
        return SecretStatus(bool(value), "protected_file" if value else None, False)

    def set_secret(self, name: str, value: str) -> None:
        if not value or not value.strip():
            raise ValueError("La credencial no puede estar vacía.")
        if self._prefer_file_store():
            values = self._read_file_store()
            values[name] = value.strip()
            try:
                self._write_file_store(values)
                return
            except OSError as exc:
                raise RuntimeError("No se pudo guardar la credencial en el volumen persistente.") from exc
        keyring = self._keyring()
        if keyring:
            try:
                keyring.set_password(SERVICE_NAME, name, value.strip())
                return
            except Exception:
                pass
        # El keyring puede estar instalado pero no disponer de backend (caso
        # habitual en entornos virtuales de desarrollo). En ese caso se usa el
        # fichero local separado, sin almacenar claves en .env.
        if self._file_store_enabled():
            values = self._read_file_store()
            values[name] = value.strip()
            try:
                self._write_file_store(values)
                return
            except OSError as exc:
                raise RuntimeError("No se pudo guardar la credencial local.") from exc
        raise RuntimeError("No hay un almacén de credenciales disponible en este entorno.")

    def delete_secret(self, name: str) -> None:
        if self._prefer_file_store():
            values = self._read_file_store()
            if name in values:
                del values[name]
                self._write_file_store(values)
            return
        keyring = self._keyring()
        if keyring:
            try:
                keyring.delete_password(SERVICE_NAME, name)
            except Exception:
                pass
        if self._file_store_enabled():
            values = self._read_file_store()
            if name in values:
                del values[name]
                self._write_file_store(values)

    def has_secret(self, name: str) -> bool:
        return self.status(name).configured


secret_store = SecretStore()
