import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from routes.terminals import (
    _websocket_client_allowed,
    require_loopback_terminal_client,
)


def _request(host: str) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/terminals/sessions",
            "raw_path": b"/terminals/sessions",
            "query_string": b"",
            "headers": [],
            "client": (host, 50000),
            "server": ("127.0.0.1", 8000),
        }
    )


class TerminalRouteSecurityTests(unittest.TestCase):
    def test_http_loopback_clients_are_allowed(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TERMINAL_ALLOW_REMOTE", None)
            require_loopback_terminal_client(_request("127.0.0.1"))
            require_loopback_terminal_client(_request("::1"))

    def test_http_remote_client_is_blocked_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TERMINAL_ALLOW_REMOTE", None)
            with self.assertRaises(HTTPException) as raised:
                require_loopback_terminal_client(_request("192.168.1.25"))

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(
            raised.exception.detail,
            "Terminal access is loopback-only",
        )

    def test_explicit_remote_setting_allows_http_control(self):
        with patch.dict(
            os.environ,
            {"TERMINAL_ALLOW_REMOTE": "true"},
            clear=False,
        ):
            require_loopback_terminal_client(_request("192.168.1.25"))

    def test_websocket_uses_the_same_loopback_policy(self):
        websocket = SimpleNamespace(
            client=SimpleNamespace(host="192.168.1.25")
        )
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TERMINAL_ALLOW_REMOTE", None)
            self.assertFalse(_websocket_client_allowed(websocket))

        with patch.dict(
            os.environ,
            {"TERMINAL_ALLOW_REMOTE": "1"},
            clear=False,
        ):
            self.assertTrue(_websocket_client_allowed(websocket))


if __name__ == "__main__":
    unittest.main()
