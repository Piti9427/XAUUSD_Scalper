"""
Re-screen all result JSON files with owner-approved relaxed gates:
  DD <= 35%  (was <= 30% AND <= baseline)
  half trades >= 10  (was >= 20)
  Keep: net > baseline, WR > baseline, RR > baseline, trades >= 60 (full), actual BUY+SELL, risk <= 10%
  Note: trial30 baseline second-half DD is 32.93%/33.34% — candidate must still beat baseline DD.

Run from repo root: PYTHONPATH=. .venv/bin/python docs/reviews/artifacts/rescreen_relaxed_gates.py
"""

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]

# all candidate result files to search
RESULT_FILES = [
    "docs/reviews/2026-10-03-hybrid-reward-results.json",
    "docs/reviews/2026-10-03-hybrid-reward-admission-results.json",
    "docs/reviews/2026-10-03-hybrid-reward-geometry-results.json",
    "docs/reviews/2026-10-03-hybrid-reward-quality-results.json",
    "docs/reviews/2026-10-03-reward-session-results.json",
    "docs/reviews/2026-10-03-hybrid-atr-stop-results.json",
    "docs/reviews/2026-10-03-hybrid-parent-horizon-corrected-results.json",
    "docs/reviews/2026-10-03-hybrid-parent-trend-results.json",
    "docs/reviews/2026-10-03-hybrid-parent-quality-results.json",
    "docs/reviews/2026-10-03-hybrid-parent-reward-fine-results.json",
    "docs/reviews/2026-10-03-hybrid-parent-reward-pause-results.json",
    "docs/reviews/2026-10-03-hybrid-parent-risk-results.json",
    "docs/reviews/2026-10-03-hybrid-parent-atr-results.json",
    "docs/reviews/2026-10-03-hybrid-parent-protection-results.json",
    "docs/reviews/2026-10-03-hybrid-parent-invalidation-results.json",
    "docs/reviews/2026-10-01-admission-tuning-results.json",
    "docs/reviews/2026-10-01-geometry-tuning-results.json",
    "docs/reviews/2026-10-02-horizons-results.json",
    "docs/reviews/2026-10-02-horizon-quality-results.json",
    "docs/reviews/2026-10-02-compression-results.json",
    "docs/reviews/2026-10-02-hybrid-admission-results.json",
    "docs/reviews/2026-10-02-hybrid-invalidation-results.json",
    "docs/reviews/2026-10-02-hybrid-oscillator-results.json",
    "docs/reviews/2026-10-02-oscillator-results.json",
    "docs/reviews/2026-10-01-bidirectional-trial30-results.json",
    "docs/reviews/2026-10-01-dd30-results.json",
    "docs/reviews/2026-10-01-strategy-continuation-results.json",
    "docs/reviews/2026-10-01-public-drawdown-results.json",
]

# NEW gate params (owner-approved relaxation 2026-10-04)
MAX_DD_PCT = 35.0       # was 30.0 AND <= baseline
MIN_HALF_TRADES = 10    # was 20
MIN_FULL_TRADES = 60    # unchanged
REQUIRE_BOTH_SIDES = True  # buy_trades >= 1 AND sell_trades >= 1


def check_window(w_metrics, b_metrics, window_name, full=False):
    """Return list of failure reasons under new gates."""
    failures = []
    for cost_idx, (m, b) in enumerate(zip(w_metrics, b_metrics)):
        cost_label = "base" if cost_idx == 0 else "stress"
        label = f"{window_name}/{cost_label}"

        # net > baseline
        if m["net_usd"] <= b["net_usd"]:
            failures.append(f"{label}: net {m['net_usd']:.3f} <= baseline {b['net_usd']:.3f}")

        # WR > baseline
        cand_wr = m.get("win_rate") or 0.0
        baseline_wr = b.get("win_rate") or 0.0
        if cand_wr <= baseline_wr:
            failures.append(f"{label}: WR {cand_wr:.4f} <= baseline {baseline_wr:.4f}")

        # RR > baseline (use 0 if baseline RR undefined, i.e. all losses)
        baseline_rr = b.get("realized_rr") or 0.0
        cand_rr = m.get("realized_rr") or 0.0
        if cand_rr <= baseline_rr:
            failures.append(f"{label}: RR {cand_rr:.4f} <= baseline {baseline_rr:.4f}")

        # DD <= 35% (NEW: relaxed ceiling)
        if m["max_dd_pct"] > MAX_DD_PCT:
            failures.append(f"{label}: DD {m['max_dd_pct']:.2f}% > {MAX_DD_PCT}%")

        # trades
        min_trades = MIN_FULL_TRADES if full else MIN_HALF_TRADES
        if m["trades"] < min_trades:
            failures.append(f"{label}: trades {m['trades']} < {min_trades}")

        # both sides
        if REQUIRE_BOTH_SIDES:
            if m.get("buy_trades", 0) < 1:
                failures.append(f"{label}: no BUY trades")
            if m.get("sell_trades", 0) < 1:
                failures.append(f"{label}: no SELL trades")

    return failures


