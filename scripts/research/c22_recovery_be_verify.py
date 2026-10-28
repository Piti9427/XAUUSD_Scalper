"""Independent B2 cash/gate, signed-cost and full-source-tick audit; no replay."""

from copy import deepcopy
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import argparse
import gzip
import json
from pathlib import Path

from scripts.research.c22_learning_verify import (
    DATA,
    ROOT,
    GUARDS,
    VIEWS,
    IndependentTapeAudit,
    equal,
    read,
    sha,
)
from scripts.research.c22_risk_verify import audit_net_be, full_tick_and_peaks, qualify, rank, write

BASE = "26b8bcd69e043653"
B2 = "b7431d3dc4c30161"


def audit_recovery_gate(result, broker):
    """Rebuild pre-fee eligibility from realized price/cost cash, not flags."""
    evidence = result["recovery_be"]
    decisions = evidence["entry_decisions"]
    trades = result["ledger"]
    assert len(decisions) == len(trades) and evidence["version"] == 1
    cash = peak = 200.0
    eligible = set()
    for decision, trade in zip(decisions, trades):
        assert decision["entry_ms"] == trade["entry_ms"]
        equal(cash, trade["entry_equity"], "B2 entry cash")
        equal(cash, decision["balance"], "B2 prefee balance")
        equal(peak, decision["closing_peak"], "B2 realized prior peak")
        expected = bool(cash < peak)
        assert decision["eligible"] is expected and trade["recovery_be_eligible"] is expected
        if expected:
            eligible.add(trade["entry_ms"])
        # Independent accounting audit validates these signed components against
        # source price/contract/calendar. Preserve actual posting order here.
        fee = result["costs"]["commission_per_lot"] * trade["volume"]
        equal(fee, trade["commission_usd"], "B2 commission")
        factor = broker["trade_contract_size"] * trade["volume"]
        gross = trade["direction"] * (trade["exit"] - trade["entry"]) * factor
        cash -= fee
        cash += gross + trade["swap_usd"]
        peak = max(peak, cash)
    equal(cash, result["final_balance"], "B2 final cash")
    equal(peak, evidence["closing_peak"], "B2 final closing peak")
    adjusted = [e["entry_ms"] for e in evidence["be_adjustments"]]
    assert len(adjusted) == len(set(adjusted)) and set(adjusted) <= eligible
    return dict(
        entries=len(trades), eligible_entries=len(eligible), closing_peak=peak, final_cash=cash
    )


def audit_protection(auditor, cell):
    result = cell["result"]
    proof = audit_recovery_gate(result, auditor.broker)
    subset = deepcopy(cell)
    subset["result"]["ledger"] = [t for t in result["ledger"] if t["recovery_be_eligible"]]
    subset["result"]["overlay"] = {"be_adjustments": result["recovery_be"]["be_adjustments"]}
    proof["net_be"] = audit_net_be(auditor, subset, {"net_be_first": True})
    grid = Decimal(str(auditor.broker["trade_tick_size"]))
    for trade in result["ledger"]:
        if trade["recovery_be_eligible"]:
            continue
        assert not trade.get("net_be_done") and trade["stop_updates"] in (0, 1)
        if trade["stop_updates"]:
            direction = trade["direction"]
            factor = auditor.broker["trade_contract_size"] * trade["volume"]
            raw = trade["entry"] + direction * (
                trade["commission_usd"] / factor + result["costs"]["slippage"]
            )
            price = float(
                (Decimal(str(raw)) / grid).to_integral_value(
                    rounding=ROUND_CEILING if direction == 1 else ROUND_FLOOR
                )
                * grid
            )
            equal(price, trade["stop"], "non-recovery native BE")
    return proof


def _cell(out, key, folder="cells"):
    proof = read(out / (folder + "-integrity") / (key + ".json"))
    path = (ROOT / proof["path"]).resolve()
    assert path == (out / folder / (key + ".json.gz")).resolve() and sha(path) == proof["sha256"]
    with gzip.open(path, "rt") as stream:
        value = json.load(stream)
    assert key == f"{value['profile']['name']}-{value['view']}-{value['guard']}"
    return value, proof


