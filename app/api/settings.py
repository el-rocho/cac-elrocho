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


def _slot_secret_name(slot: int) -> str:
    return f"gemini_api_key_{slot}"


@router.put("/ai/credentials/{slot}", status_code=204)
def save_ai_credential(payload: AICredentialsUpdate, slot: int = Path(ge=1, le=3)):
    try:
        secret_store.set_secret(_slot_secret_name(slot), payload.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.delete("/ai/credentials/{slot}", status_code=204)
def remove_ai_credential(slot: int = Path(ge=1, le=3)):
    try:
        secret_store.delete_secret(_slot_secret_name(slot))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/ai/test/{slot}")
async def test_ai_connection(slot: int = Path(ge=1, le=3)):
    ai = configuration_service.get_ai_config()
    selected_slot = ai["slots"][slot - 1]
    if not selected_slot["enabled"] or selected_slot["provider"] != "gemini":
        raise HTTPException(status_code=400, detail="Activa Gemini en este slot antes de comprobarlo.")
    api_key = secret_store.get_secret(_slot_secret_name(slot))
    if not api_key:
        raise HTTPException(status_code=400, detail="No hay una credencial de Gemini configurada para este slot.")
    try:
        # Una instrucción muy corta limita el coste y evita devolver contenido
        # de la respuesta del proveedor a la interfaz. Este límite es propio
        # de la comprobación: una extracción de PDF puede requerir más tiempo.
        from app.services.llm_service import check_gemini_connection
        await asyncio.wait_for(
            asyncio.to_thread(check_gemini_connection, selected_slot["model"], api_key, 15_000),
            timeout=20,
        )
        return {"status": "ok", "message": f"Conexión con Gemini verificada para el slot {slot}."}
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Gemini tardó más de 20 segundos en responder. Revisa la conectividad o inténtalo de nuevo.",
        ) from exc
    except Exception as exc:
        # No exponemos el texto completo del proveedor (puede incluir detalles
        # operativos), pero sí distinguimos cuota de indisponibilidad temporal.
        provider_error = str(exc).lower()
        if "429" in provider_error or "resourceexhausted" in provider_error or "quota" in provider_error:
            raise HTTPException(
                status_code=429,
                detail="La cuota de Gemini para este modelo está agotada. Prueba otro slot o espera a su renovación.",
            ) from exc
        if "503" in provider_error or "unavailable" in provider_error or "overloaded" in provider_error:
            raise HTTPException(
                status_code=503,
                detail="Gemini tiene alta demanda temporal. Espera unos minutos o prueba otro modelo o credencial.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="No se pudo validar Gemini. Revisa la credencial, el modelo, la cuota y la conectividad.",
        ) from exc
