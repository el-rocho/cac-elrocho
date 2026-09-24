"""API pública y segura para preferencias de instalación y credenciales de IA."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.schemas import AIConfigurationUpdate, AICredentialsUpdate
from app.security import require_settings_access
from app.services.configuration_service import configuration_service
from app.services.secret_store import secret_store


router = APIRouter(
    prefix="/settings",
    tags=["Configuración"],
    dependencies=[Depends(require_settings_access)],
)


@router.get("")
def get_settings():
    # No se incluye la ruta local ni ningún secreto: no son preferencias que la
    # interfaz pueda modificar libremente.
    return {"ai": configuration_service.get_ai_config()}


@router.patch("")
def update_settings(payload: AIConfigurationUpdate):
    try:
        return {"ai": configuration_service.update_ai_config(payload.model_dump(exclude_none=True))}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/ai")
def get_ai_settings():
    return configuration_service.get_ai_config()


@router.patch("/ai")
def update_ai_settings(payload: AIConfigurationUpdate):
    try:
        return configuration_service.update_ai_config(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.put("/ai/credentials", status_code=204)
def save_ai_credential(payload: AICredentialsUpdate):
    try:
        secret_store.set_secret("gemini_api_key", payload.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.delete("/ai/credentials", status_code=204)
def remove_ai_credential():
    try:
        secret_store.delete_secret("gemini_api_key")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/ai/test")
async def test_ai_connection():
    ai = configuration_service.get_ai_config()
    if ai["provider"] != "gemini":
        raise HTTPException(status_code=400, detail="Gemini no está seleccionado como proveedor.")
    api_key = secret_store.get_secret("gemini_api_key")
    if not api_key:
        raise HTTPException(status_code=400, detail="No hay una credencial de Gemini configurada.")
    try:
        # Una instrucción muy corta limita el coste y evita devolver contenido
        # de la respuesta del proveedor a la interfaz.
        from app.services.llm_service import call_gemini_model
        await call_gemini_model("Responde solo OK.", ai["model"], api_key)
        return {"status": "ok", "message": "Conexión con Gemini verificada."}
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="No se pudo validar Gemini. Revisa la credencial, el modelo, la cuota y la conectividad.",
        )
