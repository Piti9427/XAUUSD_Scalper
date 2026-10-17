"""Foundation story 49: Demo readiness ≠ real-money authorization."""

from __future__ import annotations

import unittest

from scripts.smc.real_money_approval import (
    REAL_MONEY_ENV,
    evaluate_real_money_approval,
    require_real_money_approval,
)


class RealMoneyApprovalTests(unittest.TestCase):
    def test_dry_run_never_requires_approval(self):
        report = evaluate_real_money_approval(
            dry_run=True,
            allow_demo_only=False,
            config_approved=False,
            env={},
        )
        self.assertTrue(report.ok)
        self.assertFalse(report.required)

    def test_demo_live_path_does_not_require_real_money_flag(self):
        report = evaluate_real_money_approval(
            dry_run=False,
            allow_demo_only=True,
            config_approved=False,
            env={},
        )
        self.assertTrue(report.ok)
        self.assertFalse(report.required)

    def test_real_money_path_fails_without_dual_approval(self):
        report = evaluate_real_money_approval(
            dry_run=False,
            allow_demo_only=False,
            config_approved=False,
            env={},
        )
        self.assertFalse(report.ok)
        self.assertTrue(report.required)
        self.assertIn("missing_env_approval", report.reasons)
        self.assertIn("missing_config_approval", report.reasons)

    def test_real_money_path_needs_both_env_and_config(self):
        env_only = evaluate_real_money_approval(
            dry_run=False,
            allow_demo_only=False,
            config_approved=False,
            env={REAL_MONEY_ENV: "1"},
        )
        self.assertFalse(env_only.ok)
        self.assertEqual(env_only.reasons, ("missing_config_approval",))

        config_only = evaluate_real_money_approval(
            dry_run=False,
            allow_demo_only=False,
            config_approved=True,
            env={},
        )
        self.assertFalse(config_only.ok)
        self.assertEqual(config_only.reasons, ("missing_env_approval",))

        both = evaluate_real_money_approval(
            dry_run=False,
            allow_demo_only=False,
            config_approved=True,
            env={REAL_MONEY_ENV: "1"},
        )
        self.assertTrue(both.ok)
        self.assertTrue(both.required)

    def test_require_raises_system_exit_when_blocked(self):
        with self.assertRaises(SystemExit) as ctx:
            require_real_money_approval(
                dry_run=False,
                allow_demo_only=False,
                config_approved=False,
                env={},
            )
        self.assertIn("real-money approval boundary", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
