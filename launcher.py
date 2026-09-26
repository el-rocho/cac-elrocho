"""Punto de entrada de escritorio para Analíticas Clínicas.

El servidor sigue siendo FastAPI, pero se expone únicamente en loopback y se
vincula al ciclo de vida de la ventana nativa de pywebview. Este módulo no
importa ``webview`` hasta que se va a mostrar la interfaz para que las pruebas
del backend y los despliegues Docker no necesiten dependencias gráficas.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

from app import __version__

LOGGER = logging.getLogger("analiticas.desktop")
LOOPBACK_HOST = "127.0.0.1"
STARTUP_TIMEOUT_SECONDS = 20
WINDOW_INITIAL_WIDTH = 1280
WINDOW_INITIAL_HEIGHT = 840
WINDOW_MINIMUM_SIZE = (960, 640)
WINDOW_TITLE = f"CAC El Rocho v{__version__}"


class ServerStartupError(RuntimeError):
    """El backend local no llegó a estar disponible a tiempo."""


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
