"""Utilidades de tiempo consistentes para la persistencia de la aplicación."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Devuelve el instante actual con zona horaria UTC explícita."""
    return datetime.now(timezone.utc)
