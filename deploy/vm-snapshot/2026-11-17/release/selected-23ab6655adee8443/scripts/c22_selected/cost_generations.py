"""Durable cost provenance in the existing sender journal; never entry authority.

The original accepted policy review cutoff is enrolled once. Later policy
reviews cannot change it. Each post-cutoff closed owned position requires an
explicit, evidence-bound generation association; missing provenance is refused,
not assigned to whichever generation happens to be current.

This module neither collects broker facts nor resolves financial authority. Its
caller supplies the existing sender's complete epoch reads. Actual charge math
is delegated to validate_observed_costs with the stored position generation.
"""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from types import SimpleNamespace

from scripts.demo_runtime.costs import validate_observed_costs, validate_policy

_KEY = 'selected_cost_generations_v1'
_CASH = ('profit', 'commission', 'swap', 'fee')
_FIELDS = ('ticket', 'position_id', 'magic', 'entry', 'type', 'volume', 'time_msc') + _CASH
_HISTORY_CODES = frozenset({
    'cost_history_invalid_numeric', 'cost_history_epoch_window_invalid', 'cost_history_count_mismatch',
    'cost_history_invalid_identity', 'cost_history_duplicate_ticket', 'cost_history_future_deal',
    'cost_history_invalid_volume', 'cost_history_balance_mismatch', 'cost_history_exposure_unknown',
    'cost_history_position_invalid', 'cost_history_position_mismatch',
})


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _utc(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(stamp, datetime) or stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise ValueError('cost_generation_aware_utc_required')
    return stamp


def _hex(value, length=64):
    return isinstance(value, str) and len(value) == length and all(c in '0123456789abcdef' for c in value)


def _number(value, *, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (positive and value <= 0)):
        raise ValueError('cost_history_invalid_numeric')
    return float(value)


class CostGenerationLedger:
    """Append evidence atomically without touching native financial state.

    Generation IDs are canonical policy SHA256s. The independently obtained
    original review hash is provenance, not a newly created owner approval.
    register/bind/audit never install policy, send an order or clear a halt.
    """

    def __init__(self, journal, *, fingerprint, magic):
        if not _hex(fingerprint, 16) or type(magic) is not int or magic <= 0:
            raise ValueError('cost_generation_identity_invalid')
        self.journal = journal
        self.fingerprint = fingerprint
        self.magic = magic
        self._load()

    def _load(self):
        state = self.journal.get(_KEY)
        row = self.journal.conn.execute(
            "SELECT payload FROM audit_events WHERE json_extract(payload, '$.kind')=? ORDER BY id DESC LIMIT 1",
            ('COST_GENERATIONS',)).fetchone()
        try:
            last = json.loads(row[0]) if row is not None else None
            recorded = last['cost_state_sha256'] if last is not None else None
            observed = _digest(state) if state is not None else None
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('cost_generation_state_audit_invalid') from error
        if ((state is None and recorded is not None)
                or (state is not None and (not _hex(recorded) or observed != recorded))):
            raise ValueError('cost_generation_state_audit_mismatch')
        if state is None:
            return dict(schema_version=1, account_fingerprint=self.fingerprint, magic=self.magic,
                        generations={}, positions={}, audits={}, incidents={}, deals={},
                        checkpoint=None, last_attempt=None, legacy_cutoff_utc=None,
                        original_review_sha256=None)
        try:
            if (state['schema_version'] != 1 or state['account_fingerprint'] != self.fingerprint
                    or state['magic'] != self.magic):
                raise ValueError('cost_generation_identity_mismatch')
            for ident, generation in state['generations'].items():
                if _digest(generation['policy']) != ident:
                    raise ValueError('cost_generation_policy_hash_drift')
            for value in state['positions'].values():
                if value['generation_id'] not in state['generations']:
                    raise ValueError('cost_generation_binding_invalid')
            for key in ('audits', 'incidents', 'deals'):
                if not isinstance(state[key], dict):
                    raise ValueError('cost_generation_state_invalid')
            _utc(state['legacy_cutoff_utc'])
            if not _hex(state['original_review_sha256']):
                raise ValueError('cost_generation_state_invalid')
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError('cost_generation_state_invalid') from error
        return deepcopy(state)

    def _save(self, state, *, action, now, facts):
        if self.journal.conn.in_transaction:
            raise ValueError('cost_generation_transaction_owned_elsewhere')
        raw = json.dumps(state, sort_keys=True, allow_nan=False)
        # The shared Journal owns this connection/single-writer lock. Calling
        # its public put/audit separately would commit a torn checkpoint.
        with self.journal.conn:
            self.journal._audit('COST_GENERATIONS', action=action, observed_utc=now.isoformat(),
                                cost_state_sha256=_digest(state), **facts)
            self.journal.conn.execute(
                'INSERT INTO kv VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                (_KEY, raw))

    def register_generation(self, policy, *, evidence_sha256, now, original_review_sha256=None):
        now = _utc(now)
        try:
            if not isinstance(policy, dict):
                raise ValueError('cost_generation_policy_invalid')
            policy = deepcopy(policy)
            reviewed = _utc(policy['reviewed_utc'])
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            raise ValueError('cost_generation_policy_invalid') from error
        if reviewed > now or not _hex(evidence_sha256) or policy.get('version') != 2:
            raise ValueError('cost_generation_policy_invalid')
        valid, _ = validate_policy(policy, fingerprint=self.fingerprint, now=reviewed, strategy='c22h4')
        if not valid:
            raise ValueError('cost_generation_policy_invalid')
        ident = _digest(policy)
        state = self._load()
        if state['legacy_cutoff_utc'] is None:
            if not _hex(original_review_sha256):
                raise ValueError('cost_generation_original_review_required')
            state['legacy_cutoff_utc'] = reviewed.isoformat()
            state['original_review_sha256'] = original_review_sha256
        elif original_review_sha256 is not None and original_review_sha256 != state['original_review_sha256']:
            raise ValueError('cost_generation_original_review_immutable')
        if ident in state['generations']:
            return ident
        record = dict(policy=policy, evidence_sha256=evidence_sha256, registered_utc=now.isoformat())
        state['generations'][ident] = record
        self._save(state, action='REGISTER', now=now, facts=dict(generation_id=ident, generation=record))
        return ident

    def bind_position(self, position_id, generation_id, *, evidence_sha256, now):
        now = _utc(now)
        if type(position_id) is not int or position_id <= 0 or not _hex(evidence_sha256):
            raise ValueError('cost_generation_position_binding_invalid')
        state = self._load()
        if generation_id not in state['generations']:
            raise ValueError('cost_generation_unknown')
        key = str(position_id)
        prior = state['positions'].get(key)
        if prior is not None:
            if prior['generation_id'] != generation_id:
                raise ValueError('cost_generation_position_binding_immutable')
            return deepcopy(prior)
        binding = dict(generation_id=generation_id, evidence_sha256=evidence_sha256,
                       bound_utc=now.isoformat())
        state['positions'][key] = binding
        self._save(state, action='BIND', now=now, facts=dict(position_id=position_id, binding=binding))
        return deepcopy(binding)

    def _history(self, deals, *, total, history_start, history_end, balance, positions, now):
        start, end = _utc(history_start), _utc(history_end)
        if (start != datetime(1970, 1, 1, tzinfo=timezone.utc) or not start <= end <= now
                or now - end > timedelta(minutes=5)):
            raise ValueError('cost_history_epoch_window_invalid')
        if type(total) is not int or total <= 0 or not isinstance(deals, (list, tuple)) or len(deals) != total:
            raise ValueError('cost_history_count_mismatch')
        balance = _number(balance, positive=True)
        records, signed = {}, {}
        for deal in deals:
            row = {key: getattr(deal, key) for key in _FIELDS}
            for key in ('ticket', 'position_id', 'magic', 'entry', 'type', 'time_msc'):
                if type(row[key]) is not int or row[key] < 0:
                    raise ValueError('cost_history_invalid_identity')
            if row['ticket'] <= 0 or str(row['ticket']) in records:
                raise ValueError('cost_history_duplicate_ticket')
            if row['time_msc'] > end.timestamp() * 1000:
                raise ValueError('cost_history_future_deal')
            for key in _CASH:
                row[key] = _number(row[key])
            row['volume'] = _number(row['volume'])
            if row['type'] in (0, 1):
                if row['entry'] not in (0, 1, 3) or row['volume'] <= 0 or row['position_id'] <= 0:
                    raise ValueError('cost_history_invalid_volume')
                key = str(row['position_id'])
                signed[key] = signed.get(key, 0.) + row['volume'] * (1 if row['type'] == 0 else -1)
            records[str(row['ticket'])] = row
        cash = math.fsum(row[key] for row in records.values() for key in _CASH)
        if abs(cash - balance) > .02:
            raise ValueError('cost_history_balance_mismatch')
        if not isinstance(positions, (list, tuple)):
            raise ValueError('cost_history_exposure_unknown')
        live = {}
        for position in positions:
            if (type(position.identifier) is not int or position.identifier <= 0
                    or str(position.identifier) in live or type(position.type) is not int
                    or position.type not in (0, 1)):
                raise ValueError('cost_history_position_invalid')
            live[str(position.identifier)] = _number(position.volume, positive=True) * (1 if position.type == 0 else -1)
        if any(abs(signed.get(k, 0.) - live.get(k, 0.)) > 1e-8 for k in signed.keys() | live.keys()):
            raise ValueError('cost_history_position_mismatch')
        return records, cash, end

    @staticmethod
    def _incident(state, code, *, evidence, now, position_id=None, generation_id=None):
        identity = dict(code=code, position_id=position_id, generation_id=generation_id,
                        evidence_sha256=evidence)
        ident = _digest(identity)
        state['incidents'].setdefault(ident, dict(identity, incident_id=ident,
            first_observed_utc=now.isoformat(), resolution_references=[]))

    def audit_history(self, deals, *, total, history_start, history_end, balance, positions, now):
        """Audit every post-enrollment closed ledger, never a moving date slice.

        Input must be the existing sender's full reconciled epoch read. Ordering
        does not matter; unseen old-timestamp exits are still audited. Duplicate,
        missing, modified or incomplete records cannot advance the checkpoint.
        """
        now = _utc(now)
        state = self._load()
        if not state['generations']:
            raise ValueError('cost_generation_original_review_required')
        try:
            records, cash, end = self._history(deals, total=total, history_start=history_start,
                history_end=history_end, balance=balance, positions=positions, now=now)
        except (ValueError, AttributeError, TypeError, KeyError, OverflowError) as error:
            code = str(error) if type(error) is ValueError and str(error) in _HISTORY_CODES else 'cost_history_fields_missing'
            state['last_attempt'] = dict(status='BLOCKED', reason=code, observed_utc=now.isoformat())
            self._save(state, action='HISTORY_REFUSED', now=now, facts=dict(reason=code))
            return self._receipt(state)
        snapshot_sha = _digest(records)
        prior = state['checkpoint']
        if prior and end < _utc(prior['history_end_utc']):
            state['last_attempt'] = dict(status='BLOCKED', reason='cost_history_window_regressed', observed_utc=now.isoformat())
            self._save(state, action='HISTORY_REFUSED', now=now, facts=dict(reason='cost_history_window_regressed'))
            return self._receipt(state)
        for ticket, previous in state['deals'].items():
            if ticket not in records or records[ticket] != previous:
                self._incident(state, 'cost_history_changed_or_missing', evidence=snapshot_sha, now=now)
        # Keep original rows and append new immutable observations. Changed old
        # rows stay in their prior form; incident evidence retains current hash.
        for ticket, row in records.items():
            state['deals'].setdefault(ticket, row)
        owned = {row['position_id'] for row in records.values()
                 if row['entry'] == 0 and row['type'] in (0, 1) and row['magic'] == self.magic}
        scanned = []
        cutoff = _utc(state['legacy_cutoff_utc']).timestamp() * 1000
        for ident in sorted(owned):
            rows = sorted((r for r in records.values() if r['position_id'] == ident and r['type'] in (0, 1)),
                          key=lambda r: (r['time_msc'], r['ticket']))
            exits = [r for r in rows if r['entry'] in (1, 3)]
            if not exits or abs(sum(r['volume'] * (1 if r['type'] == 0 else -1) for r in rows)) > 1e-8:
                continue
            ledger_sha = _digest(rows)
            exit_ms = max(r['time_msc'] for r in exits)
            if exit_ms < cutoff:
                state['audits'][str(ident)] = dict(status='LEGACY_PRE_REVIEW_UNQUALIFIED',
                    ledger_sha256=ledger_sha, exit_tickets=[r['ticket'] for r in exits])
                continue
            binding = state['positions'].get(str(ident))
            if binding is None:
                self._incident(state, 'cost_position_generation_unbound', evidence=ledger_sha,
                               now=now, position_id=ident)
                continue
            generation_id = binding['generation_id']
            cost = deepcopy(state['generations'][generation_id]['policy'])
            opening_ms = min(r['time_msc'] for r in rows if r['entry'] == 0)
            # Audit-only arguments, not a rewritten policy/attestation. The native
            # cutoff must not suppress this already-proved applicable position.
            cost['reviewed_utc'] = datetime.fromtimestamp(min(opening_ms, exit_ms) / 1000, timezone.utc).isoformat()
            exit_at = datetime.fromtimestamp(exit_ms / 1000, timezone.utc)
            code = None
            try:
                validate_observed_costs(cost, [SimpleNamespace(**r) for r in rows], magic=self.magic, now=exit_at)
            except (ValueError, KeyError, TypeError, AttributeError, OverflowError) as error:
                code = str(error) if type(error) is ValueError and str(error) in {
                    'cost_broker_deal_drift', 'cost_swap_calendar_missing'} else 'cost_generation_evidence_invalid'
                self._incident(state, code, evidence=ledger_sha, now=now,
                               position_id=ident, generation_id=generation_id)
            audit = dict(status='BLOCKED' if code else 'AUDITED', generation_id=generation_id,
                ledger_sha256=ledger_sha, exit_tickets=[r['ticket'] for r in exits],
                cash={key: math.fsum(row[key] for row in rows) for key in _CASH})
            state['audits'][str(ident)] = audit
            scanned.append(dict(position_id=ident, **audit))
        checkpoint = dict(observed_utc=now.isoformat(), history_start_utc=_utc(history_start).isoformat(),
            history_end_utc=end.isoformat(), history_count=total, snapshot_sha256=snapshot_sha,
            cash_total=cash, balance=float(balance),
            audited_positions=sum(a['status'] == 'AUDITED' for a in state['audits'].values()),
            audited_exit_deals=sum(len(a['exit_tickets']) for a in state['audits'].values() if a['status'] == 'AUDITED'),
            legacy_pre_review_positions=sum(a['status'] == 'LEGACY_PRE_REVIEW_UNQUALIFIED' for a in state['audits'].values()))
        blocked = bool(state['incidents'])
        if not blocked:
            state['checkpoint'] = checkpoint
        state['last_attempt'] = dict(status='BLOCKED' if blocked else 'CLEAR',
            reason='unresolved_cost_incident' if blocked else 'all_applicable_closed_ledgers_audited', **checkpoint)
        self._save(state, action='HISTORY_AUDITED', now=now,
                   facts=dict(attempt=state['last_attempt'], audited_ledgers=scanned,
                              unresolved_incidents=list(state['incidents'])))
        return self._receipt(state)

    def record_resolution(self, incident_id, *, decision_sha256, now):
        """Record external review provenance; never clear or accept an incident."""
        now = _utc(now)
        state = self._load()
        if incident_id not in state['incidents'] or not _hex(decision_sha256):
            raise ValueError('cost_incident_resolution_reference_invalid')
        refs = state['incidents'][incident_id]['resolution_references']
        if any(item['decision_sha256'] == decision_sha256 for item in refs):
            return self._receipt(state)
        refs.append(dict(decision_sha256=decision_sha256, recorded_utc=now.isoformat(),
                         status='REVIEW_RECORDED_NOT_CLEARED'))
        self._save(state, action='RESOLUTION_REFERENCE', now=now,
                   facts=dict(incident_id=incident_id, resolution=refs[-1]))
        return self._receipt(state)

    def _receipt(self, state):
        attempt = state['last_attempt']
        result = dict(schema_version=1, account_fingerprint=self.fingerprint, magic=self.magic,
            status='BLOCKED' if state['incidents'] else attempt['status'] if attempt else 'UNVERIFIED',
            execution_authorized=False, legacy_cutoff_utc=state['legacy_cutoff_utc'],
            original_review_sha256=state['original_review_sha256'],
            generation_ids=sorted(state['generations']), checkpoint=deepcopy(state['checkpoint']),
            latest_attempt=deepcopy(attempt), unresolved_incidents=deepcopy(list(state['incidents'].values())))
        result['receipt_sha256'] = _digest(result)
        return result

    def status(self):
        return self._receipt(self._load())
