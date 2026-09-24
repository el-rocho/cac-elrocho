"""Resolución centralizada de las rutas persistentes de la aplicación."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_FOLDER_NAME = "AnaliticasClinicas"


def _platform_data_dir() -> Path:
    """Devuelve una ubicación de datos apropiada para una instalación distribuida."""
    if os.name == "nt":
        local_app_data = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local_app_data) / APP_FOLDER_NAME
    xdg_data_home = os.getenv("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(xdg_data_home) / APP_FOLDER_NAME


@dataclass(frozen=True)
class AppPaths:
    """Todas las rutas persistentes derivadas de una única raíz de datos."""

    root: Path

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def database_file(self) -> Path:
        return self.data_dir / "analiticas.db"

    @property
    def uploads_dir(self) -> Path:
        # Se conserva este nombre para no romper el contrato actual de los informes.
        return self.data_dir / "uploads"

    @property
    def inbox_dir(self) -> Path:
        return self.root / "inbox"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    def ensure_directories(self) -> None:
        for directory in (
            self.data_dir,
            self.uploads_dir,
            self.inbox_dir,
            self.backups_dir,
            self.config_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
            if not os.access(directory, os.R_OK | os.W_OK):
                raise PermissionError(f"La aplicación no puede leer o escribir en: {directory}")


def default_data_root(base_dir: Path) -> Path:
    """Mantiene el árbol actual al ejecutar desde el código fuente.

    En una distribución sin el repositorio, el valor por defecto pasa a ser la
    carpeta de datos del usuario. Docker debe declarar APP_DATA_DIR=/app (o el
    punto de montaje que corresponda).
    """
    if (base_dir / ".git").exists():
        return base_dir
    if Path("/.dockerenv").exists():
        return Path("/app")
    return _platform_data_dir()
