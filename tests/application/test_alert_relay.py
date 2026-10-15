import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from scripts.alert_relay import create_alert_relay


class Notifier:
    def __init__(self):
        self.messages = []

    async def send_message(self, message):
        self.messages.append(message)


class AlertRelayTests(unittest.TestCase):
    def setUp(self):
        self.notifier = Notifier()
        self.client = TestClient(create_alert_relay("secret", self.notifier))
        self.payload = {
            "schema_version": "2",
            "secret": "secret",
            "event_id": "evt-1",
            "setup_id": "setup-1",
            "event": "SIMULATED_ENTRY",
            "simulation": True,
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "engine": "SMC",
            "contributors": ["SMC"],
            "direction": "long",
            "event_time_utc": datetime.now(timezone.utc).isoformat(),
            "message": "demo only",
        }

    def test_accepts_simulated_alert_once(self):
        self.assertEqual(202, self.client.post("/api/v2/alerts", json=self.payload).status_code)
        duplicate = self.client.post("/api/v2/alerts", json=self.payload)
        self.assertEqual("duplicate", duplicate.json()["status"])
        self.assertEqual(1, len(self.notifier.messages))

    def test_rejects_wrong_secret_and_live_event(self):
        bad = dict(self.payload, secret="wrong", event_id="evt-2")
        self.assertEqual(401, self.client.post("/api/v2/alerts", json=bad).status_code)
        live = dict(self.payload, simulation=False, event_id="evt-3")
        self.assertEqual(422, self.client.post("/api/v2/alerts", json=live).status_code)


if __name__ == "__main__":
    unittest.main()
