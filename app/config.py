import os
import sys
from pathlib import Path
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.paths import AppPaths, default_data_root


# Un .env del repositorio es útil en desarrollo, pero un ejecutable puede
# iniciarse desde cualquier directorio (incluido el repositorio original). En
# modo congelado no debe heredar por accidente valores de desarrollo; las
# credenciales del usuario se gestionan mediante SecretStore.
DOTENV_FILE = None if getattr(sys, "frozen", False) else ".env"

class Settings(BaseSettings):
    APP_NAME: str = "cac-elrocho"
    APP_ENV: str = "production"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # APP_DATA_DIR es la única raíz de datos persistentes. Las variables
    # heredadas se aceptan durante la transición, pero no se usan en negocio.
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    APP_DATA_DIR: Optional[Path] = None
    DATA_DIR: Optional[Path] = None
    INBOX_DIR: Optional[Path] = None
    DATABASE_URL: Optional[str] = None
    
    # Seguridad básica opcional
    AUTH_ENABLED: bool = False
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    SECRET_KEY: str = "cac-elrocho-secret-key-change-me"

    CORS_ORIGINS: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    model_config = SettingsConfigDict(
        env_file=DOTENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        enable_decoding=False,
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_list(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def _resolve_legacy_path(self, value: Path) -> Path:
        text = str(value).replace("\\", "/")
        if (text == "/app" or text.startswith("/app/")) and (os.name == "nt" or not Path("/app").exists()):
            return self.BASE_DIR / text.removeprefix("/app").lstrip("/")
        return value if value.is_absolute() else self.BASE_DIR / value

    @property
    def paths(self) -> AppPaths:
        if self.APP_DATA_DIR:
            root = self._resolve_legacy_path(self.APP_DATA_DIR)
        elif self.DATA_DIR:
            root = self._resolve_legacy_path(self.DATA_DIR).parent
        elif self.INBOX_DIR:
            root = self._resolve_legacy_path(self.INBOX_DIR).parent
        else:
            root = default_data_root(self.BASE_DIR)
        return AppPaths(root.resolve())

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            legacy_url = self.DATABASE_URL
            if "/app/" in legacy_url and (os.name == "nt" or not Path("/app").exists()):
                database_relative_path = legacy_url.split("/app/", 1)[1]
                database_path = (self.BASE_DIR / database_relative_path).resolve().as_posix()
                return f"sqlite:///{database_path}"
            return legacy_url
        return f"sqlite:///{self.paths.database_file.as_posix()}"

settings = Settings()
settings.paths.ensure_directories()
