"""Contratos del frontend que permiten ejecutarlo sin acceso a Internet."""

from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestFrontendDistribution(unittest.TestCase):
    def test_packaged_styles_are_local_and_not_loaded_from_a_cdn(self):
        index = (PROJECT_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
        tailwind = PROJECT_ROOT / "app" / "static" / "vendor" / "tailwind.min.css"

        self.assertTrue(tailwind.is_file())
        self.assertGreater(tailwind.stat().st_size, 10_000)
        self.assertIn('/static/vendor/tailwind.min.css', index)
        self.assertNotIn("cdn.tailwindcss.com", index)
        self.assertNotIn("fonts.googleapis.com", index)

    def test_paginador_de_gestion_sigue_integrado(self):
        """La pestaña 4 pagina el registro: 15 informes por página."""
        index = (PROJECT_ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
        app_js = (PROJECT_ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")

        for elemento in ("audit-pager", "audit-pager-prev", "audit-pager-next", "audit-pager-range"):
            self.assertIn(f'id="{elemento}"', index, f"falta {elemento} en index.html")

        self.assertIn("const AUDIT_PAGE_SIZE = 15;", app_js)
        for funcion in ("function renderAuditTable", "function irAPaginaAudit", "function syncAuditPager"):
            self.assertIn(funcion, app_js, f"falta {funcion} en app.js")

        # La página se reinicia cuando llegan datos nuevos (importar, restaurar, borrar todo).
        self.assertGreaterEqual(app_js.count("reiniciarPagina: true"), 4)
        # El tramo visible siempre sale del tamaño de página declarado.
        self.assertGreaterEqual(app_js.count("AUDIT_PAGE_SIZE"), 4)
