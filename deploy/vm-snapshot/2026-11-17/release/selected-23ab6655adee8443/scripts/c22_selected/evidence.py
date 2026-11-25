"""Opt-in broker evidence from the existing sender's completed read seam.

No SDK reference, policy installation or entry authority lives here. A private
request file asks for an observation; immutable packet dates never advance on
retry. Financial processing finishes before optional packet IO begins.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile


def _utc(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("evidence_utc_required")
    return stamp


def _write_private(path, raw):
    """One sender owns this private directory; replace only complete bytes."""
    path = Path(path)
    descriptor, name = tempfile.mkstemp(prefix=".evidence-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _packet(snapshot, *, context, now):
    account, positions, orders, deals, info, started, observed, identity = snapshot
    if not timedelta(0) <= observed - started <= now - started <= timedelta(minutes=5):
        raise ValueError("evidence_read_window_stale")
    if positions or orders:
        raise ValueError("evidence_not_flat")
    if context.policy.get("account_type") != "Standard Demo":
        raise ValueError("evidence_account_type_unproven")
    if (int(account.trade_mode) != 0 or int(account.margin_mode) != 2 or account.currency != "USD"
            or identity.get("identity_terminal_connected") is not True):
        raise ValueError("evidence_demo_identity_unproven")
    amounts = [float(getattr(d, key)) for d in deals for key in ("profit", "commission", "swap", "fee")]
    if (not deals or not all(math.isfinite(x) for x in amounts)
            or not math.isfinite(float(account.balance)) or not math.isfinite(float(account.equity))
            or account.balance <= 0 or account.equity <= 0
            or abs(math.fsum(amounts) - account.balance) > 0.02
            or abs(account.balance - account.equity) > 0.02):
        raise ValueError("evidence_cash_not_reconciled")
    tickets = set()
    volumes = {}
    ledger = []
    for deal in deals:
        ticket, kind, stamp = int(deal.ticket), int(deal.type), int(deal.time_msc)
        if ticket <= 0 or ticket in tickets or kind < 0 or not 0 <= stamp <= started.timestamp() * 1000:
            raise ValueError("evidence_history_invalid")
        tickets.add(ticket)
        if kind in (0, 1):
            volume = float(deal.volume)
            if not math.isfinite(volume) or volume <= 0 or int(deal.entry) not in (0, 1, 3):
                raise ValueError("evidence_history_invalid")
            ident = int(deal.position_id)
            volumes[ident] = volumes.get(ident, 0.0) + volume * (1 if kind == 0 else -1)
        ledger.append({key: getattr(deal, key) for key in (
            "ticket", "type", "time_msc", "position_id", "magic", "entry", "volume",
            "profit", "commission", "swap", "fee")})
    if any(abs(volume) > 1e-8 for volume in volumes.values()):
        raise ValueError("evidence_position_history_not_flat")
    fields = ("trade_contract_size", "trade_tick_size", "point", "volume_min", "volume_max",
              "volume_step", "swap_mode", "swap_long", "swap_short", "swap_rollover3days", "currency_profit")
    spec = {key: getattr(info, key) for key in fields}
    numeric = [spec[key] for key in fields if key != "currency_profit"]
    if (spec["currency_profit"] != "USD" or any(isinstance(value, bool)
            or not isinstance(value, (int, float)) or not math.isfinite(value) for value in numeric)):
        raise ValueError("evidence_spec_invalid")
    return dict(captured_utc=started.isoformat(), read_observed_utc=observed.isoformat(),
        source="existing_sender_reads", account_fingerprint=context.fingerprint,
        account_type="Standard Demo", account_type_basis="existing_policy_label_not_SDK_entitlement",
        demo_verified=True, hedging_verified=True, symbol=context.symbol,
        account={key: getattr(account, key) for key in ("currency", "balance", "equity")},
        terminal={"connected": True}, positions=0, orders=0, spec=spec,
        history_start_utc=datetime(1970, 1, 1, tzinfo=timezone.utc).isoformat(),
        history_end_utc=started.isoformat(), history_complete=True,
        history_deals_total=len(deals), history_deals=ledger, order_send_called=False,
        execution_authorized=False, swap_entitlement="UNKNOWN",
        release_hash=context.release_hash, config_hash=context.journal.audit_context["config_hash"],
        policy_sha256=hashlib.sha256(json.dumps(context.policy, sort_keys=True).encode()).hexdigest(),
        correlation_id=context.journal.audit_context.get("correlation_id"))


def capture_current_reads(context, snapshot, *, now):
    """Serialize this sender's current flat reads without requesting SDK data."""
    if (snapshot is None or context.journal.get("active") is not None
            or context.journal.get("safety_halt") or context._cycle_send_attempted):
        raise ValueError("evidence_current_flat_reads_required")
    return _bytes(_packet(snapshot, context=context, now=_utc(now)))


