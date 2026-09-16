"""Tests for shared MT5 initialize path helper."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from scripts.smc.mt5_init import MT5_PATH_ENV, initialize_mt5, resolve_mt5_terminal_path


class FakeMT5:
    def __init__(self, ok: bool, last_error):
        self._ok = ok
        self._last_error = last_error
        self.kwargs = None

    def initialize(self, **kwargs):
        self.kwargs = kwargs
        return self._ok

    def last_error(self):
        return self._last_error


class MT5InitTests(unittest.TestCase):
    def test_resolve_prefers_explicit_path(self):
        self.assertEqual(
            resolve_mt5_terminal_path(path="C:\\MT5\\terminal64.exe", env={MT5_PATH_ENV: "ignored"}),
            "C:\\MT5\\terminal64.exe",
        )

    def test_resolve_uses_env(self):
        self.assertEqual(
            resolve_mt5_terminal_path(env={MT5_PATH_ENV: "C:\\env\\terminal64.exe"}),
            "C:\\env\\terminal64.exe",
        )

    def test_initialize_passes_path_and_classifies_auth_failure(self):
        mt5 = FakeMT5(False, (-6, "Terminal: Authorization failed"))
        result = initialize_mt5(mt5, path="C:\\Program Files\\MetaTrader 5\\terminal64.exe")
        self.assertFalse(result.ok)
        self.assertEqual(result.detail, "terminal_authorization_failed")
        self.assertEqual(result.last_error, (-6, "Terminal: Authorization failed"))
        self.assertEqual(mt5.kwargs["path"], "C:\\Program Files\\MetaTrader 5\\terminal64.exe")

    def test_initialize_classifies_ipc_missing(self):
        mt5 = FakeMT5(False, (-10003, "IPC initialize failed"))
        result = initialize_mt5(mt5)
        self.assertFalse(result.ok)
        self.assertEqual(result.detail, "ipc_terminal_not_found")

    def test_initialize_success(self):
        mt5 = FakeMT5(True, (1, "Success"))
        result = initialize_mt5(mt5, path="C:\\MT5\\terminal64.exe", timeout=10000)
        self.assertTrue(result.ok)
        self.assertEqual(result.detail, "initialized")
        self.assertEqual(mt5.kwargs["timeout"], 10000)

    def test_resolve_account_kwargs_from_xauusd_env(self):
        from scripts.smc.mt5_init import resolve_mt5_account_kwargs

        kwargs = resolve_mt5_account_kwargs(
            env={
                "XAUUSD_MT5_LOGIN": "12345678",
                "XAUUSD_MT5_PASSWORD": "secret",
                "XAUUSD_MT5_SERVER": "Exness-MT5Trial",
            }
        )
        self.assertEqual(
            kwargs,
            {"login": 12345678, "password": "secret", "server": "Exness-MT5Trial"},
        )

    def test_resolve_account_kwargs_incomplete_returns_empty(self):
        from scripts.smc.mt5_init import resolve_mt5_account_kwargs

        self.assertEqual(
            resolve_mt5_account_kwargs(env={"XAUUSD_MT5_LOGIN": "1"}),
            {},
        )

    def test_initialize_forwards_account_kwargs(self):
        mt5 = FakeMT5(True, (1, "Success"))
        result = initialize_mt5(
            mt5,
            path="C:\\MT5\\terminal64.exe",
            login=99,
            password="pw",
            server="Exness-MT5Trial",
        )
        self.assertTrue(result.ok)
        self.assertEqual(mt5.kwargs["login"], 99)
        self.assertEqual(mt5.kwargs["password"], "pw")
        self.assertEqual(mt5.kwargs["server"], "Exness-MT5Trial")


if __name__ == "__main__":
    unittest.main()
