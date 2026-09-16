import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.seed_data import run_seed
from app.services.watcher import inbox_watcher
from app.services.backup_service import backfill_informe_hashes
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
    if settings.APP_ENV == "demo":
        run_seed()
    
    # Backfill de hashes SHA-256 para informes existentes
    backfill_informe_hashes()

    # Iniciar monitor de buzón en segundo plano
    inbox_watcher.start()
    
    yield
    
    # Finalización
    logger.info("Deteniendo servicios de cac-elrocho...")
    inbox_watcher.stop()

app = FastAPI(
    title="cac-elrocho",
    description="Panel Clínico Autónomo y Cuadro de Mando de Analíticas con Validación LLM",
    version="0.3.0",
    lifespan=lifespan
)

# Soporte CORS para desarrollo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conectar rutas de la API REST
app.include_router(api_router)

# Servir archivos estáticos del frontend
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def serve_index():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "cac-elrocho API activa. Visita /docs para la documentación interactiva."}
