import re
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from app import __version__

from app.config import settings
from app.database import init_db, SessionLocal, close_database
from app.services.watcher import inbox_watcher
from app.services.backup_service import backfill_informe_hashes
from app.services.db_harmonizer import harmonize_database_records
from app.api.router import api_router

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("cac-elrocho")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicialización de la base de datos
    logger.info("Iniciando cac-elrocho: verificando base de datos SQLite...")
    init_db()
    
    # Backfill de hashes SHA-256 para informes existentes
    backfill_informe_hashes()

    # Armonización automática de unidades y escalas en la base de datos
    try:
        with SessionLocal() as db_session:
            harmonize_database_records(db_session)
    except Exception as e:
        logger.warning(f"Aviso al armonizar base de datos: {e}")

    # Iniciar monitor de buzón en segundo plano
    inbox_watcher.start()
    
    yield
    
    # Finalización
    logger.info("Deteniendo servicios de cac-elrocho...")
    inbox_watcher.stop()
    close_database()

app = FastAPI(
    title="cac-elrocho",
    description="Panel Clínico Autónomo y Cuadro de Mando de Analíticas con Validación LLM",
    version=__version__,
    lifespan=lifespan
)

# Solo se habilitan orígenes administrativos declarados. La interfaz propia se
# sirve desde el mismo origen y no depende de CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conectar rutas de la API REST
app.include_router(api_router)

# Servir archivos estáticos del frontend
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Los recursos de marca viven fuera del paquete ``app`` para que puedan
# reutilizarse en el ejecutable y el instalador. PyInstaller los copia como
# hermanos del paquete en la distribución congelada.
branding_dir = Path(__file__).resolve().parent.parent / "assets"
if branding_dir.exists():
    app.mount("/branding", StaticFiles(directory=str(branding_dir)), name="branding")

import time

@app.get("/")
async def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        html = index_file.read_text(encoding="utf-8")
        # Inyección dinámica de la versión en el footer para evitar desincronizaciones
        html = re.sub(
            r'id="footer-app-version">[^<]*<',
            f'id="footer-app-version">v{__version__}<',
            html
        )
        # Inyección dinámica de timestamp para app.js para evitar problemas de caché del navegador
        html = re.sub(
            r'src="/static/app\.js\?v=[^"]*"',
            f'src="/static/app.js?v={int(time.time())}"',
            html
        )
        return HTMLResponse(
            content=html,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"message": "cac-elrocho API activa. Visita /docs para la documentación interactiva."}
