"""Explicit cost review only; never renew, overwrite, activate or contact MT5."""

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import SimpleNamespace

from scripts.demo_runtime.costs import validate_evidence, validate_policy, validate_observed_costs


CONFIRMATIONS = (
    "standard_demo_tariff_applies",
    "account_swap_applicability_checked",
    "dated_calendar_and_broker_notices_checked",
    "historical_deal_charges_and_swap_reviewed",
    "slippage_is_assumption_not_guarantee",
)


def utc(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("aware UTC required")
    return value


def review_policy(draft_bytes, broker_bytes, review, *, now):
    now = utc(now)
    draft, broker = json.loads(draft_bytes), json.loads(broker_bytes)
    reviewed, checked = utc(review["reviewed_utc"]), utc(review["sources_checked_utc"])
    captured = utc(broker["captured_utc"])
    if not (
        timedelta(0) <= now - reviewed <= timedelta(minutes=5)
        and timedelta(0) <= reviewed - captured <= timedelta(minutes=5)
        and timedelta(0) <= reviewed - checked <= timedelta(hours=24)
    ):
        raise ValueError("fresh broker capture and explicit source review required")
    if (
        review.get("draft_sha256") != hashlib.sha256(draft_bytes).hexdigest()
        or review.get("broker_sha256") != hashlib.sha256(broker_bytes).hexdigest()
        or not str(review.get("reviewed_by", "")).strip()
        or not str(review.get("review_note", "")).strip()
        or any(review.get("confirmations", {}).get(key) is not True for key in CONFIRMATIONS)
    ):
        raise ValueError("review must bind exact evidence and every explicit confirmation")
    if (
        draft.get("status") != "DRAFT_NOT_ATTESTED"
        or draft.get("reviewed_utc") is not None
        or draft.get("version") != 2
        or not validate_evidence(draft)
    ):
        raise ValueError("intact unapproved v2 draft required; timestamp renewal prohibited")
    if (
        broker.get("demo_verified") is not True
        or broker.get("hedging_verified") is not True
        or broker.get("order_send_called") is not False
        or broker.get("account_fingerprint") != draft.get("account_fingerprint")
        or broker.get("symbol") != "XAUUSDm"
        or broker.get("positions") != 0
        or broker.get("orders") != 0
        or broker.get("terminal", {}).get("connected") is not True
        or broker.get("account", {}).get("currency") != "USD"
        or broker.get("spec", {}).get("currency_profit") != "USD"
    ):
        raise ValueError("fresh flat dedicated Demo evidence required")
    if not validate_evidence(draft, spec=SimpleNamespace(**broker["spec"])):
        raise ValueError("broker spec changed; review a new draft rather than refresh timestamp")
    if "point" not in draft["evidence"]["spec"]["document"]["fields"]:
        raise ValueError("point conversion must be bound in the swap spec evidence")
    ledger = broker["history_deals"]
    if not isinstance(ledger, list) or not ledger:
        raise ValueError("historical deal evidence required")
    # This prepared Standard tariff is zero. A charged deal contradicts that basis;
    # retain it for a new account/tariff review, never silently change the allowance.
    if draft["commission_per_lot"] != 0 or any(
        float(deal[k]) != 0
        for deal in ledger
        if deal["type"] in (0, 1)
        for k in ("commission", "fee")
    ):
        raise ValueError("historical charges contradict prepared zero-commission tariff")
    policy = deepcopy(draft)
    policy.update(
        status="REVIEWED_DEMO_ASSUMPTIONS",
        reviewed_utc=reviewed.isoformat(),
        account_evidence_sha256=hashlib.sha256(broker_bytes).hexdigest(),
        source="Explicit operator review of account tariff, current spec, calendar and deals",
        operator_review=deepcopy(review),
        pending_checks=[],
    )
    docs = policy["evidence"]
    docs["spec"]["document"].update(
        captured_utc=captured.isoformat(),
        broker_evidence_sha256=policy["account_evidence_sha256"],
    )
    for key in ("tariff", "swap_calendar"):
        docs[key]["document"]["checked_utc"] = checked.isoformat()
    calendar = docs["swap_calendar"]["document"]
    for offset in range(8):
        day = (reviewed + timedelta(days=offset)).date().isoformat()
        if day not in calendar["days"]:
            raise ValueError("dated swap calendar must cover the full next 168 hours")
    # Remove draft-only uncertainty only after the reviewer bound that exact draft.
    calendar["review_note"] = review["review_note"]
    for item in docs.values():
        item["sha256"] = hashlib.sha256(
            json.dumps(item["document"], sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
    valid, reason = validate_policy(
        policy,
        fingerprint=broker["account_fingerprint"],
        now=now,
        strategy="c22h4",
        spec=SimpleNamespace(**broker["spec"]),
    )
    if not valid:
        raise ValueError("reviewed cost policy invalid: " + reason)
    validate_observed_costs(valid, [SimpleNamespace(**d) for d in ledger], magic=22261004, now=now)
    return policy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("draft", "broker", "review", "out"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = {p.resolve() for p in (args.draft, args.broker, args.review)}
    if args.out.resolve() in inputs or args.out.exists():
        parser.error("output must be new; financial evidence and policies are never overwritten")
    policy = review_policy(
        args.draft.read_bytes(),
        args.broker.read_bytes(),
        json.loads(args.review.read_text()),
        now=datetime.now(timezone.utc),
    )
    # Publish complete bytes atomically, without replacing an existing policy.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=args.out.parent, delete=False) as handle:
        temp = Path(handle.name)
        try:
            handle.write((json.dumps(policy, indent=2, allow_nan=False) + "\n").encode())
            handle.flush()
            os.fsync(handle.fileno())
            os.link(temp, args.out)
        finally:
            temp.unlink(missing_ok=True)
    print(json.dumps(dict(status=policy["status"], execution_authorized=False)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
