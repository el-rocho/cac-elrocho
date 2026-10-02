"""API pública y segura para preferencias de instalación y credenciales de IA."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Path

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


def _slot_secret_name(slot: int, provider: str) -> str:
    return f"{provider}_api_key_{slot}"


def _gemini_error_detail(exc: Exception) -> str:
    """Conserva literalmente el diagnóstico que entrega el SDK de Gemini."""
    error_text = str(exc)
    # Algunas excepciones de red no tienen texto. En ese caso el nombre de la
    # excepción sigue ofreciendo un diagnóstico útil (p. ej. ``TimeoutError``).
    return error_text or type(exc).__name__


@router.put("/ai/credentials/{slot}", status_code=204)
def save_ai_credential(payload: AICredentialsUpdate, slot: int = Path(ge=1, le=3)):
    try:
        secret_store.set_secret(_slot_secret_name(slot, payload.provider), payload.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.delete("/ai/credentials/{slot}", status_code=204)
def remove_ai_credential(slot: int = Path(ge=1, le=3)):
    provider = configuration_service.get_ai_config()["slots"][slot - 1]["provider"]
    if provider not in {"gemini", "openai", "deepseek"}:
        raise HTTPException(status_code=400, detail="Selecciona un proveedor antes de eliminar su credencial.")
    try:
        secret_store.delete_secret(_slot_secret_name(slot, provider))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/ai/test/{slot}")
async def test_ai_connection(slot: int = Path(ge=1, le=3)):
    ai = configuration_service.get_ai_config()
    selected_slot = ai["slots"][slot - 1]
    provider = selected_slot["provider"]
    provider_label = {"gemini": "Gemini", "openai": "OpenAI", "deepseek": "DeepSeek"}.get(provider, provider)
    if not selected_slot["enabled"] or provider not in {"gemini", "openai", "deepseek"}:
        raise HTTPException(status_code=400, detail="Activa un proveedor de IA en este slot antes de comprobarlo.")
    api_key = secret_store.get_secret(_slot_secret_name(slot, provider))
    if not api_key:
        raise HTTPException(status_code=400, detail=f"No hay una credencial de {provider_label} configurada para este slot.")
    try:
        # Una instrucción muy corta limita el coste y evita devolver contenido
        # de la respuesta del proveedor a la interfaz. Este límite es propio
        # de la comprobación: una extracción de PDF puede requerir más tiempo.
        from app.services.llm_service import check_deepseek_connection, check_gemini_connection, check_openai_connection
        check_connection = {
            "gemini": check_gemini_connection,
            "openai": check_openai_connection,
            "deepseek": check_deepseek_connection,
        }[provider]
        await asyncio.wait_for(
            asyncio.to_thread(check_connection, selected_slot["model"], api_key, 15_000),
            timeout=20,
        )
        return {"status": "ok", "message": f"Conexión con {provider_label} verificada para el slot {slot}."}
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=(
                f"TIMEOUT: {provider_label} tardó más de 20 segundos en responder. "
                f"Error exacto: {_gemini_error_detail(exc)}"
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"{provider_label} devolvió el siguiente error: {_gemini_error_detail(exc)}",
        ) from exc
