"""Pruebas unitarias del ciclo de vida del lanzador de escritorio."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

import launcher


class TestDesktopLauncher(unittest.TestCase):
    def test_reserved_port_is_a_valid_loopback_port(self):
        port = launcher.reserve_loopback_port()
        self.assertGreater(port, 0)
        self.assertLess(port, 65536)

    def test_stop_requests_uvicorn_shutdown_and_joins_thread(self):
        server = Mock()
        thread = Mock()
        thread.is_alive.return_value = False
        local_server = launcher.LocalServer(port=12345, server=server, thread=thread)

        local_server.stop()

        self.assertTrue(server.should_exit)
        thread.join.assert_called_once_with(timeout=10)

    def test_local_server_url_is_bound_to_loopback(self):
        local_server = launcher.LocalServer(port=23456, server=Mock(), thread=Mock())
        self.assertEqual(local_server.url, "http://127.0.0.1:23456/")
