"""Read-only, pinned offline probes of current runtime gates versus trial30.

Test fixtures supply synthetic broker inputs. No broker, order or alert APIs.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def main():
    from test_pure_b1_decision import PureB1DecisionTests
    from scripts.pure_b1.cost_policy import validate_cost_policy
    from scripts.pure_b1.decision import decide
    from scripts.pure_b1.shadow import _day_start
    from scripts.strategy import pure_b1_levels

    fixture = PureB1DecisionTests()
    fixture.setUp()
    cases = {}
    for name, overrides in (
        ("control", {}),
        ("missing_cost", {"cost_policy_source": ""}),
        ("missing_day_start", {"day_start_equity": None}),
        ("loss_20_percent", {"equity": 160.0}),
        ("existing_position", {"open_positions": 1}),
        ("insufficient_margin", {"free_margin": 1.0}),
        ("risk_over_cap", {"equity": 40.0, "day_start_equity": 40.0}),
    ):
        result = decide(**(fixture.inputs | overrides))
        cases[name] = {k: result[k] for k in ("admit", "reason", "direction")}
    assert cases["control"]["admit"]
    assert cases["loss_20_percent"]["admit"], "observed old runtime daily40 mismatch changed"
    assert all(not cases[k]["admit"] for k in cases if k not in ("control", "loss_20_percent"))
    policy = json.loads((ROOT / "config/pure_b1_cost_policy.json").read_text())
    pinned = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    kwargs = {"fingerprint": policy["account_fingerprint"]}
    at_review = validate_cost_policy(
        policy, now=datetime.fromisoformat(policy["reviewed_utc"]), **kwargs
    )[1]
    later = validate_cost_policy(policy, now=pinned, **kwargs)[1]
    assert at_review == "operator_attested_for_shadow" and later == "invalid_or_stale"
    with TemporaryDirectory() as temporary:
        state = Path(temporary) / "day.json"
        common = {"fingerprint": "synthetic", "equity": 200.0, "balance": 200.0}
        late = _day_start(state, now=datetime(2026, 10, 1, 0, 0, 5, tzinfo=timezone.utc), **common)[
            1
        ]
        exact = _day_start(state, now=pinned, **common)[1]
        restarted = _day_start(
            state, now=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc), **common
        )[1]
        changed = _day_start(
            state,
            now=datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
            **(common | {"balance": 197.0, "equity": 197.0}),
        )[1]
    assert late == "day_start_unknown" and exact == restarted == "captured_at_utc_boundary"
    assert changed == "balance_changed"
    stop, target = pure_b1_levels(100.0, -1, 2.0)
    assert stop == 105.0 and target == 87.5
    print(
        json.dumps(
            {
                "pinned_utc": pinned.isoformat(),
                "snapshot": "RESEARCH-D48-SELL-BE1R-20261001-T030",
                "synthetic_current_runtime_gates": cases,
                "cost_policy": {"at_original_review": at_review, "at_pinned_today": later},
                "day_start": {
                    "missing_at_00_00_05": late,
                    "capture_at_00_00_00": exact,
                    "restart_same_balance": restarted,
                    "after_balance_change": changed,
                },
                "sell_levels_entry100_atr2": {
                    "current_sl": stop,
                    "current_tp": target,
                    "trial30_sl": 105.0,
                    "trial30_tp": 94.0,
                },
                "broker_tested": False,
                "order_api_called": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