def export_requested(context, directory, snapshot, *, now):
    """Return a safe receipt, or None without a request. Errors stay optional."""
    directory = Path(directory)
    request_path = directory / "request.json"
    if not request_path.exists():
        return None
    if directory.is_symlink() or request_path.is_symlink() or request_path.stat().st_size > 4096:
        raise ValueError("evidence_request_invalid")
    request = json.loads(request_path.read_bytes())
    if (not isinstance(request, dict) or set(request) != {"request_id", "requested_utc"}
            or not isinstance(request["request_id"], str)
            or re.fullmatch("[0-9a-f]{32}", request["request_id"]) is None
            or _utc(request["requested_utc"]) > _utc(now)):
        raise ValueError("evidence_request_invalid")
    ident = request["request_id"]
    target = directory / ("broker-" + ident + ".json")
    receipt = dict(request_id=ident, status="DEFERRED", execution_authorized=False)
    if target.exists() or target.is_symlink():
        # Idempotent retry/restart: never re-date a completed observation.
        if target.is_symlink():
            raise ValueError("evidence_packet_invalid")
        raw = target.read_bytes()
        packet = json.loads(raw)
        if (packet.get("request_id") != ident or packet.get("requested_utc") != request["requested_utc"]
                or packet.get("account_fingerprint") != context.fingerprint
                or packet.get("execution_authorized") is not False):
            raise ValueError("evidence_packet_invalid")
        if (packet.get("release_hash") != context.release_hash
                or packet.get("config_hash") != context.journal.audit_context["config_hash"]):
            raise ValueError("evidence_packet_context_mismatch")
        receipt.update(status="CAPTURED", captured_utc=packet["captured_utc"],
                       fresh_for_generation=timedelta(0) <= _utc(now) - _utc(packet["captured_utc"]) <= timedelta(minutes=5),
                       packet_sha256=hashlib.sha256(raw).hexdigest())
        return receipt
    if context.journal.get("active") is not None or context.journal.get("safety_halt") or context._cycle_send_attempted:
        receipt["reason"] = "owned_or_uncertain_exposure"
    elif snapshot is None:
        receipt["reason"] = "broker_reads_incomplete"
    elif snapshot[5] < _utc(request["requested_utc"]):
        receipt["reason"] = "await_next_complete_read_cycle"
    else:
        try:
            packet = _packet(snapshot, context=context, now=_utc(now))
        except (ValueError, AttributeError, TypeError, KeyError, OverflowError) as exc:
            codes = {"evidence_read_window_stale", "evidence_not_flat", "evidence_account_type_unproven",
                "evidence_demo_identity_unproven", "evidence_cash_not_reconciled", "evidence_history_invalid",
                "evidence_position_history_not_flat", "evidence_spec_invalid"}
            receipt["reason"] = str(exc) if type(exc) is ValueError and str(exc) in codes else "evidence_fields_incomplete"
        else:
            packet.update(request)
            raw = _bytes(packet)
            _write_private(target, raw)
            receipt.update(status="CAPTURED", captured_utc=packet["captured_utc"],
                           fresh_for_generation=True,
                           packet_sha256=hashlib.sha256(raw).hexdigest())
    receipt_raw = _bytes(receipt)
    receipt_path = directory / "receipt.json"
    if not receipt_path.exists() or receipt_path.read_bytes() != receipt_raw:
        _write_private(receipt_path, receipt_raw)
    return receipt
