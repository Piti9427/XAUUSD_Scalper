import os
import tempfile
import unittest
from fastapi.testclient import TestClient

from scripts.webhook_bridge import create_app


class TestVersionedSetupAPI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_trades.db")
        self.secret_token = "SECRET_TOKEN_API_V1"
        self.app = create_app(
            auth_token=self.secret_token,
            dry_run=True,
            db_path=self.db_path,
        )
        self.client = TestClient(self.app)
        self.headers = {"Authorization": f"Bearer {self.secret_token}"}

    def tearDown(self):
        if hasattr(self.app.state, "adapter") and self.app.state.adapter:
            self.app.state.adapter.close()
        self.temp_dir.cleanup()

    def test_versioned_setup_accepts_valid_payload_with_202(self):
        payload = {
            "order_id": "V1_SETUP_1",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "limit": 4050.0,
            "sl": 4045.0,
            "tp1": 4055.0,
            "tp2": 4062.5,
            "type": "SMC_PRIME",
        }
        res = self.client.post("/api/v1/setup", json=payload, headers=self.headers)
        self.assertEqual(res.status_code, 202)
        data = res.json()
        self.assertEqual(data["status"], "accepted")
        self.assertEqual(data["order_id"], "V1_SETUP_1")
        self.assertTrue(bool(data.get("receipt_id")))

    def test_versioned_setup_duplicate_returns_200(self):
        payload = {
            "order_id": "V1_SETUP_DUP",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "limit": 4050.0,
            "sl": 4045.0,
            "tp1": 4055.0,
            "tp2": 4062.5,
        }
        res1 = self.client.post("/api/v1/setup", json=payload, headers=self.headers)
        self.assertEqual(res1.status_code, 202)
        receipt_id = res1.json()["receipt_id"]

        res2 = self.client.post("/api/v1/setup", json=payload, headers=self.headers)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(data2["status"], "ignored_duplicate")
        self.assertEqual(data2["receipt_id"], receipt_id)

    def test_versioned_setup_conflict_returns_409(self):
        payload = {
            "order_id": "V1_SETUP_CONFLICT",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "limit": 4050.0,
            "sl": 4045.0,
        }
        res1 = self.client.post("/api/v1/setup", json=payload, headers=self.headers)
        self.assertEqual(res1.status_code, 202)

        conflicting_payload = {**payload, "sl": 4044.0}
        res2 = self.client.post("/api/v1/setup", json=conflicting_payload, headers=self.headers)
        self.assertEqual(res2.status_code, 409)
        self.assertEqual(res2.json()["status"], "conflict")

    def test_versioned_setup_rejects_invalid_geometry_with_400(self):
        invalid_buy = {
            "order_id": "V1_GEOM_BUY",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "limit": 4040.0,
            "sl": 4050.0,  # BUY SL must be below entry limit
        }
        res_buy = self.client.post("/api/v1/setup", json=invalid_buy, headers=self.headers)
        self.assertEqual(res_buy.status_code, 400)
        self.assertIn("geometry", res_buy.json()["detail"].lower())

        invalid_sell = {
            "order_id": "V1_GEOM_SELL",
            "symbol": "XAUUSD",
            "dir": "SELL",
            "limit": 4060.0,
            "sl": 4050.0,  # SELL SL must be above entry limit
        }
        res_sell = self.client.post("/api/v1/setup", json=invalid_sell, headers=self.headers)
        self.assertEqual(res_sell.status_code, 400)
        self.assertIn("geometry", res_sell.json()["detail"].lower())

    def test_versioned_setup_rejects_missing_fields_with_400(self):
        incomplete = {
            "order_id": "V1_INCOMPLETE",
            "symbol": "XAUUSD",
            # missing dir, limit, sl
        }
        res = self.client.post("/api/v1/setup", json=incomplete, headers=self.headers)
        self.assertEqual(res.status_code, 400)

    def test_versioned_setup_busy_returns_409(self):
        payload1 = {
            "order_id": "V1_BUSY_1",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "limit": 4050.0,
            "sl": 4045.0,
        }
        res1 = self.client.post("/api/v1/setup", json=payload1, headers=self.headers)
        self.assertEqual(res1.status_code, 202)

        payload2 = {
            "order_id": "V1_BUSY_2",
            "symbol": "XAUUSD",
            "dir": "BUY",
            "limit": 4050.0,
            "sl": 4045.0,
        }
        res2 = self.client.post("/api/v1/setup", json=payload2, headers=self.headers)
        self.assertEqual(res2.status_code, 409)
        self.assertEqual(res2.json()["status"], "busy")
