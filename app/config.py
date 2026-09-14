import os
from pathlib import Path
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
    
    # Inteligencia Artificial (LLM Gemini)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini") # 'gemini' o 'mock'
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # Seguridad básica opcional
    AUTH_ENABLED: bool = False
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"
    SECRET_KEY: str = "cac-elrocho-secret-key-change-me"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

# Asegurar directorios
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.INBOX_DIR.mkdir(parents=True, exist_ok=True)
(settings.DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
