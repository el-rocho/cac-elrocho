import os
import time
import logging
from pathlib import Path
from threading import Thread
from app.config import settings

logger = logging.getLogger(__name__)

class InboxWatcher:
    """
    Monitor en segundo plano que vigila la carpeta /inbox
    para detectar la llegada de nuevos PDFs de analíticas.
    """
    def __init__(self, inbox_path: Path):
        self.inbox_path = inbox_path
        self.is_running = False
        self._thread = None

    def start(self):
        self.is_running = True
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"Monitor de buzón iniciado en: {self.inbox_path}")

    def stop(self):
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Monitor de buzón detenido.")

    def _run(self):
        while self.is_running:
            try:
                if self.inbox_path.exists():
                    for file_path in self.inbox_path.glob("*.pdf"):
                        # Esperar a que el archivo termine de escribirse
                        initial_size = file_path.stat().st_size
                        time.sleep(1)
                        if file_path.stat().st_size == initial_size and initial_size > 0:
                            logger.info(f"Nuevo PDF detectado en buzón: {file_path.name}")
                            # Procesamiento desatendido o preparación en cola
            except Exception as e:
                logger.error(f"Error en monitor de buzón: {e}")
            time.sleep(5)

inbox_watcher = InboxWatcher(settings.paths.inbox_dir)
