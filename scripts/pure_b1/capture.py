"""Bounded, immutable MT5 M15 Bid + Bid/Ask tick capture for Pure B1 parity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import scripts.smc.risk as risk_module
import scripts.strategy as strategy_module

from scripts.pure_b1.broker_data import completed_m15, completed_m15_from_m1, m1_gap_events
from scripts.pure_b1.provenance import module_sha256, sha256_file
from scripts.pure_b1.quote_time import FRESH_QUOTE
from scripts.research.shadow_capture import capture as capture_ticks
from scripts.smc.broker_rates import rates_to_frame


def _sha256(path: Path) -> str:
    return sha256_file(path)


def _check_account(mt5, *, login: int, server: str) -> str:
    account = mt5.account_info()
    if (
        account is None
        or int(account.login) != login
        or str(account.server) != server
        or int(account.trade_mode) != int(mt5.ACCOUNT_TRADE_MODE_DEMO)
        or str(account.currency) != "USD"
    ):
        raise ValueError("capture target Demo account changed")
    return hashlib.sha256(f"{account.server}:{account.login}".encode()).hexdigest()[:16]


def _terminal_quote_events(mt5, *, symbol: str, now: datetime) -> tuple[dict, list[dict]]:
    info = mt5.symbol_info(symbol)
    if info is None or str(getattr(info, "name", "")) != symbol or "XAUUSD" not in symbol:
        raise ValueError("capture symbol_info mismatch")
    tick = mt5.symbol_info_tick(symbol)
    if tick is None or not getattr(tick, "time_msc", 0):
        raise ValueError("capture symbol_info_tick unavailable")
    quote_time = datetime.fromtimestamp(int(tick.time_msc) / 1000, timezone.utc)
    age = (now - quote_time).total_seconds()
    snapshot = {
        "quote_utc": quote_time.isoformat(),
        "quote_age_seconds": age,
        "bid": float(tick.bid),
        "ask": float(tick.ask),
        "quote_rule": FRESH_QUOTE.name,
    }
    events = []
    if quote_time > now:
        events.append(
            {
                "type": "terminal_clock_ahead",
                "quote_utc": quote_time.isoformat(),
                "clock_utc": now.isoformat(),
                "cause": "quote_after_capture_clock",
                "late_entry": False,
            }
        )
    elif age > FRESH_QUOTE.max_age_seconds:
        events.append(
            {
                "type": "stale_quote",
                "quote_utc": quote_time.isoformat(),
                "quote_age_seconds": age,
                "cause": "quote_older_than_60s",
                "late_entry": False,
            }
        )
    return snapshot, events


def capture_window(
    mt5,
    *,
    start: datetime,
    end: datetime,
    freeze_at: datetime,
    symbol: str,
    expected_login: int,
    expected_server: str,
    output: Path,
) -> dict:
    """Capture at most one UTC day; caller owns MT5 initialize/shutdown."""
    if output.exists():
        raise FileExistsError(output)
    if (
        any(
            stamp.tzinfo is None or stamp.utcoffset() != timedelta(0)
            for stamp in (start, end, freeze_at)
        )
        or not freeze_at <= start < end
        or end - start > timedelta(days=1)
    ):
        raise ValueError("invalid bounded UTC capture window")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="pure_b1_capture_", dir=output.parent) as temporary:
        staging = Path(temporary)
        fingerprint = _check_account(mt5, login=expected_login, server=expected_server)
        quote_snapshot, quote_events = _terminal_quote_events(mt5, symbol=symbol, now=end)
        terminal_rates = mt5.copy_rates_range(
            symbol, mt5.TIMEFRAME_M15, start - timedelta(days=30), end
        )
        m1_rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start - timedelta(days=30), end)
        if _check_account(mt5, login=expected_login, server=expected_server) != fingerprint:
            raise ValueError("capture account changed during bar read")
        terminal_bars = completed_m15(terminal_rates, now=end)
        bar_events = m1_gap_events(m1_rates, now=end) + quote_events
        bars = completed_m15_from_m1(m1_rates, now=end)
        if bars.index[-1] < start:
            raise ValueError("M15 capture does not cover requested window")
        tick_manifest = capture_ticks(
            mt5,
            start=start,
            end=end,
            freeze_at=freeze_at,
            symbol=symbol,
            expected_login=expected_login,
            expected_server=expected_server,
            output=staging / "ticks",
        )
        if _check_account(mt5, login=expected_login, server=expected_server) != fingerprint:
            raise ValueError("capture account changed during tick read")
        bar_file = staging / "m15_bid.csv"
        terminal_file = staging / "m15_terminal.csv"
        m1_file = staging / "m1_bid.csv"
        bars.to_csv(bar_file, index_label="bar_open_utc")
        terminal_bars.to_csv(terminal_file, index_label="bar_open_utc")
        rates_to_frame(m1_rates).to_csv(m1_file, index=False)
        manifest = {
            "schema": "pure-b1-broker-capture-v2",
            "status": "captured_research_only",
            "order_api_called": False,
            "symbol": symbol,
            "account_fingerprint": fingerprint,
            "requested_start_utc": start.isoformat(),
            "requested_end_utc": end.isoformat(),
            "freeze_at_utc": freeze_at.isoformat(),
            "m15_source": "complete 15/15 MT5 Bid M1 bars, matching archived reference",
            "terminal_m15_source": "MetaTrader5.copy_rates_range(TIMEFRAME_M15)",
            "m1_source": "MetaTrader5.copy_rates_range(TIMEFRAME_M1)",
            "m1_sha256": _sha256(m1_file),
            "terminal_m15_sha256": _sha256(terminal_file),
            "terminal_m15_bars": len(terminal_bars),
            "m15_bars": len(bars),
            "first_m15_open_utc": bars.index[0].isoformat(),
            "last_m15_open_utc": bars.index[-1].isoformat(),
            "m15_sha256": _sha256(bar_file),
            "capture_code_sha256": _sha256(Path(__file__)),
            "bar_adapter_sha256": _sha256(Path(__file__).with_name("broker_data.py")),
            "strategy_sha256": module_sha256(strategy_module),
            "risk_sha256": module_sha256(risk_module),
            "quote_rule": FRESH_QUOTE.name,
            "terminal_quote": quote_snapshot,
            "bar_events": bar_events,
            "late_entries": 0,
            "tick_source": tick_manifest["source"],
            "tick_count": tick_manifest["tick_count"],
            "tick_sha256": tick_manifest["tick_sha256"],
            "tick_manifest_sha256": _sha256(staging / "ticks" / "manifest.json"),
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (staging / "COMPLETE").write_text("Read-only Exness capture; research only.\n")
        staging.rename(output)
    return manifest
