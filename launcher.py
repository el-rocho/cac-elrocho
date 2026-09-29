"""Punto de entrada de escritorio para Analíticas Clínicas.

El servidor sigue siendo FastAPI, pero se expone únicamente en loopback y se
vincula al ciclo de vida de la ventana nativa de pywebview. Este módulo no
importa ``webview`` hasta que se va a mostrar la interfaz para que las pruebas
del backend y los despliegues Docker no necesiten dependencias gráficas.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

import uvicorn

from app import __version__

LOGGER = logging.getLogger("analiticas.desktop")
LOOPBACK_HOST = "127.0.0.1"
STARTUP_TIMEOUT_SECONDS = 20
WINDOW_INITIAL_WIDTH = 1280
WINDOW_INITIAL_HEIGHT = 840
WINDOW_MINIMUM_SIZE = (960, 640)
WINDOW_TITLE = f"CAC El Rocho v{__version__}"
GITHUB_LATEST_RELEASE_URL = "https://api.github.com/repos/el-rocho/cac-elrocho/releases/latest"
UPDATE_INFORMATION_URL = "https://cac.elrocho.es/"
UPDATE_CHECK_TIMEOUT_SECONDS = 3


class ServerStartupError(RuntimeError):
    """El backend local no llegó a estar disponible a tiempo."""


@dataclass(frozen=True)
class AvailableUpdate:
    """Datos mínimos de una actualización publicada para mostrar al usuario."""

    version: str
    url: str


def version_components(version: str) -> tuple[int, ...] | None:
    """Convierte versiones de releases como ``v0.9.7`` en una tupla comparable."""
    normalized = version.strip().removeprefix("v")
    parts = normalized.split(".")
    if not parts or len(parts) > 4 or any(not part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def find_available_update() -> AvailableUpdate | None:
    """Consulta GitHub y devuelve solo releases estables más nuevas.

    Un fallo de red, una instalación sin Internet o una respuesta no esperada
    no afectan al uso normal de la aplicación: simplemente no se muestra aviso.
    """
    installed_version = version_components(__version__)
    if installed_version is None:
        LOGGER.warning("La versión instalada no tiene un formato comparable: %s", __version__)
        return None

    request = Request(
        GITHUB_LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "CAC-El-Rocho-update-check"},
    )
    try:
        with urlopen(request, timeout=UPDATE_CHECK_TIMEOUT_SECONDS) as response:  # noqa: S310 - URL fija de releases.
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, UnicodeDecodeError, json.JSONDecodeError) as error:
        LOGGER.info("No se pudo comprobar si hay actualizaciones: %s", error)
        return None

    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        return None

    published_version = payload.get("tag_name")
    if not isinstance(published_version, str):
        return None

    available_version = version_components(published_version)
    if available_version is None or available_version <= installed_version:
        return None
    return AvailableUpdate(version=published_version.removeprefix("v"), url=UPDATE_INFORMATION_URL)


def notify_available_update(window, update: AvailableUpdate) -> None:
    """Pide al frontend que muestre el aviso, una vez que ya está cargado."""
    payload = json.dumps({"version": update.version, "url": update.url})
    try:
        window.evaluate_js(f"window.showUpdateAvailable({payload});")
    except Exception as error:
        # La ventana puede haberse cerrado mientras terminaba la consulta.
        LOGGER.info("No se pudo mostrar el aviso de actualización: %s", error)


def check_for_update_after_window_load(window) -> None:
    """Lanza la consulta en segundo plano para no retrasar la ventana principal."""
    def worker() -> None:
        update = find_available_update()
        if update is not None:
            notify_available_update(window, update)

    threading.Thread(target=worker, name="analiticas-update-check", daemon=True).start()


def reserve_loopback_port() -> int:
    """Obtiene un puerto libre del sistema, limitado a la interfaz local."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((LOOPBACK_HOST, 0))
        return int(probe.getsockname()[1])


@dataclass
class LocalServer:
    """Servidor Uvicorn que puede finalizarse desde el evento de la ventana."""

    port: int
    server: uvicorn.Server
    thread: threading.Thread

    @property
    def url(self) -> str:
        return f"http://{LOOPBACK_HOST}:{self.port}/"

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            LOGGER.warning("El servidor local no terminó dentro del tiempo previsto.")


def start_local_server(port: int | None = None) -> LocalServer:
    """Inicia FastAPI sin abrir ningún puerto accesible desde la red."""
    selected_port = port if port is not None else reserve_loopback_port()
    config = uvicorn.Config(
        "app.main:app",
        host=LOOPBACK_HOST,
        port=selected_port,
        log_level="info",
        access_log=False,
        # La configuración predeterminada de Uvicorn usa formateadores
        # resueltos mediante cadenas. En una aplicación congelada esos módulos
        # pueden no estar importados todavía; el logging estándar ya está
        # configurado por ``run_desktop`` y no necesita esa resolución dinámica.
        log_config=None,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="analiticas-fastapi", daemon=True)
    thread.start()
    return LocalServer(port=selected_port, server=server, thread=thread)


def wait_until_available(local_server: LocalServer, timeout: float = STARTUP_TIMEOUT_SECONDS) -> None:
    """Comprueba la disponibilidad HTTP, detectando también fallos de arranque."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not local_server.thread.is_alive():
            raise ServerStartupError("El servidor local se detuvo durante el arranque.")
        try:
            with urlopen(local_server.url, timeout=0.5) as response:  # noqa: S310 - URL local fija.
                if 200 <= response.status < 500:
                    return
        except (OSError, URLError):
            time.sleep(0.1)
    raise ServerStartupError("No se pudo iniciar el servidor local de Analíticas Clínicas.")


def run_desktop() -> None:
    """Muestra la aplicación y garantiza una parada ordenada al cerrar la ventana."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    local_server = start_local_server()
    try:
        wait_until_available(local_server)

        import webview

        window = webview.create_window(
            title=WINDOW_TITLE,
            url=local_server.url,
            width=WINDOW_INITIAL_WIDTH,
            height=WINDOW_INITIAL_HEIGHT,
            min_size=WINDOW_MINIMUM_SIZE,
            resizable=True,
        )
        window.events.closed += local_server.stop
        # La consulta se inicia después de cargar la interfaz y en un hilo
        # independiente; sin conexión, la aplicación se abre exactamente igual.
        window.events.loaded += lambda: check_for_update_after_window_load(window)
        webview.start()
    except Exception:
        local_server.stop()
        raise
    finally:
        if local_server.thread.is_alive():
            local_server.stop()


def show_startup_error(error: Exception) -> None:
    """Informa de un fallo aunque el ejecutable se haya creado sin consola."""
    try:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        messagebox.showerror(
            "Analíticas Clínicas no pudo iniciarse",
            f"No se pudo abrir la aplicación.\n\n{error}",
        )
        root.destroy()
    except Exception:
        # La excepción original sigue quedando registrada cuando hay consola.
        pass


if __name__ == "__main__":
    try:
        run_desktop()
    except Exception as exc:
        LOGGER.exception("No se pudo iniciar el cliente de escritorio.")
        show_startup_error(exc)
