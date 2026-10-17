"""Pure helpers of the Wine MT5 Strategy Tester runner (no Wine, no terminal)."""

import unittest

from scripts.ops.mt5_wine_tester import (
    tester_ini,
    set_file_text,
    resolve_params,
    redact,
    run_segment,
    MODELS,
)


class TesterRunnerTests(unittest.TestCase):
    def test_ini_requests_real_ticks_shutdown_and_local_agent(self):
        ini = tester_ini(
            "B1FinalEA",
            "XAUUSDm",
            "M15",
            MODELS["real_ticks"],
            "2026.05.14",
            "2026.09.26",
            1173.46,
            1000,
            "reports\\run",
            "B1FinalEA_run.set",
        )
        for line in (
            "Expert=B1Final\\B1FinalEA.ex5",
            "Model=4",
            "Leverage=1:1000",
            "Deposit=1173.46",
            "ShutdownTerminal=1",
            "UseLocal=1",
            "UseCloud=0",
            "ExpertParameters=B1FinalEA_run.set",
        ):
            self.assertIn(line + "\r\n", ini)

    def test_ini_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError):
            tester_ini("x", "XAUUSDm", "M15", 9, "a", "b", 100, 1000, "r")
        with self.assertRaises(ValueError):
            tester_ini("x", "XAUUSDm", "M15", 4, "a", "b", 0, 1000, "r")

    def test_set_file_lowercases_bools_and_rejects_newlines(self):
        self.assertEqual(
            set_file_text({"BootstrapState": True, "ExitMode": 2}),
            "BootstrapState=true\r\nExitMode=2\r\n",
        )
        with self.assertRaises(ValueError):
            set_file_text({"x": "a\nb"})

    def test_private_params_resolved_but_redacted_in_shared_manifest(self):
        resolved, shared = resolve_params(
            {"ExpectedLogin": "env:LOGIN", "ExitMode": "0"}, {"LOGIN": "1234567"}
        )
        self.assertEqual(resolved["ExpectedLogin"], "1234567")
        self.assertEqual(shared["ExpectedLogin"], "<LOGIN>")
        self.assertEqual(shared["ExitMode"], "0")
        with self.assertRaises(SystemExit):
            resolve_params({"ExpectedLogin": "env:MISSING"}, {})

    def test_redact_and_last_run_segment(self):
        text = "old login (build 1)\nold\nnew login (build 2)\naccount 1234567 on Srv\n"
        segment = run_segment(text)
        self.assertTrue(segment.startswith("new login"))
        self.assertEqual(
            redact(
                segment, {"XAUUSD_MT5_LOGIN": "1234567", "XAUUSD_MT5_SERVER": "Srv", "OTHER": "on"}
            ),
            "new login (build 2)\naccount <XAUUSD_MT5_LOGIN> on <XAUUSD_MT5_SERVER>\n",
        )


if __name__ == "__main__":
    unittest.main()
