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
