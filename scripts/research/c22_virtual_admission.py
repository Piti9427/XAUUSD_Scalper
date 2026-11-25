"""Research-only native virtual-book veto; never a sender or sizing override."""
import hashlib
import json
import operator
from datetime import timedelta

import pandas as pd


def _decision(event):
    stamp = pd.Timestamp(event['time_utc'])
    if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0) or stamp.value % 10**6:
        raise ValueError('virtual decision requires an aware UTC millisecond timestamp')
    if isinstance(event['direction'], bool):
        raise ValueError('invalid virtual decision direction')
    try:
        direction = operator.index(event['direction'])
    except TypeError as exc:
        raise ValueError('invalid virtual decision direction') from exc
    reason = event['reason']
    if direction not in (-1, 1) or not isinstance(reason, str) or not reason:
        raise ValueError('invalid virtual decision')
    return (stamp.value // 10**6, direction), reason


class NativeAdmissionVeto:
    """Exact current-time lookup, with no access to trade outcomes.

    A replay may precompute the native decisions only after prefix-invariance
    validation. The checksum is evidence provenance; the gate never uses it to
    decide an entry. Candidate replay still performs its own admission checks.
    """

    def __init__(self, events):
        decisions: dict[tuple[int, int], str] = {}
        for event in events:
            key, reason = _decision(event)
            if key in decisions and decisions[key] != reason:
                raise ValueError('conflicting virtual decisions')
            decisions[key] = reason
        self._decisions = decisions
        self._admitted = frozenset(key for key, reason in decisions.items() if reason == 'admitted')
        clean = [(ms, direction, reason) for (ms, direction), reason in sorted(decisions.items())]
        self.evidence_sha256 = hashlib.sha256(json.dumps(clean).encode()).hexdigest()

    def __call__(self, row, quote_ms, _balance, _ledger):
        key = (operator.index(quote_ms), int(row.direction))
        if key in self._admitted:
            return None
        return 'shadow_native_' + self._decisions.get(key, 'not_admitted')


def effective_summary(actual, virtual, initial=200):
    """Keep books separate and prevent virtual vetoes hiding cap unavailability.

    The existing observed-span proxy is bounded below by each book's own proxy
    without reordering either event stream. This can strengthen, never relax, native
    continuous duration acceptance. It does not prove uninterrupted inability.
    """
    from scripts.research.c22_profit_preservation_campaign import summary

    result = summary(actual, initial)
    reference = summary(virtual, initial)
    own_span = result['cap_rejection_span_days']
    virtual_span = reference['cap_rejection_span_days']
    result.update(actual_cap_rejection_span_days=own_span,
                  virtual_cap_rejection_span_days=virtual_span,
                  cap_rejection_span_days=max(own_span, virtual_span),
                  cap_span_note='max actual and required virtual observed cap spans; not continuous lock proof',
                  virtual_rejections=dict(virtual['rejections']),
                  virtual_final_balance=reference['final_balance'])
    return result