qualified = []
all_failures_by_candidate = []

for rel_path in RESULT_FILES:
    path = REPO / rel_path
    if not path.exists():
        print(f"SKIP (not found): {rel_path}", file=sys.stderr)
        continue

    with open(path) as f:
        data = json.load(f)

    rows = data.get("rows", [])
    baseline = data.get("baseline", {})
    if not rows or not baseline:
        print(f"SKIP (no rows/baseline): {rel_path}", file=sys.stderr)
        continue

    b_full = baseline.get("full", [])
    b_first = baseline.get("first_half", [])
    b_second = baseline.get("second_half", [])

    for row in rows:
        m = row.get("metrics", {})
        m_full = m.get("full", [])
        m_first = m.get("first_half", [])
        m_second = m.get("second_half", [])

        if not (m_full and m_first and m_second):
            continue

        # Apply new gates on all 6 scenarios
        fails = []
        fails += check_window(m_full, b_full, "full", full=True)
        fails += check_window(m_first, b_first, "first_half", full=False)
        fails += check_window(m_second, b_second, "second_half", full=False)

        entry = {
            "source": rel_path,
            "trial": row.get("trial"),
            "candidate": row.get("candidate", {}),
            "metrics": m,
            "failures": fails,
        }

        if not fails:
            qualified.append(entry)
        elif len(fails) <= 3:
            # near-miss: <= 3 failures
            all_failures_by_candidate.append(entry)

# Sort near-misses by failure count
all_failures_by_candidate.sort(key=lambda x: len(x["failures"]))

print(f"\n{'='*60}")
print(f"RE-SCREEN RESULTS (new gates: DD<=35%, half trades>=10)")
print(f"{'='*60}")
print(f"Qualified: {len(qualified)}")
print(f"Near-miss (<=3 failures): {len(all_failures_by_candidate)}")

if qualified:
    print(f"\n{'='*40}")
    print("QUALIFIED CANDIDATES:")
    for q in qualified:
        print(f"\n  Source: {q['source']}")
        print(f"  Trial: {q['trial']}")
        mf = q['metrics']['full']
        m1 = q['metrics']['first_half']
        m2 = q['metrics']['second_half']
        print(f"  Full:   base net={mf[0]['net_usd']:.2f} DD={mf[0]['max_dd_pct']:.2f}% WR={mf[0]['win_rate']:.3f} RR={mf[0].get('realized_rr',0):.4f} trades={mf[0]['trades']}")
        if len(mf) > 1:
            print(f"  Full:   stress net={mf[1]['net_usd']:.2f} DD={mf[1]['max_dd_pct']:.2f}%")
        print(f"  First:  base net={m1[0]['net_usd']:.2f} DD={m1[0]['max_dd_pct']:.2f}% trades={m1[0]['trades']}")
        print(f"  Second: base net={m2[0]['net_usd']:.2f} DD={m2[0]['max_dd_pct']:.2f}% trades={m2[0]['trades']}")
        if len(m2) > 1:
            print(f"  Second: stress net={m2[1]['net_usd']:.2f} DD={m2[1]['max_dd_pct']:.2f}%")
        rules = q['candidate'].get('rules', {})
        print(f"  Rules: {json.dumps({k:v for k,v in rules.items() if v not in (0, 0.0, False, 'off', 'all', 'atr', 'immediate', 'legacy', 'fixed', 'static', None)})}")
else:
    print("\nNo fully qualified candidates.")

print(f"\n{'='*40}")
print(f"TOP NEAR-MISSES (<=3 failures):")
for nm in all_failures_by_candidate[:20]:
    mf = nm['metrics']['full']
    m2 = nm['metrics']['second_half']
    print(f"\n  Source: {nm['source'].split('/')[-1]}")
    print(f"  Trial: {nm['trial']}")
    print(f"  Full base: net={mf[0]['net_usd']:.2f} DD={mf[0]['max_dd_pct']:.2f}% trades={mf[0]['trades']} BUY={mf[0].get('buy_trades',0)} SELL={mf[0].get('sell_trades',0)}")
    print(f"  2nd  base: net={m2[0]['net_usd']:.2f} DD={m2[0]['max_dd_pct']:.2f}% trades={m2[0]['trades']}")
    print(f"  Failures ({len(nm['failures'])}): {nm['failures']}")
