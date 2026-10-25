"""Default-shadow entrypoint for the selected C22 candidate; no cutover bypass."""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

from scripts.c22_selected.runner import SelectedDemoRunner
from scripts.c22_selected.execution import install_execution_review
from scripts.c22_selected.strategy import CANDIDATE_ID, CONFIG_PATH, CONTRACT, SNAPSHOT, verify_sources
from scripts.demo_runtime import cli as runtime_cli
from scripts.demo_runtime.cli import main as shared_main


def main(argv=None, *, mt5=None, runner_class=None):
    args = list(sys.argv[1:] if argv is None else argv)
    abbreviated = any(argument.startswith("--") and "--execute".startswith(argument)
                      and argument != "--execute" for argument in args)
    if abbreviated:
        print(json.dumps({"status": "BLOCKED", "reason": "selected_demo_readiness_pending", "order_api_called": False}))
        return 2
    if "--verify-sources" in args:
        parser = argparse.ArgumentParser(allow_abbrev=False)
        parser.add_argument("--verify-sources", action="store_true")
        parser.add_argument("--config", type=Path, default=CONFIG_PATH)
        options = parser.parse_args(args)
        try:
            verify_sources(json.loads(options.config.read_text()))
        except (OSError, ValueError, TypeError):
            print(json.dumps({"status": "BLOCKED", "reason": "source_drift", "broker_api_called": False}))
            return 2
        print(json.dumps({"status": "CONFIG_SOURCES_VERIFIED", "snapshot": SNAPSHOT,
                          "rules_id": CANDIDATE_ID, "broker_api_called": False, "execute": False}))
        return 0
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--cache-output", type=Path)
    parser.add_argument("--execution-review", type=Path)
    selected, args = parser.parse_known_args(args)
    if "--execute" in args and selected.execution_review is None:
        print(json.dumps({"status": "BLOCKED", "reason": "selected_demo_readiness_pending", "order_api_called": False}))
        return 2
    expected = {
        "snapshot": SNAPSHOT, "contract_id": CANDIDATE_ID, "contract": CONTRACT,
        "symbol": "XAUUSDm", "volume": 0.01, "research_only": True,
        "real_money": "PROHIBITED", "commission_unit": "USD_per_lot_round_trip",
    }
    def reviewed_runner(*, config, **kwargs):
        verify_sources(config)
        execute = kwargs.get("execute", False)
        if execute and ("--execute" not in args or selected.execution_review is None):
            raise ValueError("selected_demo_readiness_pending")
        if selected.cache_output is not None:
            kwargs["cache_output"] = selected.cache_output
        runner = (runner_class or SelectedDemoRunner)(config=config, **kwargs)
        if execute:
            try:
                install_execution_review(runner, selected.execution_review, now=runtime_cli.clock_now())
            except Exception:
                runner.close()
                raise
        return runner

    return shared_main(args, mt5=mt5, runner_class=reviewed_runner, name="c22-selected", expected_config=expected)


if __name__ == "__main__":
    raise SystemExit(main())
