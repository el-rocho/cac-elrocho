"""Protecciones reutilizables para rutas de administración local."""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import settings


basic_auth = HTTPBasic(auto_error=False)


def require_settings_access(
    credentials: HTTPBasicCredentials | None = Depends(basic_auth),
) -> None:
    """Protege los cambios de configuración cuando AUTH_ENABLED está activo."""
    if not settings.AUTH_ENABLED:
        return
    valid = bool(credentials) and secrets.compare_digest(
        credentials.username.encode("utf-8"), settings.ADMIN_USERNAME.encode("utf-8")
    ) and secrets.compare_digest(
        credentials.password.encode("utf-8"), settings.ADMIN_PASSWORD.encode("utf-8")
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requieren credenciales de administración.",
            headers={"WWW-Authenticate": "Basic"},
        )
