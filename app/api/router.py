from fastapi import APIRouter
from app import __version__
from app.api.analiticas import router as analiticas_router
from app.api.upload import router as upload_router
from app.api.ai_review import router as ai_router
from app.api.backup import router as backup_router
from app.api.settings import router as settings_router

api_router = APIRouter(prefix="/api/v1")

@api_router.get("/health")
def health_check():
    return {"status": "ok", "app": "cac-elrocho", "version": __version__}

api_router.include_router(analiticas_router)
api_router.include_router(upload_router)
api_router.include_router(ai_router)
api_router.include_router(backup_router)
api_router.include_router(settings_router)
