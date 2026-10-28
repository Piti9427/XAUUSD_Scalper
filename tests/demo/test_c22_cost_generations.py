"""A new cost generation cannot erase an earlier observed charge incident."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest

from scripts.demo_runtime.journal import Journal
from scripts.c22_selected.cost_generations import CostGenerationLedger
from tests.demo.test_c22_cost_diagnostics import v2_policy, rebind

NOW = datetime(2026, 10, 28, 9, tzinfo=timezone.utc)
MAGIC = 22261025


def policy():
    value = v2_policy(NOW - timedelta(days=1))
    days = {}
    for offset in range(8):
        stamp = NOW - timedelta(days=1) + timedelta(days=offset)
        days[stamp.date().isoformat()] = dict(rollover_utc=stamp.replace(hour=21).isoformat(), buy=-10.0, sell=0.0)
    value['evidence']['swap_calendar']['document']['days'] = days
    rebind(value, 'swap_calendar')
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def ledger(swap=-0.1, fee=0.0, ident=7, opening=None, exit_at=None):
    opening = opening or NOW - timedelta(days=1)
    exit_at = exit_at or NOW - timedelta(hours=1)
    return [NS(ticket=ident * 10 + 1, position_id=ident, magic=MAGIC, entry=0, type=0,
               volume=.01, time_msc=int(opening.timestamp() * 1000), profit=0., commission=0., fee=0., swap=0.),
            NS(ticket=ident * 10 + 2, position_id=ident, magic=0, entry=1, type=1,
               volume=.01, time_msc=int(exit_at.timestamp() * 1000), profit=4., commission=0., fee=fee, swap=swap)]


def deposit():
    return NS(ticket=1, position_id=0, magic=0, entry=0, type=2, volume=0.,
              time_msc=int((NOW - timedelta(days=10)).timestamp() * 1000),
              profit=200., commission=0., fee=0., swap=0.)


class CostGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'selected.sqlite3'
        self.journal = Journal(self.path)
        self.addCleanup(self.journal.close)
        self.fingerprint = policy()['account_fingerprint']
        self.subject = CostGenerationLedger(self.journal, fingerprint=self.fingerprint, magic=MAGIC)
        self.policy = policy()
        self.generation = self.subject.register_generation(self.policy, now=NOW,
            evidence_sha256='a' * 64, original_review_sha256='b' * 64)

    def audit(self, rows, **kwargs):
        data = [deposit()] + rows
        balance = sum(float(getattr(d, k)) for d in data for k in ('profit', 'commission', 'swap', 'fee'))
        return self.subject.audit_history(data, total=len(data),
            history_start=datetime(1970, 1, 1, tzinfo=timezone.utc),
            history_end=NOW, balance=balance, positions=[], now=NOW, **kwargs)

    def bind(self, ident=7, generation=None):
        return self.subject.bind_position(ident, generation or self.generation,
            evidence_sha256='c' * 64, now=NOW)

    def test_higher_lower_swap_and_excess_fee_incidents_survive_new_review_and_restart(self):
        for kind, swap, fee in [('higher', -.5, 0.), ('lower', 0., 0.), ('fee', -.1, -.01)]:
            with self.subTest(kind=kind):
                self.setUp()
                self.bind()
                first = self.audit(ledger(swap, fee))
                self.assertEqual(first['status'], 'BLOCKED')
                self.assertEqual(first['unresolved_incidents'][0]['code'], 'cost_broker_deal_drift')
                new = deepcopy(self.policy)
                new['reviewed_utc'] = NOW.isoformat()
                self.subject.register_generation(new, now=NOW, evidence_sha256='d' * 64)
                self.journal.close()
                self.journal = Journal(self.path)
                self.subject = CostGenerationLedger(self.journal, fingerprint=self.fingerprint, magic=MAGIC)
                again = self.audit(ledger(swap, fee))
                self.assertEqual(again['status'], 'BLOCKED')
                self.assertEqual(again['unresolved_incidents'][0]['incident_id'],
                                 first['unresolved_incidents'][0]['incident_id'])
                self.assertEqual(again['unresolved_incidents'][0]['generation_id'], self.generation)
                self.assertEqual(again['legacy_cutoff_utc'], self.policy['reviewed_utc'])
                self.assertIsNone(again['checkpoint'])
                self.journal.close()


    def test_matching_costs_advance_coverage_without_mutating_financial_state(self):
        self.journal.put('active', {'status': 'PROOF_ONLY'})
        self.journal.put('day', {'day': '2026-10-28', 'equity': 200.})
        self.journal.put('selected_last_loss_ms', 1000)
        self.journal.put('safety_halt', 'retain')
        self.bind()
        report = self.audit(ledger())
        self.assertEqual(report['status'], 'CLEAR')
        self.assertEqual(report['checkpoint']['audited_positions'], 1)
        self.assertEqual(report['checkpoint']['audited_exit_deals'], 1)
        self.assertAlmostEqual(report['checkpoint']['cash_total'], 203.9)
        self.assertEqual(report['checkpoint']['history_count'], 3)
        self.assertEqual(report['unresolved_incidents'], [])
        self.assertFalse(report['execution_authorized'])
        expected = dict(report)
        expected.pop('receipt_sha256')
        self.assertEqual(report['receipt_sha256'], digest(expected))
        self.assertEqual(self.journal.get('active'), {'status': 'PROOF_ONLY'})
        self.assertEqual(self.journal.get('day'), {'day': '2026-10-28', 'equity': 200.})
        self.assertEqual(self.journal.get('selected_last_loss_ms'), 1000)
        self.assertEqual(self.journal.get('safety_halt'), 'retain')

    def test_late_out_of_order_exit_is_audited_even_before_previous_checkpoint(self):
        self.bind()
        first = self.audit(ledger())
        self.assertEqual(first['status'], 'CLEAR')
        self.bind(8)
        late = ledger(ident=8, opening=NOW - timedelta(hours=23), exit_at=NOW - timedelta(hours=2))
        # Full history contains a newly available older-time position, unordered.
        rows = list(reversed(ledger() + late))
        result = self.audit(rows)
        self.assertEqual(result['status'], 'CLEAR')
        self.assertEqual(result['checkpoint']['audited_positions'], 2)
        self.assertEqual(result['checkpoint']['audited_exit_deals'], 2)
        self.assertEqual(result['checkpoint']['history_count'], 5)
        self.assertNotEqual(result['checkpoint']['snapshot_sha256'], first['checkpoint']['snapshot_sha256'])

    def test_incomplete_duplicate_or_cash_mismatch_cannot_advance_then_valid_snapshot_recovers(self):
        self.bind()
        original = self.audit(ledger())['checkpoint']
        for kind in ('count', 'duplicate', 'cash', 'future', 'exposure', 'nonfinite'):
            with self.subTest(kind=kind):
                data = [deposit()] + ledger()
                total = len(data)
                balance = 203.9
                positions = []
                end = NOW
                if kind == 'count':
                    total += 1
                elif kind == 'duplicate':
                    data.append(deepcopy(data[-1]))
                    total += 1
                elif kind == 'cash':
                    balance += 1.
                elif kind == 'future':
                    data[-1].time_msc = int((NOW + timedelta(seconds=1)).timestamp() * 1000)
                elif kind == 'nonfinite':
                    data[-1].swap = float('nan')
                else:
                    positions = None
                bad = self.subject.audit_history(data, total=total,
                    history_start=datetime(1970, 1, 1, tzinfo=timezone.utc),
                    history_end=end, balance=balance, positions=positions, now=NOW)
                self.assertEqual(bad['status'], 'BLOCKED')
                self.assertEqual(bad['checkpoint'], original)
                self.assertEqual(bad['unresolved_incidents'], [])
        recovered = self.audit(ledger())
        self.assertEqual(recovered['status'], 'CLEAR')
        self.assertEqual(recovered['checkpoint'], original)

    def test_missing_or_changed_old_deal_is_sticky_and_does_not_advance_checkpoint(self):
        for kind in ('missing', 'changed'):
            with self.subTest(kind=kind):
                self.setUp()
                self.bind()
                before = self.audit(ledger())['checkpoint']
                rows = [] if kind == 'missing' else ledger(swap=-.11)
                result = self.audit(rows)
                self.assertEqual(result['status'], 'BLOCKED')
                self.assertEqual(result['checkpoint'], before)
                self.assertEqual(result['unresolved_incidents'][0]['code'], 'cost_history_changed_or_missing')
                self.assertEqual(self.audit(ledger())['status'], 'BLOCKED')
                self.journal.close()

    def test_legacy_exits_before_original_review_are_recorded_without_fake_cost_qualification(self):
        old = ledger(swap=-30., opening=NOW - timedelta(days=3), exit_at=NOW - timedelta(days=2))
        result = self.audit(old)
        self.assertEqual(result['status'], 'CLEAR')
        self.assertEqual(result['checkpoint']['legacy_pre_review_positions'], 1)
        self.assertEqual(result['checkpoint']['audited_positions'], 0)
        self.assertEqual(result['checkpoint']['audited_exit_deals'], 0)
        self.assertEqual(result['unresolved_incidents'], [])
        self.assertEqual(result['original_review_sha256'], 'b' * 64)
        newer = deepcopy(self.policy)
        newer['reviewed_utc'] = NOW.isoformat()
        self.subject.register_generation(newer, now=NOW, evidence_sha256='d' * 64)
        with self.assertRaisesRegex(ValueError, 'original_review_immutable'):
            self.subject.register_generation(newer, now=NOW, evidence_sha256='d' * 64,
                                             original_review_sha256='e' * 64)
        self.assertEqual(self.subject.status()['legacy_cutoff_utc'], self.policy['reviewed_utc'])

    def test_unbound_position_or_missing_original_generation_calendar_is_not_guessed(self):
        unbound = self.audit(ledger())
        self.assertEqual(unbound['status'], 'BLOCKED')
        self.assertEqual(unbound['unresolved_incidents'][0]['code'], 'cost_position_generation_unbound')
        self.assertEqual(unbound['generation_ids'], [self.generation])
        self.setUp()
        missing = deepcopy(self.policy)
        missing['evidence']['swap_calendar']['document']['days'].pop('2026-10-27')
        rebind(missing, 'swap_calendar')
        generation = self.subject.register_generation(missing, now=NOW, evidence_sha256='d' * 64)
        self.bind(generation=generation)
        result = self.audit(ledger())
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['unresolved_incidents'][0]['code'], 'cost_swap_calendar_missing')
        self.assertEqual(result['unresolved_incidents'][0]['generation_id'], generation)

    def test_position_binding_is_immutable_and_review_reference_never_clears_drift(self):
        self.bind()
        newer = deepcopy(self.policy)
        newer['reviewed_utc'] = NOW.isoformat()
        other = self.subject.register_generation(newer, now=NOW, evidence_sha256='d' * 64)
        with self.assertRaisesRegex(ValueError, 'binding_immutable'):
            self.bind(generation=other)
        result = self.audit(ledger(swap=-.5))
        incident = result['unresolved_incidents'][0]['incident_id']
        reviewed = self.subject.record_resolution(incident, decision_sha256='e' * 64, now=NOW)
        self.assertEqual(reviewed['status'], 'BLOCKED')
        refs = reviewed['unresolved_incidents'][0]['resolution_references']
        self.assertEqual(refs, [dict(decision_sha256='e' * 64, recorded_utc=NOW.isoformat(),
                                  status='REVIEW_RECORDED_NOT_CLEARED')])
        again = self.subject.record_resolution(incident, decision_sha256='e' * 64, now=NOW)
        self.assertEqual(again, reviewed)

    def test_audit_and_checkpoint_roll_back_together_when_state_write_fails(self):
        self.bind()
        before = self.subject.status()
        self.journal.conn.executescript("""
            CREATE TRIGGER deny_cost_state BEFORE UPDATE ON kv
            WHEN NEW.key='selected_cost_generations_v1'
            BEGIN SELECT RAISE(ABORT, 'injected_failure'); END;
        """)
        count_before = self.journal.conn.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            self.audit(ledger())
        self.assertEqual(self.subject.status(), before)
        count_after = self.journal.conn.execute('SELECT COUNT(*) FROM audit_events').fetchone()[0]
        self.assertEqual(count_before, count_after)
        self.journal.conn.execute('DROP TRIGGER deny_cost_state')
        self.assertEqual(self.audit(ledger())['status'], 'CLEAR')

    def test_generation_registration_rejects_bad_binding_future_review_and_malformed_policy(self):
        for kind in ('account', 'future', 'hash', 'version', 'proof'):
            with self.subTest(kind=kind):
                value = deepcopy(self.policy)
                proof = 'd' * 64
                if kind == 'account':
                    value['account_fingerprint'] = 'f' * 16
                elif kind == 'future':
                    value['reviewed_utc'] = (NOW + timedelta(seconds=1)).isoformat()
                elif kind == 'hash':
                    value['evidence']['tariff']['sha256'] = '0' * 64
                elif kind == 'version':
                    value['version'] = 1
                else:
                    proof = 'not-a-hash'
                before = self.subject.status()
                with self.assertRaises(ValueError):
                    self.subject.register_generation(value, now=NOW, evidence_sha256=proof)
                self.assertEqual(self.subject.status(), before)



    def test_malformed_policy_and_sdk_field_error_expose_only_fixed_codes(self):
        for value in (None, [], {}, {'version': 2}):
            with self.subTest(policy=value):
                before = self.subject.status()
                with self.assertRaisesRegex(ValueError, '^cost_generation_policy_invalid$'):
                    self.subject.register_generation(value, now=NOW, evidence_sha256='d' * 64)
                self.assertEqual(self.subject.status(), before)
        class BrokenDeal:
            @property
            def ticket(self):
                raise ValueError('cost_history_SECRET-password')
        report = self.subject.audit_history([BrokenDeal()], total=1,
            history_start=datetime(1970, 1, 1, tzinfo=timezone.utc), history_end=NOW,
            balance=200., positions=[], now=NOW)
        self.assertEqual(report['latest_attempt']['reason'], 'cost_history_fields_missing')
        self.assertNotIn('SECRET', json.dumps(report))

    def test_existing_financial_transaction_is_never_committed_by_cost_evidence(self):
        new = deepcopy(self.policy)
        new['reviewed_utc'] = NOW.isoformat()
        self.journal.conn.execute("INSERT INTO kv VALUES ('pending_financial_fixture', '1')")
        self.assertTrue(self.journal.conn.in_transaction)
        with self.assertRaisesRegex(ValueError, 'transaction_owned_elsewhere'):
            self.subject.register_generation(new, now=NOW, evidence_sha256='d' * 64)
        self.assertTrue(self.journal.conn.in_transaction)
        self.journal.conn.rollback()
        self.assertIsNone(self.journal.get('pending_financial_fixture'))
        self.assertEqual(self.subject.status()['generation_ids'], [self.generation])



    def test_append_only_cost_audit_detects_incident_reset_or_deleted_state(self):
        for kind in ('erase_incidents', 'restore_old_clear', 'delete_state'):
            with self.subTest(kind=kind):
                self.setUp()
                self.bind()
                self.audit(ledger())
                previous = self.journal.get('selected_cost_generations_v1')
                self.audit(ledger(swap=-.5))
                state = self.journal.get('selected_cost_generations_v1')
                if kind == 'erase_incidents':
                    state['incidents'] = {}
                    state['last_attempt']['status'] = 'CLEAR'
                    self.journal.put('selected_cost_generations_v1', state)
                elif kind == 'restore_old_clear':
                    self.journal.put('selected_cost_generations_v1', previous)
                else:
                    with self.journal.conn:
                        self.journal.conn.execute("DELETE FROM kv WHERE key='selected_cost_generations_v1'")
                with self.assertRaisesRegex(ValueError, 'cost_generation_state_audit'):
                    self.subject.status()
                self.journal.close()


if __name__ == '__main__':
    unittest.main()