def verify(out):
    out = Path(out).resolve()
    assert out.is_relative_to(ROOT / "runs")
    p = read(out / "protocol.json")
    complete = read(out / "COMPLETE.json")
    assert (
        p["algorithm"] == "c22_recovery_netbe_v1"
        and p["holdout"] is False
        and p["execution_authorized"] is False
    )
    for name, digest in p["sources"].items():
        assert sha(ROOT / name) == sha(out / "source_snapshot" / name) == digest, name
    assert sha(DATA / "manifest.json") == p["input_manifest_sha256"]
    for name, digest in p["input_hashes"].items():
        assert sha(DATA / name) == digest, name
    for item in p["parent"].values():
        assert sha(ROOT / item["path"]) == item["sha256"]
    parent = read(ROOT / p["parent"]["protocol"]["path"])
    prereg = read(ROOT / p["parent"]["prereg"]["path"])
    assert p["catalog_sha256"] == prereg["catalog_sha256"]
    for field in (
        "broker",
        "views",
        "start",
        "end",
        "original_floors",
        "native_rules",
        "references",
    ):
        assert p[field] == parent[field], field
    for name, digest in parent["sources"].items():
        assert p["sources"].get(name) == digest, "frozen source omitted"
    for name, digest in complete["artifacts"].items():
        assert sha(out / name) == digest, name
    assert sha(out / "catalog.json") == p["catalog_sha256"]
    cats = read(out / "catalog.json")
    assert cats["finite_domain"] == 2
    profiles = {x["name"]: x for x in cats["profiles"]}
    assert set(profiles) == {BASE, B2}
    expected = {f"{name}-{view}-{guard}" for name in profiles for view in VIEWS for guard in GUARDS}
    assert {x.stem for x in (out / "cells-integrity").glob("*.json")} == expected
    auditor = IndependentTapeAudit(p, read(DATA / "manifest.json")["last_quote_utc"])
    rows = {}
    checks = {}
    payloads = {}
    for key in sorted(expected):
        value, proof = _cell(out, key)
        name, view, guard = key.split("-")
        assert value["profile"] == profiles[name] and value["result"]["rules"] == p["native_rules"]
        accounting = auditor.audit_cell(value)
        ticks, _ = full_tick_and_peaks(auditor, value)
        if name == BASE:
            reference = p["references"][view + "-" + guard]
            assert sha(ROOT / reference["path"]) == reference["sha256"]
            original = read(ROOT / reference["path"])
            assert value["result"] == original["result"]
            behavior = {"native_control_exact": True}
        else:
            behavior = audit_protection(auditor, value)
        rows.setdefault(name, {}).setdefault(guard, {})[view] = {
            "metrics": value["metrics"],
            "risk": accounting["risk"],
        }
        checks[key] = dict(accounting=accounting, full_tick=ticks, behavior=behavior)
        payloads[proof["path"]] = proof["sha256"]
        print("PASS independent full-tick B2 cell", len(checks), "/12", key, flush=True)
    eligible = sorted(name for name in profiles if qualify(rows[name], p["original_floors"]))
    assert BASE in eligible
    selected = min(eligible, key=lambda name: (*rank(rows[name]), name != BASE))
    saved = read(out / "results.json")
    assert saved["selected"] == selected and saved["qualified"] == eligible
    for name in profiles:
        for guard in GUARDS:
            for view in VIEWS:
                summary = saved["summaries"][name][guard][view]
                assert summary["metrics"] == rows[name][guard][view]["metrics"]
                for key, value in summary["risk"].items():
                    equal(value, rows[name][guard][view]["risk"][key], "summary " + key)
    repeats = {f"{selected}-{view}-{guard}" for view in VIEWS for guard in GUARDS}
    assert {x.stem for x in (out / "repeats-integrity").glob("*.json")} == repeats
    for key in repeats:
        fresh, proof = _cell(out, key, "repeats")
        original, _ = _cell(out, key)
        assert all(fresh[k] == original[k] for k in ("result", "metrics", "diagnostics", "summary"))
        payloads[proof["path"]] = proof["sha256"]
    all_nets = all(
        rows[B2][g][v]["metrics"]["net_usd"] + 1e-7 >= rows[BASE][g][v]["metrics"]["net_usd"]
        for g in GUARDS
        for v in VIEWS
    )
    improvement = (
        B2 in eligible
        and all_nets
        and rows[B2]["raw"]["base"]["metrics"]["net_usd"]
        > rows[BASE]["raw"]["base"]["metrics"]["net_usd"] + 1e-7
    )
    value = dict(
        status="PASS",
        primary_cells=12,
        fresh_repeats=6,
        full_tick_dd_cells=12,
        protocol_sha256=sha(out / "protocol.json"),
        verifier_sha256=sha(Path(__file__)),
        completion_sha256=sha(out / "COMPLETE.json"),
        selected_profit=selected,
        qualified=eligible,
        matched_native_net_preserved_all_six=all_nets,
        strict_profit_improvement=improvement,
        retain_native=not improvement,
        cost_status="COST_INCONCLUSIVE",
        holdout=False,
        payload_hashes=payloads,
        audited_cells=checks,
    )
    write(out / "independent-verification.json", value)
    write(
        out / "FINAL.json",
        dict(
            status="VERIFIED_COMPLETE",
            paths=12,
            fresh_repeats=6,
            audited_full_tick_paths=12,
            audit_sha256=sha(out / "independent-verification.json"),
            selected_profit=selected,
            strict_profit_improvement=improvement,
            retain_native=not improvement,
            demo_changed=False,
            cost_status="COST_INCONCLUSIVE",
            holdout=False,
        ),
    )
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    verify(args.out)
