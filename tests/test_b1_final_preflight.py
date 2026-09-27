"""B1-FINAL Standard Demo preflight -> affordability report (no broker calls)."""
import copy
import json
import unittest

from scripts.ops.b1_final_preflight import evaluate, B1_MAGIC


def snapshot(**overrides):
    base = {
        'created_at_utc': '2026-09-27T02:00:00+00:00', 'initialized': True, 'last_error': [1, 'Success'],
        'identity_match': True, 'order_api_called': False,
        'account': {'trade_mode': 0, 'margin_mode': 2, 'currency': 'USD', 'equity': 1173.46,
                    'balance': 1173.46, 'margin_free': 1173.46, 'leverage': 1000},
        'symbol_spec': {'name': 'XAUUSDm', 'trade_mode': 4, 'volume_min': 0.01, 'volume_step': 0.01,
                        'volume_max': 200.0, 'trade_tick_size': 0.001, 'point': 0.001, 'currency_profit': 'USD',
                        'trade_stops_level': 0, 'trade_freeze_level': 0, 'filling_mode': 3},
        'tick': {'bid': 4285.9, 'ask': 4286.16},
        'exposure': [],
        # 1-lot loss and margin from broker calculations for each stop distance.
        'stops': [{'label': 'p10', 'distance': 10.0, 'loss_1lot': 1000.0, 'margin_1lot': 428.6},
                  {'label': 'median', 'distance': 20.0, 'loss_1lot': 2000.0, 'margin_1lot': 428.6},
                  {'label': 'current', 'distance': 2.0, 'loss_1lot': 200.0, 'margin_1lot': 428.6}],
    }
    for key, value in overrides.items():
        base[key] = value
    return base


