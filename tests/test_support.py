"""Inicialización segura de la base temporal compartida por la suite."""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path


_initialized = False
_created_root: Path | None = None


def initialize_test_environment() -> Path:
    """Fuerza un almacenamiento de pruebas antes de importar módulos de app.

    ``ANALITICAS_TEST_DATA_DIR`` permite que CI comparta el mismo directorio
    temporal entre la preparación de datos demo y los tests.
    """
    global _initialized, _created_root
    if _initialized:
        return _created_root  # type: ignore[return-value]

    configured_root = os.environ.get("ANALITICAS_TEST_DATA_DIR")
    root = Path(configured_root) if configured_root else Path(tempfile.mkdtemp(prefix="analiticas-tests-"))
    root.mkdir(parents=True, exist_ok=True)
    _created_root = root

    # BaseSettings da prioridad a estas variables de proceso sobre .env.
    os.environ["APP_DATA_DIR"] = str(root)
    os.environ["DATABASE_URL"] = f"sqlite:///{(root / 'data' / 'analiticas.db').as_posix()}"
    os.environ["DATA_DIR"] = str(root / "data")
    os.environ["INBOX_DIR"] = str(root / "inbox")
    os.environ["AUTH_ENABLED"] = "false"

    from app.seed_data import run_seed
    run_seed()

    def cleanup() -> None:
        # TestClient no ejecuta el ciclo de vida de FastAPI cuando se instancia
        # sin context manager; liberar el pool evita conexiones SQLite abiertas.
        from app.database import close_database
        close_database()
        if not configured_root:
            shutil.rmtree(root, ignore_errors=True)

    atexit.register(cleanup)
    _initialized = True
    return root
