"""Offline MT5 deal exports with explicit cash, grouping and cost coverage.

No account connection or attestation occurs here. A matched comparison describes
only supplied dated documents and observed closed ledgers, never future costs.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
from typing import Any

from scripts.demo_runtime.costs import validate_evidence
from scripts.qualification.c22.artifacts import make_report, parse_utc, read_json, source_ref


CASH_FIELDS = ("profit", "commission", "fee", "swap")
VOLUME_TOLERANCE = 1e-8
SWAP_TOLERANCE = 0.02  # Same USD tolerance as observed runtime cost checks.


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"invalid_{name}")
    return value


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"invalid_{name}")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError(f"invalid_{name}")
    return result


def _normalize(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("deal_not_object")
    try:
        row: dict[str, Any] = {key: _number(raw[key], key) for key in CASH_FIELDS}
        for key in ("ticket", "position_id", "type", "entry", "time_msc"):
            row[key] = _integer(raw[key], key, minimum=1 if key == "ticket" else 0)
        row["utc"] = datetime.fromtimestamp(row["time_msc"] / 1000, timezone.utc).isoformat()
        if row["type"] in (0, 1):
            if row["position_id"] == 0:
                raise ValueError("trade_position_id_missing")
            row["magic"] = _integer(raw["magic"], "magic")
            row["volume"] = _number(raw["volume"], "volume", positive=True)
            row["price"] = _number(raw["price"], "price", positive=True)
            row["symbol"] = raw["symbol"]
            if not isinstance(row["symbol"], str) or not row["symbol"].strip():
                raise ValueError("trade_symbol_missing")
        return row
    except KeyError as exc:
        raise ValueError(f"deal_field_missing:{exc.args[0]}") from exc
    except (OverflowError, OSError) as exc:
        raise ValueError("invalid_time_msc") from exc


def _cash(rows: list[dict[str, Any]]) -> dict[str, float]:
    amounts = {key: math.fsum(row[key] for row in rows) for key in CASH_FIELDS}
    amounts["net"] = math.fsum(amounts.values())
    return amounts


def _position(
    ident: int, deals: list[dict[str, Any]], currency: str | None, invalid: bool = False
) -> dict[str, Any]:
    entries = [row for row in deals if row["entry"] == 0]
    exits = [row for row in deals if row["entry"] == 1]
    entry_volume = math.fsum(row["volume"] for row in entries)
    exit_volume = math.fsum(row["volume"] for row in exits)
    reasons = []
    unsupported = any(row["entry"] not in (0, 1) for row in deals)
    side = entries[0]["type"] if entries else None
    if len({row["symbol"] for row in deals}) > 1:
        invalid = True
        reasons.append("position_symbol_changed")
    if entries and any(row["type"] != side for row in entries):
        unsupported = True
        reasons.append("mixed_entry_directions")
    if entries and any(row["type"] == side for row in exits):
        invalid = True
        reasons.append("exit_direction_not_opposite")
    if entries and not unsupported:
        remaining = 0.0
        for row in deals:
            remaining += row["volume"] * (1 if row["entry"] == 0 else -1)
            if remaining < -VOLUME_TOLERANCE:
                invalid = True
                reasons.append("exit_exceeds_observed_entry_volume")
                break
    if invalid:
        status = "INVALID"
        reasons.append("invalid_or_conflicting_deal")
    elif unsupported:
        status = "UNSUPPORTED"
        reasons.append("unsupported_entry_mode")
    elif not entries:
        status = "ORPHAN"
        reasons.append("entry_not_in_export")
    elif not exits or entry_volume - exit_volume > VOLUME_TOLERANCE:
        status = "OPEN"
        reasons.append("unclosed_observed_volume")
    else:
        status = "COMPLETE"
    return dict(
        position_id=ident, status=status, reasons=sorted(set(reasons)),
        symbol=deals[0]["symbol"] if deals else None,
        magic_values=sorted({row["magic"] for row in deals}),
        side={0: "BUY", 1: "SELL"}.get(side) if side is not None else None,
        deal_ids=[row["ticket"] for row in deals],
        deal_count=len(deals), entry_volume=entry_volume, exit_volume=exit_volume,
        outstanding_volume=entry_volume - exit_volume,
        opened_utc=entries[0]["utc"] if entries else None,
        closed_utc=exits[-1]["utc"] if status == "COMPLETE" else None,
        observed=_cash(deals) if not invalid else None, currency=currency,
        comparison=dict(status="NOT_COMPARED", reasons=["position_not_complete"]),
        slippage=dict(status="NOT_MEASURED", reason="no_supported_contemporaneous_decision_quote"),
    )


def _policy_reasons(policy: Any, fingerprint: Any, currency: str | None) -> list[str]:
    reasons = []
    if currency != "USD":
        reasons.append("account_currency_missing_or_not_usd")
    if not isinstance(policy, dict):
        return reasons + ["historical_cost_policy_missing"]
    if policy.get("version") != 2 or not validate_evidence(policy):
        reasons.append("policy_evidence_hash_schema_or_unit_invalid")
    try:
        if _number(policy["commission_per_lot"], "commission_per_lot") < 0:
            raise ValueError("negative_tariff")
    except (KeyError, ValueError):
        reasons.append("commission_allowance_missing_or_invalid")
    if not fingerprint or policy.get("account_fingerprint") != fingerprint:
        reasons.append("policy_account_not_matched")
    if policy.get("status") not in ("SUPPORTED_HISTORICAL_DOCUMENTS", "REVIEWED_DEMO_ASSUMPTIONS"):
        reasons.append("historical_policy_support_not_declared")
    if policy.get("pending_checks"):
        reasons.append("policy_checks_pending")
    try:
        parse_utc(policy["reviewed_utc"])
    except (KeyError, TypeError, ValueError):
        reasons.append("policy_review_time_missing_or_invalid")
    return sorted(set(reasons))


def _compare(
    position: dict[str, Any], rows: list[dict[str, Any]], policy: Any,
    common_reasons: list[str],
) -> dict[str, Any]:
    if position["status"] != "COMPLETE":
        return position["comparison"]
    reasons = list(common_reasons)
    if reasons:
        return dict(status="COST_INCONCLUSIVE", reasons=reasons)
    opened, closed = parse_utc(position["opened_utc"]), parse_utc(position["closed_utc"])
    documents = policy["evidence"]
    for name in ("tariff", "spec"):
        try:
            doc = documents[name]["document"]
            start, end = parse_utc(doc["effective_from_utc"]), parse_utc(doc["effective_until_utc"])
            if not start <= opened <= closed < end:
                reasons.append(f"historical_{name}_period_not_covered")
        except (KeyError, TypeError, ValueError):
            reasons.append(f"historical_{name}_period_missing_or_invalid")
    calendar = documents["swap_calendar"]["document"]["days"]
    day = opened.replace(hour=0, minute=0, second=0, microsecond=0)
    rollovers = []
    while day.date() <= closed.date():
        key = day.date().isoformat()
        if key not in calendar:
            reasons.append(f"historical_swap_calendar_missing:{key}")
        else:
            item = calendar[key]
            rollover = parse_utc(item["rollover_utc"])
            if opened < rollover <= closed:
                # Runtime semantics: all fills at the rollover timestamp count.
                held = math.fsum(
                    row["volume"] * (1 if row["entry"] == 0 else -1)
                    for row in rows if row["time_msc"] <= rollover.timestamp() * 1000
                )
                rate = float(item["buy" if position["side"] == "BUY" else "sell"])
                rollovers.append(dict(rollover_utc=rollover.isoformat(), held_lots=held,
                                      rate_usd_per_lot=rate, amount=rate * held))
        day += timedelta(days=1)
    if reasons:
        return dict(status="COST_INCONCLUSIVE", reasons=sorted(set(reasons)))
    modeled = math.fsum(row["amount"] for row in rollovers)
    observed = position["observed"]
    charges = math.fsum(max(0.0, -row["commission"]) + max(0.0, -row["fee"]) for row in rows)
    allowance = float(policy["commission_per_lot"]) * position["entry_volume"]
    delta = observed["swap"] - modeled
    if abs(delta) > SWAP_TOLERANCE:
        reasons.append("swap_drift")
    if charges > allowance + 1e-8:
        reasons.append("charge_allowance_exceeded")
    return dict(
        status="COST_DRIFT" if reasons else "OBSERVED_COSTS_MATCH", reasons=reasons,
        modeled_swap=modeled, observed_swap=observed["swap"], swap_delta=delta,
        observed_charges=charges, charge_allowance=allowance,
        charge_test="UPPER_ALLOWANCE_NOT_EXACT_TARIFF_EQUALITY", rollovers=rollovers,
        swap_tolerance_usd=SWAP_TOLERANCE, charge_tolerance_usd=1e-8,
    )


def reconcile_export(export_path: Path, policy_path: Path | None = None) -> dict[str, Any]:
    """Normalize one exported MT5 account snapshot; retain all exclusions.

    Deal fields are mandatory, including literal zero commission/fee/swap. IN/OUT
    trades are supported; INOUT/OUT_BY require another explicitly reviewed model.
    Dated tariff/spec periods are [effective_from_utc, effective_until_utc).
    """
    sources = [source_ref(export_path)]
    if policy_path is not None:
        sources.append(source_ref(policy_path))
    try:
        raw = read_json(export_path)
    except ValueError:
        return make_report("observed_cost_reconciliation", "INVALID", sources=sources,
                           coverage={}, reasons=["invalid_export_json"], positions=[], currency=None)
    if not isinstance(raw, dict) or not isinstance(raw.get("history_deals"), list):
        return make_report("observed_cost_reconciliation", "INVALID", sources=sources,
                           coverage={}, reasons=["mt5_history_deals_array_missing"], positions=[], currency=None)
    reasons = []
    stamps = {}
    for field in ("captured_utc", "history_start_utc"):
        try:
            if field == "captured_utc" or raw.get(field) is not None:
                stamps[field] = parse_utc(raw[field])
        except (KeyError, TypeError, ValueError):
            reasons.append(f"{field}_missing_or_invalid")
    account = raw.get("account") or {}
    currency = account.get("currency", raw.get("currency")) if isinstance(account, dict) else None
    if not isinstance(currency, str) or not currency.strip():
        currency = None
    fingerprint = raw.get("account_fingerprint")
    policy = None
    if policy_path is not None:
        try:
            policy = read_json(policy_path)
        except ValueError:
            reasons.append("invalid_policy_json")
    common_reasons = _policy_reasons(policy, fingerprint, currency)
    unique: dict[int, dict[str, Any]] = {}
    bad_positions: set[int] = set()
    errors: list[dict[str, Any]] = []
    duplicates = 0
    for index, item in enumerate(raw["history_deals"]):
        try:
            row = _normalize(item)
        except ValueError as exc:
            ident = item.get("position_id") if isinstance(item, dict) else None
            if isinstance(ident, int) and not isinstance(ident, bool) and ident > 0:
                bad_positions.add(ident)
            errors.append(dict(record_index=index, reason=str(exc)))
            continue
        previous = unique.get(row["ticket"])
        if previous is not None:
            if previous == row:
                duplicates += 1
            else:
                reasons.append("conflicting_duplicate_ticket")
                bad_positions.update((previous["position_id"], row["position_id"]))
                errors.append(dict(record_index=index, reason="conflicting_duplicate_ticket"))
            continue
        unique[row["ticket"]] = row
    if errors:
        reasons.append("invalid_deal_records")
    ordered = sorted(unique.values(), key=lambda row: (row["time_msc"], row["ticket"]))
    if ordered and "captured_utc" in stamps and ordered[-1]["time_msc"] > stamps["captured_utc"].timestamp() * 1000:
        reasons.append("deal_after_export_capture")
    if ordered and "history_start_utc" in stamps and ordered[0]["time_msc"] < stamps["history_start_utc"].timestamp() * 1000:
        reasons.append("deal_before_requested_history_start")
    grouped: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    nontrade: list[dict[str, Any]] = []
    for row in ordered:
        if row["type"] in (0, 1):
            grouped[row["position_id"]].append(row)
        else:
            nontrade.append(dict(deal_id=row["ticket"], utc=row["utc"], type=row["type"],
                                 observed=_cash([row]), reason="nontrade_cash_excluded_from_position_pnl"))
    positions = [_position(ident, deals, currency, ident in bad_positions)
                 for ident, deals in sorted(grouped.items())]
    # Preserve even positions whose every available deal was invalid.
    for ident in sorted(bad_positions - grouped.keys()):
        if ident > 0:
            positions.append(_position(ident, [], currency, True))
    pre_review = 0
    for position in positions:
        if position["status"] == "COMPLETE" and isinstance(policy, dict):
            try:
                position["pre_review"] = parse_utc(position["closed_utc"]) < parse_utc(policy["reviewed_utc"])
                pre_review += position["pre_review"]
            except (KeyError, TypeError, ValueError):
                position["pre_review"] = None
        else:
            position["pre_review"] = None
        position["comparison"] = _compare(position, grouped.get(position["position_id"], []), policy, common_reasons)
    compared = [row for row in positions if row["comparison"]["status"] in ("OBSERVED_COSTS_MATCH", "COST_DRIFT")]
    complete = [row for row in positions if row["status"] == "COMPLETE"]
    counts = {key: sum(row["status"] == status for row in positions) for key, status in (
        ("complete_positions", "COMPLETE"), ("open_positions", "OPEN"),
        ("orphan_positions", "ORPHAN"), ("unsupported_positions", "UNSUPPORTED"),
        ("invalid_positions", "INVALID"))}
    if reasons or counts["invalid_positions"]:
        status = "INVALID"
    elif any(row["comparison"]["status"] == "COST_DRIFT" for row in positions):
        status = "COST_DRIFT"
    elif complete and len(compared) == len(positions) == len(complete):
        status = "OBSERVED_COSTS_MATCH"
    else:
        status = "COST_INCONCLUSIVE"
    report_reasons = sorted(set(reasons + common_reasons + [reason for row in positions
        for reason in row["reasons"] + row["comparison"]["reasons"]]))
    if not positions:
        report_reasons.append("no_observed_trade_positions")
    coverage = dict(
        input_records=len(raw["history_deals"]), unique_deals=len(unique), duplicates_dropped=duplicates,
        trade_deals=sum(len(rows) for rows in grouped.values()), nontrade_deals=len(nontrade),
        invalid_deals=len(errors), position_count=len(positions), **counts,
        compared_positions=len(compared), unqualified_complete_positions=len(complete) - len(compared),
        pre_review_positions=pre_review,
        export_captured_utc=stamps["captured_utc"].isoformat() if "captured_utc" in stamps else None,
        history_requested_since_utc=stamps["history_start_utc"].isoformat() if "history_start_utc" in stamps else None,
        observed_first_utc=ordered[0]["utc"] if ordered else None,
        observed_last_utc=ordered[-1]["utc"] if ordered else None,
        provider_history_completeness="NOT_CERTIFIED", slippage="NOT_MEASURED",
    )
    trade_rows = [row for rows in grouped.values() for row in rows]
    coverage.update(
        observed_trade_first_utc=min(trade_rows, key=lambda row: row["time_msc"])["utc"] if trade_rows else None,
        observed_trade_last_utc=max(trade_rows, key=lambda row: row["time_msc"])["utc"] if trade_rows else None,
        input_reordered=list(unique.values()) != ordered,
    )
    totals = ({key: math.fsum(row["observed"][key] for row in complete)
               for key in (*CASH_FIELDS, "net")} if complete else None)
    return make_report(
        "observed_cost_reconciliation", status, sources=sources, coverage=coverage,
        reasons=report_reasons, currency=currency, account_fingerprint=fingerprint,
        positions=positions, nontrade_records=nontrade, invalid_records=errors,
        scope="ALL_EXPORTED_POSITIONS_NO_STRATEGY_FILTER",
        strategy_attribution="NOT_INFERRED_FROM_ACCOUNT_TOTALS",
        complete_position_cash=totals, policy_reviewed_utc=policy.get("reviewed_utc") if isinstance(policy, dict) else None,
        units=dict(cash=currency, volume="lot", price="symbol_price", timestamp="aware UTC"),
        ordering="time_msc_then_ticket", profitability="INCONCLUSIVE", cost_attestation_created=False,
        limitations=["Observed ledgers and supplied documents only; no historical completeness certification",
                     "Charge comparison checks an upper allowance, not exact tariff equality",
                     "Slippage requires a supported contemporaneous decision quote; none is inferred",
                     "No source policy is attested, renewed or modified by this report"],
    )
