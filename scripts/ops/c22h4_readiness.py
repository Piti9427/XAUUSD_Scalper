"""Read-only market-open prerequisites. A report never authorizes execution."""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from scripts.demo_runtime.costs import validate_policy, validate_observed_costs


def utc(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError("aware UTC required")
    return stamp


def build_report(
    conn, *, now, since, broker, parity, policy, feed_review=None,
    expected_snapshot="RESEARCH-C22-H4EMA200-20261004",
    contract_id="1af968e9ac6a26ea", magic=22261004,
):
    now, since = utc(now), utc(since)
    if since >= now:
        raise ValueError("shadow window must start before now")
    values = {k: json.loads(v) for k, v in conn.execute("SELECT key,value FROM kv")}
    fingerprint = values.get("identity")
    blockers = []

    def require(condition, reason):
        if not condition:
            blockers.append(reason)

    latest = values.get("last_result") or {}
    try:
        age = (now - utc(latest["captured_utc"])).total_seconds()
    except (ValueError, TypeError, KeyError):
        age = None
    require(age is not None and 0 <= age <= 15, "shadow_heartbeat_stale_or_missing")
    require(latest.get("execute") is False, "shadow_mode_not_verified")
    require(latest.get("status") in ("WAIT", "SHADOW_ADMIT"), "current_shadow_admission_blocked")
    require(
        not values.get("active") and not values.get("safety_halt"), "journal_active_or_safety_halt"
    )
    require(
        bool(fingerprint) and values.get("strategy_snapshot") == expected_snapshot,
        "journal_identity_or_strategy_missing",
    )
    pending = conn.execute("SELECT count(*) FROM events WHERE sent=0").fetchone()[0]
    require(pending == 0, "pending_outbox")

    cycles, cohorts, bars, reasons = [], set(), set(), Counter()
    invalid = 0
    invalid_bars = 0
    unknown = 0
    executed = 0
    for (raw,) in conn.execute("SELECT payload FROM audit_events ORDER BY id"):
        try:
            event = json.loads(raw)
            stamp = utc(event["utc"])
            if not since <= stamp <= now:
                continue
            if event.get("kind") not in ("CYCLE", "SIGNAL"):
                continue
            cohort = (
                event.get("account_fingerprint"),
                event.get("release_hash"),
                event.get("config_hash"),
            )
            if cohort[0] != fingerprint or not all(cohort):
                invalid += 1
                continue
            cohorts.add(cohort)
            if event["kind"] == "CYCLE":
                result = event["result"]
                cycles.append(stamp)
                executed += result.get("execute") is not False
                unknown += (
                    result.get("position_protection") != "flat"
                    or result.get("observed_positions") != 0
                )
                if result.get("status") == "BLOCKED":
                    reasons[result.get("reason") or "unknown"] += 1
            else:
                bar = utc(event["bar"])
                if bar < since:
                    continue  # Historical bootstrap bars are not prospective evidence.
                macro = event.get("observed", {}).get("macro_ema")
                if (
                    bar.timestamp() % 900
                    or not 0 <= (stamp - bar).total_seconds() <= 900
                    or isinstance(macro, bool)
                    or not math.isfinite(float(macro))
                ):
                    invalid_bars += 1
                    continue
                bars.add(bar)
        except (KeyError, TypeError, ValueError, OverflowError):
            invalid += 1
    cycles.sort()
    elapsed = (cycles[-1] - cycles[0]).total_seconds() if cycles else 0
    gaps = [(b - a).total_seconds() for a, b in zip(cycles, cycles[1:])]
    max_gap = max(gaps, default=0)
    require(
        bool(cycles) and elapsed >= 48 * 3600 and max_gap <= 120,
        "shadow_48h_continuous_observation_missing",
    )
    require(len(bars) >= 96, "shadow_96_new_complete_m15_missing")
    require(bool(cycles) and cycles[0].date() < cycles[-1].date(), "shadow_utc_midnight_missing")
    require(len(cohorts) == 1, "shadow_release_or_config_changed")
    require(not invalid and not invalid_bars, "shadow_invalid_bar_evidence")
    require(not executed, "execution_seen_in_shadow_window")
    require(not reasons and not unknown, "shadow_unexpected_blockers_or_protection_unknown")

    try:
        captured = utc(broker["captured_utc"])
        broker_age = (now - captured).total_seconds()
        quote_age = captured.timestamp() - float(broker["tick"]["time_msc"]) / 1000
    except (KeyError, TypeError, ValueError, OverflowError):
        broker_age = quote_age = None
    require(broker_age is not None and 0 <= broker_age <= 300, "fresh_broker_evidence_missing")
    require(quote_age is not None and 0 <= quote_age <= 5, "fresh_broker_quote_missing")
    require(
        broker.get("demo_verified") is True
        and broker.get("hedging_verified") is True
        and broker.get("account_fingerprint") == fingerprint
        and broker.get("positions") == 0
        and broker.get("orders") == 0,
        "fresh_demo_identity_or_flat_exposure_missing",
    )
    terminal, account = broker.get("terminal", {}), broker.get("account", {})
    require(
        terminal.get("connected") is True
        and terminal.get("trade_allowed") is True
        and terminal.get("tradeapi_disabled") is False
        and account.get("trade_allowed") is True
        and account.get("trade_expert") is True,
        "execution_permissions_not_ready",
    )
    require(parity.get("history_gate") is True, "broker_history_not_passed")
    strict_parity = (
        parity.get("parity_gate") is True and parity.get("contract_id") == contract_id
    )
    # Owner may accept diagnosed feed differences for a prospective Demo cohort.
    # Preserve the original failed parity gate; never infer economic equivalence.
    accepted_feed = False
    if feed_review:
        try:
            accepted_feed = (
                feed_review["scope"] == "PROSPECTIVE_DEMO_ONLY"
                and feed_review["owner_decision"] == "เตรียม Demo trial บน feed นี้"
                and feed_review["contract_id"] == contract_id
                and feed_review["account_fingerprint"] == fingerprint
                and feed_review["parity_document_sha256"]
                == hashlib.sha256(
                    json.dumps(parity, sort_keys=True, allow_nan=False).encode()
                ).hexdigest()
                and len(cohorts) == 1
                and (fingerprint, feed_review["release_hash"], feed_review["config_hash"])
                in cohorts
                and utc(feed_review["accepted_utc"]) <= now
                and feed_review["same_input_controls_passed"] is True
                and feed_review["history_basis"] == "actual_broker_100000_M1_complete_M15"
                and bool(feed_review["diagnosis_report"])
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            accepted_feed = False
    require(strict_parity or accepted_feed, "broker_parity_not_passed")

    cost, cost_reason = validate_policy(
        policy,
        fingerprint=fingerprint,
        now=now,
        strategy="c22h4",
        spec=SimpleNamespace(**broker.get("spec", {})),
    )
    require(bool(cost) and policy.get("version") == 2, "cost_v2_evidence_missing_or_invalid")
    if cost and cost.get("version") == 2:
        try:
            ledger = broker["history_deals"]
            if not isinstance(ledger, list):
                raise ValueError("broker deal evidence required")
            validate_observed_costs(
                cost, [SimpleNamespace(**deal) for deal in ledger], magic=magic, now=now
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            blockers.append("cost_deal_or_calendar_unverified")
            cost_reason = str(exc)
    try:
        cost_age = (now - utc(policy["reviewed_utc"])).total_seconds()
        require(0 <= cost_age <= 24 * 3600, "cost_cutover_review_older_than_24h")
    except (KeyError, TypeError, ValueError):
        cost_age = None
        blockers.append("cost_review_timestamp_missing")
    attended_trial = bool(
        accepted_feed
        and feed_review.get("operating_mode") == "ATTENDED_DEMO_TRIAL"
        and feed_review.get("owner_attended_decision") == "Demo trial แบบมีคนเฝ้า + backup บน Mac"
    )
    time_waiver = False
    if attended_trial:
        try:
            waiver = feed_review["shadow_time_waiver"]
            trial_day = date.fromisoformat(waiver["trial_date_local"])
            time_waiver = (
                waiver["owner_decision"] == "ยกเว้นเวลา shadow สำหรับ Demo trial มีคนเฝ้า"
                and waiver["timezone"] == "Asia/Bangkok"
                and trial_day.weekday() == 0
                and now.astimezone(ZoneInfo("Asia/Bangkok")).date() == trial_day
            )
        except (KeyError, TypeError, ValueError):
            pass
    if time_waiver:
        # This is an explicit, dated owner exception, not a passed 48h soak.
        time_gates = {
            "shadow_48h_continuous_observation_missing",
            "shadow_96_new_complete_m15_missing",
            "shadow_utc_midnight_missing",
        }
        blockers = [reason for reason in blockers if reason not in time_gates]
        require(bool(cycles) and max_gap <= 120, "recent_shadow_observation_missing_or_interrupted")
        require(bool(bars), "fresh_closed_m15_not_observed")
        try:
            macro = latest.get("macro_ema")
            macro_ok = not isinstance(macro, bool) and math.isfinite(float(macro))
        except (ValueError, TypeError, OverflowError):
            macro_ok = False
        require(macro_ok, "current_macro_warmup_not_verified")
    return dict(
        captured_utc=now.isoformat(),
        since_utc=since.isoformat(),
        status="BLOCKED" if blockers else "AWAITING_OPERATOR_REVIEW",
        execution_authorized=False,
        operating_mode="ATTENDED_DEMO_TRIAL" if attended_trial else "STANDARD_ROLLOUT",
        unattended_authorized=False,
        blockers=blockers,
        shadow=dict(
            cycles=len(cycles),
            observed_hours=elapsed / 3600,
            max_cycle_gap_seconds=max_gap,
            new_complete_m15_bars=len(bars),
            cohorts=len(cohorts),
            blocked_cycles=dict(reasons),
            unknown_protection_cycles=unknown,
            invalid_events=invalid,
            invalid_bars=invalid_bars,
            time_requirement_waived_for_attended_trial=time_waiver,
        ),
        journal=dict(pending_outbox=pending, heartbeat_age_seconds=age),
        broker=dict(evidence_age_seconds=broker_age, quote_age_at_probe_seconds=quote_age),
        feed=dict(
            original_parity_passed=strict_parity,
            prospective_demo_feed_accepted=accepted_feed,
            economic_equivalence_established=False,
        ),
        costs=dict(
            status=cost_reason, review_age_hours=None if cost_age is None else cost_age / 3600
        ),
        required_reviews=[
            "frozen_release_and_exact_cache_replay",
            "broker_parity_explanations_and_history_depth",
            "scheduled_session_closures_vs_unexpected_blocks",
            "observed_deal_cost_drift_and_swap_calendar",
            "attended_operator_console_and_verified_off_VM_snapshot"
            if attended_trial
            else "external_monitoring_and_private_cloud_restore",
            "one_account_one_sender_and_cutover_UTC_day",
            "execution_time_owner_approval",
        ],
        limitations=[
            "No MT5 calls; evidence files must be refreshed by an exclusive read-only probe",
            "BLOCKED quote_stale during closed sessions remains visible for explicit session review",
            "A report, exit code or market opening never enables sending",
            "No live trading or profitability qualification",
        ],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("journal", "broker", "parity", "cost-policy", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--feed-review", type=Path)
    parser.add_argument("--since", type=utc, required=True)
    args = parser.parse_args(argv)
    inputs = {p.resolve() for p in (args.journal, args.broker, args.parity, args.cost_policy)}
    if args.feed_review:
        inputs.add(args.feed_review.resolve())
    pending = args.out.with_suffix(args.out.suffix + ".tmp")
    if args.out.resolve() in inputs or pending.resolve() in inputs:
        parser.error("report output must not overwrite input or financial evidence")
    # mode=ro must fail if absent; never create/reset a financial journal.
    conn = sqlite3.connect(args.journal.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        result = build_report(
            conn,
            now=datetime.now(timezone.utc),
            since=args.since,
            broker=json.loads(args.broker.read_text()),
            parity=json.loads(args.parity.read_text()),
            policy=json.loads(args.cost_policy.read_text()),
            feed_review=json.loads(args.feed_review.read_text()) if args.feed_review else None,
        )
    finally:
        conn.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pending.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    pending.replace(args.out)
    print(
        json.dumps(
            dict(status=result["status"], execution_authorized=False, blockers=result["blockers"])
        )
    )
    return 2 if result["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
