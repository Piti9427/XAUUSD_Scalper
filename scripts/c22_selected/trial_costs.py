"""Fresh regular-swap assumptions for a Demo trial, never economic attestation."""

from datetime import datetime, time, timedelta, timezone
import hashlib
import json
import math
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


def _utc(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("trial_cost_aware_utc_required")
    return stamp


def _number(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("trial_cost_numeric_evidence_required")
    if not math.isfinite(value) or (positive and value <= 0):
        raise ValueError("trial_cost_numeric_evidence_invalid")
    return float(value)


def _bound(document):
    return {"document": document,
            "sha256": hashlib.sha256(json.dumps(document, sort_keys=True, allow_nan=False).encode()).hexdigest()}


def build_trial_policy(broker_bytes: bytes, *, now, sources: dict) -> dict:
    """Bind a fresh flat Demo export and public schedule without zero fallback.

    Regular published swap is an operational assumption. Account swap entitlement
    and dated Personal Area exceptions remain unverified. Existing exact broker
    cost-drift checks are retained; actual swap differences can block new entries.
    """
    try:
        return _build_trial_policy(broker_bytes, now=now, sources=sources)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError("trial_cost_evidence_missing_or_malformed") from exc


def _build_trial_policy(broker_bytes, *, now, sources):
    now = _utc(now)
    broker = json.loads(broker_bytes)
    captured = _utc(broker["captured_utc"])
    if not timedelta(0) <= now - captured <= timedelta(minutes=5):
        raise ValueError("trial_cost_fresh_broker_evidence_required")
    account, spec = broker["account"], broker["spec"]
    fingerprint = broker["account_fingerprint"]
    history_end = _utc(broker["history_end_utc"])
    if not (
        broker["account_type"] == "Standard Demo"
        and broker["demo_verified"] is True and broker["hedging_verified"] is True
        and type(broker["positions"]) is int and broker["positions"] == 0
        and type(broker["orders"]) is int and broker["orders"] == 0
        and broker["symbol"] == "XAUUSDm" and broker["order_send_called"] is False
        and broker["terminal"]["connected"] is True
        and account["currency"] == "USD" and spec["currency_profit"] == "USD"
        and isinstance(fingerprint, str) and len(fingerprint) == 16
        and all(char in "0123456789abcdef" for char in fingerprint)
    ):
        raise ValueError("trial_cost_flat_standard_demo_identity_required")
    balance = _number(account["balance"], positive=True)
    equity = _number(account["equity"], positive=True)
    if abs(balance - equity) > 0.02:
        raise ValueError("trial_cost_flat_balance_equity_mismatch")
    if not (
        broker["history_complete"] is True
        and _utc(broker["history_start_utc"]) == datetime(1970, 1, 1, tzinfo=timezone.utc)
        and captured - timedelta(minutes=5) <= history_end <= captured
    ):
        raise ValueError("trial_cost_complete_epoch_history_required")
    ledger = broker["history_deals"]
    if (not isinstance(ledger, list) or not ledger or type(broker["history_deals_total"]) is not int
            or broker["history_deals_total"] != len(ledger)):
        raise ValueError("trial_cost_history_count_mismatch")
    cash = []
    tickets = set()
    for deal in ledger:
        ticket = deal["ticket"]
        if type(ticket) is not int or ticket <= 0 or ticket in tickets:
            raise ValueError("trial_cost_invalid_deal_identity")
        tickets.add(ticket)
        if type(deal["type"]) is not int or deal["type"] < 0:
            raise ValueError("trial_cost_invalid_deal_type")
        stamp = _number(deal["time_msc"])
        if not 0 <= stamp <= history_end.timestamp() * 1000:
            raise ValueError("trial_cost_invalid_deal_time")
        amounts = {name: _number(deal[name]) for name in ("profit", "commission", "swap", "fee")}
        if deal["type"] in (0, 1) and any(amounts[name] != 0 for name in ("commission", "fee")):
            raise ValueError("trial_cost_actual_charges_contradict_standard_zero_tariff")
        cash.extend(amounts.values())
    if abs(math.fsum(cash) - balance) > 0.02:
        raise ValueError("trial_cost_epoch_cash_does_not_reconcile")
    for name in ("trade_contract_size", "trade_tick_size", "point", "volume_min", "volume_max", "volume_step"):
        _number(spec[name], positive=True)
    for name in ("swap_long", "swap_short"):
        _number(spec[name])
    if type(spec["swap_mode"]) is not int or spec["swap_mode"] != 1:
        raise ValueError("trial_cost_supported_points_swap_mode_required")
    if type(spec["swap_rollover3days"]) is not int or spec["swap_rollover3days"] != 3:
        raise ValueError("trial_cost_published_wednesday_triple_must_match_spec")
    reviewed_sources = {}
    for name in ("tariff", "swap", "calendar"):
        source = sources[name]
        url = urlparse(source["source"])
        checked = _utc(source["checked_utc"])
        if not (url.scheme == "https" and url.hostname in ("www.exness.com", "get.exness.help")
                and url.username is None and url.password is None
                and timedelta(0) <= now - checked <= timedelta(hours=24)):
            raise ValueError("trial_cost_fresh_official_source_required")
        reviewed_sources[name] = dict(source=source["source"], checked_utc=checked.isoformat())
    days = {}
    conversion = _number(spec["point"], positive=True) * _number(spec["trade_contract_size"], positive=True)
    for offset in range(8):
        day = now.date() + timedelta(days=offset)
        rollover = datetime.combine(day, time(17), tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)
        factor = 0 if day.weekday() >= 5 else 3 if day.weekday() == 2 else 1
        days[day.isoformat()] = {
            "rollover_utc": rollover.isoformat(),
            "buy": _number(spec["swap_long"]) * conversion * factor,
            "sell": _number(spec["swap_short"]) * conversion * factor,
        }
    evidence_sha = hashlib.sha256(broker_bytes).hexdigest()
    spec_keys = ("trade_contract_size", "trade_tick_size", "point", "volume_min", "volume_max",
                 "volume_step", "swap_mode", "swap_long", "swap_short", "swap_rollover3days")
    tariff = dict(reviewed_sources["tariff"], account_type="Standard Demo", unit="USD_per_lot_round_trip",
                  commission_per_lot=0.0, basis="Published Standard tariff plus zero observed trade commissions/fees")
    spec_doc = dict(source="Fresh dedicated Demo SDK symbol_info XAUUSDm", captured_utc=captured.isoformat(),
                    broker_evidence_sha256=evidence_sha, fields={key: spec[key] for key in spec_keys})
    calendar = dict(reviewed_sources["swap"], holiday_source=reviewed_sources["calendar"],
                    unit="USD_per_lot", days=days, broker_holiday_exceptions_verified=False,
                    assumptions=["Regular SDK POINTS swap * point * contract_size, in USD per lot",
                                 "Published Wednesday triple and weekend zero, rollover17:00 America/New_York",
                                 "Account swap entitlement UNKNOWN; no claim of swap-free entitlement",
                                 "Dated broker/Personal Area holiday exceptions are NOT attested",
                                 "Current regular schedule is an assumption, not a guaranteed cost ceiling",
                                 "Existing exact observed-swap drift guard remains; differences block new entries"])
    return {
        "status": "CONSERVATIVE_REGULAR_SWAP_DEMO_ASSUMPTIONS", "version": 2,
        "account_type": "Standard Demo", "account_fingerprint": fingerprint,
        "account_evidence_sha256": evidence_sha, "reviewed_utc": now.isoformat(),
        "commission_per_lot": 0.0, "commission_unit": "USD_per_lot_round_trip",
        "commission_source": reviewed_sources["tariff"]["source"], "commission_from_symbol_info": False,
        "slippage_allowance_price": 0.1, "slippage_basis": "declared_assumption", "spread_buffer": 0,
        "source": "Fresh broker facts with published regular-swap Demo assumptions; account entitlement unknown",
        "swap_entitlement": "UNKNOWN", "research_economic_qualification": "COST_INCONCLUSIVE",
        "execution_authorized": False, "history_cash_reconciled": True,
        "evidence": {"tariff": _bound(tariff), "spec": _bound(spec_doc), "swap_calendar": _bound(calendar)},
    }
