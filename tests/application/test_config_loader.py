import os
import tempfile
import unittest
from unittest.mock import patch

from scripts.config_loader import ConfigError, load_config


class ConfigLoaderTests(unittest.TestCase):
    def test_load_config_applies_env_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = os.path.join(tmp, "settings.yaml")
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(
                    """
mt5:
  login: 0
  password: ""
  server: ""
  symbol: "XAUUSD"
telegram:
  enabled: false
strategy: {}
""",
                )

            with patch.dict(
                os.environ,
                {
                    "XAUUSD_MT5_LOGIN": "12345",
                    "XAUUSD_MT5_PASSWORD": "secret",
                    "XAUUSD_MT5_SERVER": "Demo-Server",
                },
                clear=True,
            ):
                config = load_config(config_path)

            self.assertEqual(config["mt5"]["login"], 12345)
            self.assertEqual(config["mt5"]["password"], "secret")
            self.assertEqual(config["mt5"]["server"], "Demo-Server")
            self.assertEqual(config["runtime"]["log_level"], "INFO")
            self.assertIs(config["news"]["enabled"], False)

    def test_load_config_requires_mt5_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = os.path.join(tmp, "settings.yaml")
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(
                    """
mt5:
  login: 0
  password: ""
  server: ""
  symbol: "XAUUSD"
telegram:
  enabled: false
""",
                )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "Missing MT5 login"):
                    load_config(config_path)

    def test_telegram_enabled_requires_real_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = os.path.join(tmp, "settings.yaml")
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(
                    """
mt5:
  login: 12345
  password: "secret"
  server: "Demo-Server"
  symbol: "XAUUSD"
telegram:
  enabled: true
  token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
""",
                )

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ConfigError, "Telegram is enabled"):
                    load_config(config_path)


if __name__ == "__main__":
    unittest.main()
