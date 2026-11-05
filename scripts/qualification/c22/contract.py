"""Bind frozen research artifacts and compare declared offline event evidence.

No adapter is implemented here. A manifest never authorizes execution. Event
comparison checks supplied records and local source bindings; it cannot prove
that a claimed implementation generated a record or qualify broker fills.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from .artifacts import make_report, parse_utc, read_json, source_ref


ROOT = Path(__file__).resolve().parents[3]
_ID = re.compile(r"[0-9a-f]{16}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SEED = "config/research-c22-terminal-profit-9e511d195c52ef3d.json"
_INPUT = "runs/c22-real-data-audit-2026-10-24/input/manifest.json"
_METADATA_LIMIT_BYTES = 256 * 1024 * 1024
_DOMAINS = {
    "buy_target_rr": [1.35, 1.5, 2.0, 3.0],
    "target_rr": [1.25, 1.35, 1.4, 1.45, 1.5, 2.0],
    "cooldown_bars": [0, 1, 2, 4],
    "stop_atr": [1.5, 2.0, 2.5],
    "buy_stop_atr": [1.5, 2.0, 2.5],
    "protect_after_r": [0.5, 1.0, 1.5],
    "buy_protect_mode": ["off", "break_even"],
}
_FIXED = dict(
    failed_closes=0,
    reset_after_exit=False,
    stagnant_bars=0,
    entry_mode="immediate",
    stop_mode="atr",
    protect_mode="break_even",
    entry_guard="off",
    buy_pause_drawdown=0.0,
    risk_mode="static",
    risk_cap=0.1,
    daily_loss_limit=0.1,
    target_atr=3.0,
    min_depth_atr=0.0,
    session_mode="all",
    max_daily_losses=2,
    sizing_mode="fixed",
    holding_mode="legacy",
    buy_stop_mode=None,
    buy_risk_cap=None,
    buy_sizing_mode=None,
    sell_stop_mode=None,
)
_PROTOCOL_FIELDS = {
    "schema",
    "algorithm",
    "sources",
    "input_hashes",
    "input_manifest_sha256",
    "parent_complete_sha256",
    "parent_results_sha256",
    "parent_audit_sha256",
    "parent_cell_bindings",
    "broker",
    "views",
    "start",
    "end",
    "original_floors",
    "benchmark_hashes",
    "domains",
    "finite_domain",
    "initial",
    "lanes",
    "risk_fields",
    "catalog_sha256",
    "batch_size",
    "cost_status",
    "holdout",
    "claim",
}
_CONTEXT_FIELDS = {
    "bars_sha256",
    "quotes_sha256",
    "spec_sha256",
    "costs_sha256",
    "account_state_sha256",
    "day_state_sha256",
}
_EVENT_FIELDS = {
    "event_id",
    "time_utc",
    "kind",
    "side",
    "entry",
    "stop",
    "target",
    "admitted",
    "reason",
    "risk_usd",
    "cooldown_until_utc",
    "protection",
    "net_usd",
}


def _keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        actual = set(value) if isinstance(value, dict) else set()
        raise ValueError(
            f"{label} fields: missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ValueError(f"Invalid SHA256: {label}")
    return value


def _candidate(value: Any) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Candidate must be a complete native 16-hex Rules ID")
    return value


def _local(relative: str) -> Path:
    if (
        not isinstance(relative, str)
        or Path(relative).is_absolute()
        or ".." in Path(relative).parts
    ):
        raise ValueError("Unsafe campaign source/input path")
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError("Campaign source/input path escaped repository")
    return path


def _bound(path: Path) -> tuple[dict, dict]:
    """Bind finite JSON metadata up to256MiB; never load or hash tick tapes."""
    for _ in range(3):
        before = source_ref(path, max_bytes=_METADATA_LIMIT_BYTES)
        if before["hash_status"] != "VERIFIED":
            raise ValueError(f"Artifact exceeds bounded hash limit: {path}")
        value = read_json(path)
        json.dumps(value, allow_nan=False)
        after = source_ref(path, max_bytes=_METADATA_LIMIT_BYTES)
        if before == after:
            if not isinstance(value, dict):
                raise ValueError(f"Expected JSON object: {path}")
            return value, after
    raise ValueError(f"Artifact changed while reading: {path}")


def _rules(values: dict) -> str:
    _keys(values, set(_FIXED) | set(_DOMAINS), "Native Rules")
    for key, expected in _FIXED.items():
        value = values[key]
        if type(value) is not type(expected) or value != expected:
            raise ValueError(f"Unsupported frozen Rules invariant: {key}")
    for key, allowed in _DOMAINS.items():
        value = values[key]
        if key == "buy_protect_mode":
            valid = isinstance(value, str) and value in allowed
        elif key == "cooldown_bars":
            valid = type(value) is int and value in allowed
        else:
            valid = type(value) in (int, float) and math.isfinite(value) and value in allowed
        if not valid:
            raise ValueError(f"Unsupported frozen Rules axis: {key}")
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:16]


def _compatibility(rules: dict, seed: dict) -> list[dict]:
    # Verified current Demo semantics. No claim that candidate plumbing exists.
    demo = dict(
        _FIXED,
        max_daily_losses=1,
        buy_target_rr=2.0,
        target_rr=0.0,
        cooldown_bars=0,
        stop_atr=2.5,
        buy_stop_atr=1.5,
        protect_after_r=1.0,
        buy_protect_mode="off",
    )
    names = {
        "max_daily_losses": "daily_loss_count",
        "cooldown_bars": "post_loss_cooldown",
        "buy_protect_mode": "buy_protection",
        "protect_after_r": "protection_activation",
    }
    rows = [
        dict(
            capability="candidate_contract",
            field=None,
            status="GAP",
            current="hardcoded Demo CONTRACT/CONTRACT_ID",
            candidate="native Rules manifest",
            reason="Candidate runtime adapter is not implemented or qualified",
        )
    ]
    rows += [
        dict(
            capability=names.get(key, key),
            field=key,
            status="MATCH" if value == demo[key] else "GAP",
            current=demo[key],
            candidate=value,
            reason="Value agreement only; runtime adapter parity remains NOT_TESTED",
        )
        for key, value in rules.items()
    ]
    for key, current in dict(
        rsi_period=14, rsi_threshold=25, sell_lookback=96, sell_ema=50, macro_span=200
    ).items():
        candidate = seed.get(key)
        rows.append(
            dict(
                capability="detector_" + key,
                field=key,
                status="MATCH" if candidate == current else "GAP",
                current=current,
                candidate=candidate,
                reason="Frozen Demo detector versus research entry seed",
            )
        )
    return rows


def _final_binding(
    campaign: Path, protocol: dict, protocol_ref: dict, manifest_ref: dict, candidate_id: str
) -> tuple[bool, list[dict], list[str]]:
    paths = {
        name: campaign / name
        for name in ("COMPLETE.json", "results.json", "independent-verification.json")
    }
    if not all(path.exists() for path in paths.values()):
        return False, [], ["FINAL_AUDIT_NOT_BOUND"]
    values, refs = {}, {}
    for name, path in paths.items():
        values[name], refs[name] = _bound(path)
    complete, result, audit = (values[name] for name in paths)
    if complete.get("status") != "EXHAUSTIVE_COMPLETE" or audit.get("status") != "PASS":
        return False, list(refs.values()), ["FINAL_AUDIT_NOT_BOUND"]
    checks = [
        complete.get("visited_cases") == 5184,
        complete.get("processed_batches") == 162,
        audit.get("finite_domain") == 5184,
        audit.get("visited_cases") == 5184,
        audit.get("processed_batches") == 162,
        audit.get("raw_cells") == 15552,
        audit.get("parent_completion_sha256") == refs["COMPLETE.json"]["sha256"],
        audit.get("input_manifest_sha256") == manifest_ref["sha256"],
        complete.get("selected") == audit.get("selected") == result.get("selected"),
    ]
    raw_qualified, cent_cells = audit.get("raw_qualified"), audit.get("cent_cells")
    checks += [
        type(raw_qualified) is int and 0 <= raw_qualified <= 5184,
        type(cent_cells) is int and type(raw_qualified) is int and cent_cells == raw_qualified * 3,
        type(cent_cells) is int and audit.get("cells") == 15552 + cent_cells,
    ]
    for name, expected in (
        ("protocol.json", protocol_ref["sha256"]),
        ("catalog.json", protocol["catalog_sha256"]),
        ("results.json", refs["results.json"]["sha256"]),
    ):
        checks.append(complete.get("artifacts", {}).get(name) == expected)
    selected = complete.get("selected", {})
    checks.append(isinstance(selected, dict) and set(selected) == {"profit", "repair"})
    selected_ids = set(selected.values()) if isinstance(selected, dict) else set()
    expected_tick = {
        f"{name}-{view}-{guard}"
        for name in selected_ids
        for view in ("base", "stress", "fee")
        for guard in ("raw", "cent")
    }
    checks += [
        set(audit.get("independent_full_tick_dd", {})) == expected_tick,
        complete.get("fresh_repeats") == len(expected_tick),
    ]
    for relative, key in (
        ("scripts/research/c22_exhaustive_verify.py", "source_sha256"),
        ("scripts/research/c22_learning_verify.py", "helper_sha256"),
    ):
        ref = source_ref(_local(relative))
        refs[relative] = ref
        checks.append(ref["hash_status"] == "VERIFIED" and audit.get(key) == ref["sha256"])
    if not all(checks):
        raise ValueError("Final audit/source/coverage binding mismatch")
    return (
        candidate_id in selected_ids,
        list(refs.values()),
        ([] if candidate_id in selected_ids else ["CANDIDATE_NOT_FINAL_SELECTION"]),
    )


def build_manifest(campaign_dir: Path, candidate_id: str | None = None) -> dict:
    """Read-only native descriptor. Large input hashes are declared, not rehashed."""
    campaign = Path(campaign_dir).resolve()
    if not campaign.is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("Campaign must remain under repository runs/")
    protocol, protocol_ref = _bound(campaign / "protocol.json")
    _keys(protocol, _PROTOCOL_FIELDS, "Frozen protocol")
    if (
        protocol["algorithm"] != "exhaustive_native_grid_v1"
        or protocol["finite_domain"] != 5184
        or protocol["domains"] != _DOMAINS
        or protocol["cost_status"] != "COST_INCONCLUSIVE"
        or protocol["holdout"] is not False
    ):
        raise ValueError("Unsupported frozen research protocol")
    if parse_utc(protocol["start"]) >= parse_utc(protocol["end"]):
        raise ValueError("Invalid campaign time interval")
    tool_bindings = [
        source_ref(Path(__file__)),
        source_ref(Path(__file__).with_name("artifacts.py")),
    ]
    sources = [protocol_ref, *tool_bindings]
    source_bindings = []
    for relative, declared in protocol["sources"].items():
        _sha(declared, relative)
        ref = source_ref(_local(relative))
        if ref["hash_status"] != "VERIFIED" or ref["sha256"] != declared:
            raise ValueError(f"Source hash drift: {relative}")
        source_bindings.append(ref)
    sources += source_bindings
    if _SEED not in protocol["sources"]:
        raise ValueError("Missing frozen detector seed binding")
    seed, seed_ref = _bound(_local(_SEED))
    if seed_ref["sha256"] != protocol["sources"][_SEED]:
        raise ValueError("Detector seed source hash drift")
    input_manifest, input_ref = _bound(_local(_INPUT))
    if input_ref["sha256"] != _sha(protocol["input_manifest_sha256"], "input manifest"):
        raise ValueError("Input manifest hash drift")
    for relative, declared in protocol["input_hashes"].items():
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("Unsafe declared input path")
        _sha(declared, relative)
    catalog, catalog_ref = _bound(campaign / "catalog.json")
    if catalog_ref["sha256"] != _sha(protocol["catalog_sha256"], "catalog"):
        raise ValueError("Catalog hash drift")
    _keys(catalog, {"schema", "axes", "finite_domain", "cases"}, "Catalog")
    if (
        catalog["schema"] != 1
        or catalog["finite_domain"] != 5184
        or catalog["axes"] != list(_DOMAINS)
        or len(catalog["cases"]) != 5184
    ):
        raise ValueError("Incomplete frozen catalog")
    cases = {}
    for case in catalog["cases"]:
        _keys(case, {"name", "rules"}, "Catalog case")
        name = _rules(case["rules"])
        if case["name"] != name or name in cases:
            raise ValueError("Catalog Rules identity mismatch or duplicate")
        cases[name] = case["rules"]
    checkpoint, checkpoint_ref = _bound(campaign / "checkpoint.json")
    if checkpoint["protocol_sha256"] != protocol_ref["sha256"]:
        raise ValueError("Checkpoint protocol hash drift")
    selected = checkpoint.get("selected", {})
    chosen = _candidate(candidate_id if candidate_id is not None else selected.get("profit"))
    if chosen not in cases:
        raise ValueError("Candidate absent from frozen catalog")
    bound, final_refs, reasons = _final_binding(campaign, protocol, protocol_ref, input_ref, chosen)
    sources += [input_ref, catalog_ref, checkpoint_ref, *final_refs]
    compatibility = _compatibility(cases[chosen], seed)
    manifest = dict(
        schema_version=1,
        candidate_id=chosen,
        rules=cases[chosen],
        detector_seed_descriptor=seed,
        detector_seed_note="Entry detector seed; all management Rules above override the seed Rules",
        data_cutoff_utc=parse_utc(protocol["end"]).isoformat(),
        observed_first_quote_utc=input_manifest.get("first_quote_utc"),
        observed_last_quote_utc=input_manifest.get("last_quote_utc"),
        campaign_protocol=protocol_ref,
        catalog=catalog_ref,
        checkpoint=checkpoint_ref,
        final_artifacts=final_refs,
        source_bindings=source_bindings,
        tool_bindings=tool_bindings,
        inputs=dict(
            manifest=input_ref,
            declared_hashes=protocol["input_hashes"],
            hash_status="DECLARED_NOT_REHASHED",
        ),
        modeled_costs=dict(
            broker=protocol["broker"],
            views=protocol["views"],
            status="COST_INCONCLUSIVE",
            swap_required=True,
        ),
        accounting_conventions=dict(
            capital_usd=200,
            volume=0.01,
            raw_and_cent_loss_guards=True,
            cent_rounding="ROUND_HALF_UP",
            time_basis="aware UTC",
        ),
        adapter_parity="NOT_TESTED",
        runtime_qualified=False,
        research_audit_bound=bound,
        forward_evidence="NOT_TESTED",
        real_money="PROHIBITED",
    )
    return make_report(
        "candidate_manifest",
        "RESEARCH_BOUND" if bound else "PROVISIONAL",
        sources=sources,
        coverage=dict(
            catalog_profiles=len(cases),
            checkpoint_profiles=checkpoint.get("visited_cases"),
            finite_domain=5184,
            large_input_hashes_reverified=False,
        ),
        reasons=[*reasons, "RUNTIME_ADAPTER_NOT_QUALIFIED", "HISTORICAL_COSTS_INCONCLUSIVE"],
        candidate_id=chosen,
        manifest=manifest,
        compatibility=compatibility,
    )


def _event_document(path: Path) -> tuple[dict, dict, dict]:
    value, ref = _bound(path)
    _keys(
        value,
        {"schema_version", "candidate_id", "implementation", "context", "events"},
        "Event document",
    )
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("Unsupported event schema")
    _candidate(value["candidate_id"])
    implementation = value["implementation"]
    _keys(implementation, {"role", "source_path", "source_sha256"}, "Implementation")
    if implementation["role"] not in ("research", "runtime_adapter"):
        raise ValueError("Unknown implementation role")
    _sha(implementation["source_sha256"], "implementation")
    if not isinstance(implementation["source_path"], str):
        raise ValueError("Implementation source path must be a string")
    source_path = Path(implementation["source_path"])
    if not source_path.is_absolute():
        source_path = path.parent / source_path
    implementation_ref = source_ref(source_path)
    if (
        implementation_ref["hash_status"] != "VERIFIED"
        or implementation_ref["sha256"] != implementation["source_sha256"]
    ):
        raise ValueError("Implementation source hash drift")
    _keys(value["context"], _CONTEXT_FIELDS, "Event context")
    for key, digest in value["context"].items():
        _sha(digest, key)
    if not isinstance(value["events"], list):
        raise ValueError("Events must be an ordered list")
    seen, previous = set(), None
    for event in value["events"]:
        _keys(event, _EVENT_FIELDS, "Event")
        ident = event["event_id"]
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError("Missing or duplicate event ID")
        seen.add(ident)
        timestamp = parse_utc(event["time_utc"])
        if previous is not None and timestamp < previous:
            raise ValueError("Events are not chronologically ordered")
        previous = timestamp
        if event["cooldown_until_utc"] is not None:
            parse_utc(event["cooldown_until_utc"])
        if event["side"] not in ("BUY", "SELL", "NONE") or type(event["admitted"]) is not bool:
            raise ValueError("Invalid event side/admission")
        if event["kind"] not in (
            "signal",
            "admission",
            "protection",
            "close",
            "restart",
            "reconciliation",
        ):
            raise ValueError("Unknown event kind")
        if not isinstance(event["reason"], str) or not event["reason"]:
            raise ValueError("Missing event reason")
        if event["protection"] not in ("off", "inactive", "active", "pending", "done", "unknown"):
            raise ValueError("Unknown protection state")
        for key in ("entry", "stop", "target", "risk_usd", "net_usd"):
            number = event[key]
            if number is not None and (
                type(number) not in (int, float) or not math.isfinite(number)
            ):
                raise ValueError(f"Nonfinite/invalid event number: {key}")
        if event["risk_usd"] is not None and event["risk_usd"] < 0:
            raise ValueError("Negative event risk")
        if event["admitted"]:
            if (
                event["kind"] != "admission"
                or event["side"] not in ("BUY", "SELL")
                or any(
                    event[key] is None or event[key] <= 0
                    for key in ("entry", "stop", "target", "risk_usd")
                )
            ):
                raise ValueError(
                    "Admitted event requires side, positive risk and complete geometry"
                )
            direction = 1 if event["side"] == "BUY" else -1
            if (
                direction * (event["entry"] - event["stop"]) <= 0
                or direction * (event["target"] - event["entry"]) <= 0
            ):
                raise ValueError("Invalid admitted stop/target geometry")
    return value, ref, implementation_ref


def compare_events(
    reference_path: Path, observed_path: Path, *, candidate_id: str | None = None
) -> dict:
    """Compare supplied event artifacts; never claim broker or economic parity."""
    reference_path, observed_path = Path(reference_path), Path(observed_path)
    sources, coverage, reasons, mismatches = [], {"events_compared": 0}, [], []
    details: dict[str, Any] = dict(
        broker_fill_parity=False,
        economic_qualification=False,
        provenance_limit="Source hashes bind local files; log generation by those files is not attested",
    )
    chosen = candidate_id
    try:
        if chosen is not None:
            _candidate(chosen)
        reference, reference_ref, ref_impl = _event_document(reference_path)
        observed, observed_ref, obs_impl = _event_document(observed_path)
        sources = [reference_ref, observed_ref, ref_impl, obs_impl]
        chosen = chosen or reference["candidate_id"]
        details.update(
            reference_implementation=reference["implementation"],
            observed_implementation=observed["implementation"],
            reference_context=reference["context"],
            observed_context=observed["context"],
        )
        if (
            reference_path.resolve() == observed_path.resolve()
            or ref_impl["sha256"] == obs_impl["sha256"]
        ):
            status, reasons = "NOT_TESTED", ["SELF_COMPARISON_OR_SAME_SOURCE"]
        elif (
            reference["implementation"]["role"] != "research"
            or observed["implementation"]["role"] != "runtime_adapter"
        ):
            status, reasons = "GAP", ["RUNTIME_ADAPTER_EVIDENCE_MISSING"]
        elif reference["candidate_id"] != chosen or observed["candidate_id"] != chosen:
            status, reasons = "GAP", ["CANDIDATE_ID_MISMATCH"]
        elif reference["context"] != observed["context"]:
            status, reasons = "GAP", ["INPUT_ACCOUNT_COST_CONTEXT_MISMATCH"]
        elif not reference["events"] or not observed["events"]:
            status, reasons = "NOT_TESTED", ["EVENT_COVERAGE_MISSING"]
        else:
            left, right = reference["events"], observed["events"]
            coverage.update(
                reference_events=len(left),
                observed_events=len(right),
                events_compared=min(len(left), len(right)),
            )
            if len(left) != len(right):
                mismatches.append(
                    dict(field="event_count", reference=len(left), observed=len(right))
                )
            for index, (expected, actual) in enumerate(zip(left, right)):
                for field in sorted(_EVENT_FIELDS):
                    first, second = expected[field], actual[field]
                    if (
                        field in ("time_utc", "cooldown_until_utc")
                        and first is not None
                        and second is not None
                    ):
                        same = parse_utc(first) == parse_utc(second)
                    else:
                        same = first == second
                    if not same:
                        mismatches.append(
                            dict(
                                index=index,
                                event_id=expected["event_id"],
                                field=field,
                                reference=first,
                                observed=second,
                            )
                        )
            status = "PARITY_FAIL" if mismatches else "PARITY_PASS"
            reasons = ["EVENT_MISMATCH"] if mismatches else ["SUPPLIED_EVENT_AGREEMENT_ONLY"]
    except FileNotFoundError as exc:
        status, reasons = "NOT_TESTED", ["EVENT_OR_IMPLEMENTATION_EVIDENCE_MISSING", str(exc)]
    except (ValueError, OSError, KeyError, TypeError) as exc:
        status, reasons = "INVALID", [str(exc)]
    return make_report(
        "event_parity",
        status,
        sources=sources,
        coverage=coverage,
        reasons=reasons,
        candidate_id=chosen,
        mismatches=mismatches,
        **details,
    )
