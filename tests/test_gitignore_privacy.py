"""Guardia de privacidad: la base de datos y sus copias nunca se publican.

Comprueba que ``.gitignore`` cubre la base SQLite (y sus auxiliares), las copias
de seguridad, los volúmenes de datos y los secretos, y que ninguno de esos
ficheros está ya rastreado por Git.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Rutas de ejemplo que deben quedar siempre fuera del repositorio, existan o no.
RUTAS_SENSIBLES = (
    "data/analiticas.db",
    "data/analiticas.db-wal",
    "data/analiticas.db-shm",
    "data/analiticas.db-journal",
    "data/uploads/informe.pdf",
    "data/uploads/historial.csv",
    "analiticas.db",
    "analiticas.sqlite",
    "analiticas.sqlite3",
    "respaldo.db3",
    "respaldo.sqlite-journal",
    "inbox/informe.pdf",
    "backups/cac-elrocho-backup-20260101_120000.json",
    "backups/respaldo-cifrado-backup-20260101.json",
    "logs/cac-elrocho.log",
    "config/config.json",
    "config/llm-credentials.json",
    "config/llm-credentials.key",
    ".env",
    ".env.local",
)

# Cualquier fichero rastreado que case con estos patrones es un fallo grave.
PATRONES_PROHIBIDOS = (
    r"\.(db|db3|sqlite|sqlite3)$",
    r"\.(db|db3|sqlite|sqlite3)-(wal|shm|journal)$",
    r"backup.*\.json$",
    r"^data/",
    r"^backups/",
    r"^logs/",
    r"^inbox/",
)


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


class TestGitignorePrivacidad(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
            raise unittest.SkipTest("No hay repositorio Git disponible")

    def test_la_base_de_datos_esta_ignorada(self) -> None:
        for ruta in RUTAS_SENSIBLES:
            with self.subTest(ruta=ruta):
                resultado = _git("check-ignore", "-q", ruta)
                self.assertEqual(
                    resultado.returncode,
                    0,
                    f"{ruta} no está cubierto por .gitignore",
                )

    def test_ningun_fichero_sensible_esta_rastreado(self) -> None:
        rastreados = _git("ls-files").stdout.splitlines()
        self.assertTrue(rastreados, "git ls-files no devolvió ningún fichero")
        for ruta in rastreados:
            for patron in PATRONES_PROHIBIDOS:
                with self.subTest(ruta=ruta, patron=patron):
                    self.assertIsNone(
                        re.search(patron, ruta),
                        f"{ruta} coincide con {patron} y no debería estar en el repositorio",
                    )


if __name__ == "__main__":
    unittest.main()
