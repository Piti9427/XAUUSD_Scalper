"""Frozen C22H4 Demo CLI, sharing explicit identity/order gates with trial30."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main(argv=None, *, mt5=None):
    from scripts.c22h4.runner import C22H4DemoRunner, SNAPSHOT
    from scripts.c22h4.strategy import CONTRACT, CONTRACT_ID
    from scripts.ops.mt5_wine_trial30 import main as run

    return run(
        argv,
        mt5=mt5,
        runner_class=C22H4DemoRunner,
        name="c22h4",
        expected_config=dict(
            snapshot=SNAPSHOT,
            contract_id=CONTRACT_ID,
            contract=CONTRACT,
            symbol="XAUUSDm",
            volume=0.01,
            research_only=True,
            real_money="PROHIBITED",
            commission_unit="USD_per_lot_round_trip",
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
