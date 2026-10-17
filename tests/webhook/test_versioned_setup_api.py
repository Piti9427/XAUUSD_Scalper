import unittest
from fastapi.testclient import TestClient
from scripts.webhook_bridge import create_app


class TestVersionedSetupAPIRemoved(unittest.TestCase):
    """Verify that unspecced /api/v1/setup endpoint is removed (F1)."""

    def test_versioned_setup_returns_404(self):
        app = create_app(auth_token="TEST_TOKEN", dry_run=True)
        try:
            client = TestClient(app)
            payload = {
                "order_id": "V1_SETUP_1",
                "symbol": "XAUUSD",
                "dir": "BUY",
                "limit": 4050.0,
                "sl": 4045.0,
            }
            res = client.post(
                "/api/v1/setup",
                json=payload,
                headers={"Authorization": "Bearer TEST_TOKEN"},
            )
            self.assertEqual(res.status_code, 404)
        finally:
            if hasattr(app.state, "adapter") and app.state.adapter:
                app.state.adapter.close()