class PreflightTests(unittest.TestCase):
    def test_connection_failure_is_unverified_not_unsupported(self):
        report = evaluate(snapshot(initialized=False, last_error=[-6, 'Authorization failed']))
        self.assertEqual(report['status'], 'UNVERIFIED')
        self.assertNotIn('ACCOUNT_BLOCKED', json.dumps(report))
        self.assertEqual(report['scenarios'], [])

    def test_identity_mismatch_blocks_without_revealing_identity(self):
        report = evaluate(snapshot(identity_match=False))
        self.assertEqual(report['status'], 'BLOCKED')
        self.assertIn('ACCOUNT_IDENTITY_MISMATCH', report['blocking_reasons'])
        self.assertNotIn('login', json.dumps(report).lower())

    def test_real_account_rejected(self):
        snap = snapshot(); snap['account']['trade_mode'] = 2
        self.assertIn('REAL_ACCOUNT_REJECTED', evaluate(snap)['blocking_reasons'])

    def test_netting_account_rejected(self):
        snap = snapshot(); snap['account']['margin_mode'] = 0
        self.assertIn('NOT_HEDGING', evaluate(snap)['blocking_reasons'])

    def test_missing_or_substituted_symbol_specification_blocks(self):
        snap = snapshot(); del snap['symbol_spec']['volume_step']
        self.assertIn('SPECIFICATION_MISSING', evaluate(snap)['blocking_reasons'])
        snap = snapshot(); snap['symbol_spec']['name'] = 'XAUUSD'
        self.assertIn('SYMBOL_MISMATCH', evaluate(snap)['blocking_reasons'])
        self.assertIn('SPECIFICATION_MISSING', evaluate(snapshot(symbol_spec=None))['blocking_reasons'])

    def test_foreign_exposure_blocks_new_risk_but_own_magic_does_not(self):
        report = evaluate(snapshot(exposure=[{'kind': 'position', 'magic': 0}]))
        self.assertIn('FOREIGN_EXPOSURE', report['blocking_reasons'])
        report = evaluate(snapshot(exposure=[{'kind': 'position', 'magic': B1_MAGIC}]))
        self.assertNotIn('FOREIGN_EXPOSURE', report['blocking_reasons'])

    def test_actual_and_hypothetical_scenarios_are_separate_and_floor_volume(self):
        snap = snapshot()
        before = copy.deepcopy(snap)
        report = evaluate(snap)
        self.assertEqual(snap, before)
        names = [s['scenario'] for s in report['scenarios']]
        self.assertEqual(names, ['actual_demo_equity', 'hypothetical_100_usd'])
        actual = report['scenarios'][0]
        self.assertEqual(actual['equity'], 1173.46)
        self.assertEqual(actual['equity_source'], 'broker_snapshot')
        self.assertEqual(report['scenarios'][1]['equity_source'], 'hypothetical_research_deposit')
        current = {r['stop']: r for r in actual['rows']}['current']
        # budget 11.7346; 200/lot -> raw 0.0587 -> floor 0.05
        self.assertAlmostEqual(current['risk_budget'], 11.7346)
        self.assertAlmostEqual(current['normalized_volume'], 0.05)
        self.assertEqual(current['outcome'], 'ADMIT')
        self.assertLessEqual(current['volume_risk'], current['risk_budget'])

    def test_below_minimum_lot_rejected_with_budget_and_min_lot_risk(self):
        median = {r['stop']: r for r in evaluate(snapshot())['scenarios'][0]['rows']}['median']
        self.assertEqual(median['outcome'], 'RISK_BELOW_MINIMUM_LOT')
        self.assertAlmostEqual(median['minimum_lot_risk'], 20.0)
        self.assertAlmostEqual(median['risk_budget'], 11.7346)
        self.assertEqual(median['normalized_volume'], 0.0)

    def test_account_blocked_verdict_when_median_stop_not_admitted(self):
        report = evaluate(snapshot())
        self.assertEqual(report['scenarios'][0]['verdict'], 'ACCOUNT_BLOCKED')
        self.assertEqual(report['scenarios'][1]['verdict'], 'ACCOUNT_BLOCKED')
        self.assertEqual(report['status'], 'VERIFIED')
        self.assertFalse(report['account_qualified'])
        self.assertFalse(report['order_api_called'])

    def test_insufficient_margin(self):
        snap = snapshot(); snap['account']['margin_free'] = 5.0
        current = {r['stop']: r for r in evaluate(snap)['scenarios'][0]['rows']}['current']
        self.assertEqual(current['outcome'], 'INSUFFICIENT_MARGIN')

    def test_feasible_when_median_admitted(self):
        snap = snapshot(); snap['account'].update(equity=100000.0, balance=100000.0, margin_free=100000.0)
        self.assertEqual(evaluate(snap)['scenarios'][0]['verdict'], 'ACCOUNT_FEASIBLE_AT_MEDIAN_STOP')

    def test_probe_that_called_order_api_is_rejected(self):
        self.assertEqual(evaluate(snapshot(order_api_called=True))['status'], 'INVALID_PROBE')

    def test_fee_and_reserve_sizing_matches_ea_admission(self):
        # EA per-lot risk = loss*(1+reserve) + commission + exit fee
        current = {r['stop']: r for r in evaluate(snapshot(), commission_per_lot=7., exit_fee_per_lot=7.,
                                                   admission_reserve_r=.1)['scenarios'][0]['rows']}['current']
        per_lot = 200.*1.1+14.
        self.assertAlmostEqual(current['raw_volume'], 11.7346/per_lot)
        self.assertAlmostEqual(current['minimum_lot_risk'], per_lot*.01)
        self.assertEqual(current['outcome'], 'ADMIT')
        self.assertLessEqual(current['volume_risk'], current['risk_budget'])

    def test_utc_offset_verified_only_from_fresh_tick(self):
        fresh = evaluate(snapshot(server_tick_epoch=1790000030, probe_utc_epoch=1790000000))
        self.assertEqual(fresh['utc_offset_status'], 'VERIFIED')
        shifted = evaluate(snapshot(server_tick_epoch=1790003630, probe_utc_epoch=1790000000))
        self.assertIn('UTC_OFFSET_MISMATCH', shifted['blocking_reasons'])
        closed = evaluate(snapshot(server_tick_epoch=1789900000, probe_utc_epoch=1790000000))
        self.assertEqual(closed['utc_offset_status'], 'UNVERIFIED_NO_FRESH_TICK')
        self.assertEqual(closed['status'], 'VERIFIED')

    def test_report_hash_covers_sanitized_snapshot(self):
        a = evaluate(snapshot())
        b = evaluate(snapshot(tick={'bid': 1.0, 'ask': 1.1}))
        self.assertNotEqual(a['snapshot_sha256'], b['snapshot_sha256'])
        self.assertEqual(len(a['snapshot_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
