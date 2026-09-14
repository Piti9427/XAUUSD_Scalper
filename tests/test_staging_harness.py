import unittest
import os
import tempfile
import yaml
from scripts.run_staging_bridge import load_config
from scripts.webhook_bridge import create_app
from fastapi.testclient import TestClient


class TestStagingHarness(unittest.TestCase):
    """Ticket 06 & 07: Staging runner configuration and live deployment validation."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "test_settings.yaml")
        sample_config = {
            "webhook": {
                "host": "127.0.0.1",
                "port": 9000,
                "secret_token": "CUSTOM_STAGING_TOKEN_999",
                "dry_run": True,
                "account_balance": 50000.0,
                "risk_pct": 0.005,
                "max_daily_losses": 3,
                "rollover_hour_utc": 21,
                "rollover_minute_utc": 0,
            }
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(sample_config, f)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_staging_config(self):
        cfg = load_config(self.config_path)
        wh = cfg.get("webhook", {})
        self.assertEqual(wh["host"], "127.0.0.1")
        self.assertEqual(wh["port"], 9000)
        self.assertEqual(wh["secret_token"], "CUSTOM_STAGING_TOKEN_999")
        self.assertEqual(wh["account_balance"], 50000.0)
        self.assertEqual(wh["risk_pct"], 0.005)

    def test_app_creation_from_staging_config(self):
        cfg = load_config(self.config_path)
        wh = cfg.get("webhook", {})
        db_path = os.path.join(self.temp_dir.name, "staging.db")
        app = create_app(
            auth_token=wh["secret_token"],
            dry_run=wh["dry_run"],
            db_path=db_path,
            account_balance=wh["account_balance"],
            risk_pct=wh["risk_pct"],
            max_daily_losses=wh["max_daily_losses"],
        )
        client = TestClient(app)
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
