"""SEC-17 (2026-11-13 security report): legacy webhook must never fall back to a hardcoded secret."""

import asyncio
import unittest

from fastapi import HTTPException

BURNED = ("XAUUSD_DEFAULT_SECRET", "DEV_SECRET_123", "XAUUSD_MASTER_SECRET_2026")


class TestWebhookSecretFailClosed(unittest.TestCase):
    def test_create_app_requires_token(self):
        from scripts.webhook_bridge import create_app

        with self.assertRaises(ValueError):
            create_app(dry_run=True)
        with self.assertRaises(ValueError):
            create_app(auth_token="", dry_run=True)
        with self.assertRaises(ValueError):
            create_app(auth_token="   ", dry_run=True)

    def test_create_app_rejects_burned_defaults(self):
        from scripts.webhook_bridge import create_app

        for token in BURNED:
            with self.subTest(token=token), self.assertRaises(ValueError):
                create_app(auth_token=token, dry_run=True)

    def test_resolve_secret_fails_closed(self):
        from scripts.webhook.auth import resolve_webhook_secret

        with self.assertRaises(SystemExit):
            resolve_webhook_secret(None, None)
        with self.assertRaises(SystemExit):
            resolve_webhook_secret(None, "XAUUSD_MASTER_SECRET_2026")
        self.assertEqual(resolve_webhook_secret("env-secret-value-0123456789", "cfg"), "env-secret-value-0123456789")
        self.assertEqual(resolve_webhook_secret(None, "cfg-secret-value-0123456789"), "cfg-secret-value-0123456789")

    def test_auth_rejects_wrong_and_accepts_right(self):
        from scripts.webhook.auth import make_verify_auth

        verify = make_verify_auth("right-token-value-0123456789")
        self.assertTrue(asyncio.run(verify(authorization="Bearer right-token-value-0123456789", x_webhook_secret=None)))
        with self.assertRaises(HTTPException):
            asyncio.run(verify(authorization="Bearer wrong", x_webhook_secret=None))
        with self.assertRaises(HTTPException):
            asyncio.run(verify(authorization=None, x_webhook_secret=None))


if __name__ == "__main__":
    unittest.main()
