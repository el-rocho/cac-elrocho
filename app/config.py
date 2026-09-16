import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "cac-elrocho"
    APP_ENV: str = "production"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Rutas relativas o absolutas
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = Path(os.getenv("DATA_DIR", "./data"))
    INBOX_DIR: Path = Path(os.getenv("INBOX_DIR", "./inbox"))
    
    # Base de Datos
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/analiticas.db")
    
    # Inteligencia Artificial (LLM) - Multi-modelo (hasta 3 slots configurables)
    LLM_PROVIDER1: Optional[str] = None
    API_KEY1: Optional[str] = None
    MODEL1: Optional[str] = None

    LLM_PROVIDER2: Optional[str] = None
    API_KEY2: Optional[str] = None
    MODEL2: Optional[str] = None

    LLM_PROVIDER3: Optional[str] = None
    API_KEY3: Optional[str] = None
    MODEL3: Optional[str] = None

    # Parámetros heredados (retrocompatibilidad)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini") # 'gemini' o 'mock'
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

    def get_configured_llm_slots(self) -> list:
        """
        Retorna la lista de slots LLM configurados por el usuario (del 1 al 3).
        Permite configurar 1, 2 o 3 modelos independientes con sus respectivas claves.
        """
        slots = []
        for i in (1, 2, 3):
            p = getattr(self, f"LLM_PROVIDER{i}", None)
            k = getattr(self, f"API_KEY{i}", None)
            m = getattr(self, f"MODEL{i}", None)

            p = (p or "").strip()
            k = (k or "").strip()
            m = (m or "").strip()

            if p or m or k:
                if not p:
                    p = "mock" if m.lower() == "mock" else "gemini"
                slots.append({
                    "slot": i,
                    "provider": p.lower(),
                    "api_key": k,
                    "model": m
                })

        # Retrocompatibilidad si no se configuró ningún slot 1, 2 o 3
        if not slots and (self.GEMINI_API_KEY or self.LLM_PROVIDER):
            slots.append({
                "slot": 1,
                "provider": (self.LLM_PROVIDER or "gemini").lower(),
                "api_key": self.GEMINI_API_KEY or "",
                "model": self.GEMINI_MODEL or "gemini-flash-lite-latest"
            })
        return slots
    
    # Seguridad básica opcional
    AUTH_ENABLED: bool = False
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    SECRET_KEY: str = "cac-elrocho-secret-key-change-me"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def resolve_paths(self):
        # Si estamos en Windows o fuera del contenedor Docker y la ruta apunta a /app/...
        if os.name == "nt" or not Path("/app").exists():
            str_data = str(self.DATA_DIR).replace("\\", "/")
            if str_data.startswith("/app/"):
                self.DATA_DIR = self.BASE_DIR / str_data[5:]
            str_inbox = str(self.INBOX_DIR).replace("\\", "/")
            if str_inbox.startswith("/app/"):
                self.INBOX_DIR = self.BASE_DIR / str_inbox[5:]
            if "/app/" in self.DATABASE_URL:
                db_rel = self.DATABASE_URL.split("/app/")[-1]
                db_path = (self.BASE_DIR / db_rel).resolve().as_posix()
                self.DATABASE_URL = f"sqlite:///{db_path}"
        return self

settings = Settings()

# Asegurar directorios
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.INBOX_DIR.mkdir(parents=True, exist_ok=True)
(settings.DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
