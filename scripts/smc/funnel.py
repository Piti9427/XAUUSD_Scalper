"""Setup funnel counters for foundation research reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


FUNNEL_STAGES = (
    "detected",
    "structure_qualified",
    "target_qualified",
    "affordable",
    "risk_admitted",
    "submitted",
    "broker_accepted",
    "filled",
    "closed",
)


@dataclass
class SetupFunnel:
    counts: Dict[str, int] = field(
        default_factory=lambda: {stage: 0 for stage in FUNNEL_STAGES}
    )
    reject_reasons: Dict[str, int] = field(default_factory=dict)

    def bump(self, stage: str, n: int = 1) -> None:
        if stage not in self.counts:
            raise ValueError(f"unknown funnel stage: {stage}")
        self.counts[stage] += n

    def reject(self, reason: str) -> None:
        key = reason or "unknown"
        self.reject_reasons[key] = self.reject_reasons.get(key, 0) + 1

    def as_dict(self) -> Dict[str, object]:
        return {
            "counts": dict(self.counts),
            "reject_reasons": dict(self.reject_reasons),
        }
