import logging
import os
from copy import deepcopy
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


CONFIG_PATH = Path("config/settings.yaml")

ENV_OVERRIDES = {
    ("mt5", "login"): ("XAUUSD_MT5_LOGIN", int),
    ("mt5", "password"): ("XAUUSD_MT5_PASSWORD", str),
    ("mt5", "server"): ("XAUUSD_MT5_SERVER", str),
    ("mt5", "symbol"): ("XAUUSD_SYMBOL", str),
    ("telegram", "token"): ("XAUUSD_TELEGRAM_TOKEN", str),
    ("telegram", "chat_id"): ("XAUUSD_TELEGRAM_CHAT_ID", str),
    ("gws", "spreadsheet_id"): ("XAUUSD_GWS_SPREADSHEET_ID", str),
    ("gws", "doc_id"): ("XAUUSD_GWS_DOC_ID", str),
    ("gws", "cli_path"): ("XAUUSD_GWS_CLI_PATH", str),
}


class ConfigError(ValueError):
    """Raised when runtime configuration is missing or invalid."""


def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as f:
        raw_config = _load_yaml(f.read())

    config = deepcopy(raw_config)
    _apply_env_overrides(config)
    _set_defaults(config)
    validate_config(config)
    return config


def _load_yaml(text):
    if yaml is not None:
        return yaml.safe_load(text) or {}

    config = {}
    current_section = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current_section = line[:-1].strip()
            config[current_section] = {}
            continue
        if current_section and line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            config[current_section][key.strip()] = _parse_scalar(value.strip())
    return config


def _parse_scalar(value):
    if value in ("", "''", '""'):
        return ""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _apply_env_overrides(config):
    for key_path, (env_name, caster) in ENV_OVERRIDES.items():
        raw_value = os.getenv(env_name)
        if raw_value is None or raw_value == "":
            continue

        current = config
        for key in key_path[:-1]:
            current = current.setdefault(key, {})
        try:
            current[key_path[-1]] = caster(raw_value)
        except ValueError as exc:
            raise ConfigError(f"{env_name} has invalid value: {raw_value!r}") from exc


def _set_defaults(config):
    config.setdefault("runtime", {})
    config["runtime"].setdefault("log_level", "INFO")

    config.setdefault("news", {})
    config["news"].setdefault("enabled", False)
    config["news"].setdefault("impact_threshold", "HIGH")
    config["news"].setdefault("pause_window_mins", 60)

    config.setdefault("telegram", {})
    config["telegram"].setdefault("enabled", True)

    config.setdefault("gws", {})
    config["gws"].setdefault("enabled", True)
    config["gws"].setdefault(
        "cli_path",
        "/Users/nopparuj/.gemini/extensions/google-workspace-cli/npm/run.js",
    )


def validate_config(config):
    mt5 = config.get("mt5") or {}
    if not mt5.get("login"):
        raise ConfigError("Missing MT5 login. Set mt5.login or XAUUSD_MT5_LOGIN.")
    if not mt5.get("password"):
        raise ConfigError("Missing MT5 password. Set mt5.password or XAUUSD_MT5_PASSWORD.")
    if not mt5.get("server"):
        raise ConfigError("Missing MT5 server. Set mt5.server or XAUUSD_MT5_SERVER.")
    if not mt5.get("symbol"):
        raise ConfigError("Missing MT5 symbol. Set mt5.symbol or XAUUSD_SYMBOL.")

    telegram = config.get("telegram") or {}
    if telegram.get("enabled", True):
        token = telegram.get("token")
        chat_id = telegram.get("chat_id")
        if token in (None, "", "YOUR_BOT_TOKEN") or chat_id in (None, "", "YOUR_CHAT_ID"):
            raise ConfigError(
                "Telegram is enabled but token/chat_id is missing. "
                "Set XAUUSD_TELEGRAM_TOKEN and XAUUSD_TELEGRAM_CHAT_ID, "
                "or set telegram.enabled=false."
            )


def setup_logging(config):
    level_name = str(config.get("runtime", {}).get("log_level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
