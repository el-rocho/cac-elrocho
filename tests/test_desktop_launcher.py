"""Pruebas unitarias del ciclo de vida del lanzador de escritorio."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

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

    def test_version_components_accepts_release_tags_only(self):
        self.assertEqual(launcher.version_components("v1.10.3"), (1, 10, 3))
        self.assertEqual(launcher.version_components(" 2.0 "), (2, 0))
        self.assertIsNone(launcher.version_components("v1.0.0-beta"))
        self.assertIsNone(launcher.version_components("latest"))

    @patch("launcher.urlopen")
    def test_finds_a_newer_stable_github_release(self, mock_urlopen):
        response = Mock()
        response.read.return_value = b'{"tag_name":"v0.9.9"}'
        mock_urlopen.return_value.__enter__.return_value = response

        update = launcher.find_available_update()

        self.assertEqual(update, launcher.AvailableUpdate(
            version="0.9.9",
            url="https://cac.elrocho.es/",
        ))
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, launcher.GITHUB_LATEST_RELEASE_URL)
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], launcher.UPDATE_CHECK_TIMEOUT_SECONDS)

    @patch("launcher.urlopen")
    def test_does_not_notify_for_current_or_prerelease(self, mock_urlopen):
        response = Mock()
        response.read.return_value = b'{"tag_name":"v0.9.7","html_url":"https://example.test/release"}'
        mock_urlopen.return_value.__enter__.return_value = response
        self.assertIsNone(launcher.find_available_update())

        response.read.return_value = b'{"tag_name":"v9.0.0","html_url":"https://example.test/release","prerelease":true}'
        self.assertIsNone(launcher.find_available_update())

    def test_notification_passes_safe_json_to_frontend(self):
        window = Mock()

        launcher.notify_available_update(window, launcher.AvailableUpdate("1.2.0", "https://example.test/release"))

        script = window.evaluate_js.call_args.args[0]
        self.assertIn('"version": "1.2.0"', script)
        self.assertIn('"url": "https://example.test/release"', script)
