"""Selected C22 hooks reuse shared broker-confirmed Demo execution lifecycle."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path

from scripts.c22_selected.strategy import CONFIG_PATH, MAGIC, SelectedStrategy
from scripts.demo_runtime.admission import Admission
from scripts.demo_runtime.broker import _cash
from scripts.demo_runtime.runner import DemoRunner


class SelectedAdmission(Admission):
    """Apply elapsed-time cooldown at the existing first-quote admission seam."""

    def __init__(self, context):
        super().__init__(context)
        self._candidate_deals = None

    def admit(self, account, positions, orders, deals, info, tick, bars, now):
        self._candidate_deals = deals
        try:
            return super().admit(account, positions, orders, deals, info, tick, bars, now)
        finally:
            self._candidate_deals = None

    def _first_quote(self, closed, now):
        first = super()._first_quote(closed, now)
        ctx = self.context
        deals = self._candidate_deals
        if deals is None:
            # The shared lifecycle also asks for the first closed-bar quote
            # when managing BE. A new-entry cooldown must not block protection.
            if ctx.journal.get("active") is not None:
                return first
            raise ValueError("cooldown_history_missing")
        owned = {
            int(d.position_id) for d in deals
            if int(d.entry) == 0 and int(d.type) in (0, 1)
            and int(d.magic) == MAGIC and str(d.comment).startswith(ctx.strategy.prefix)
        }
        last_loss = 0
        for ident in owned:
            ledger = [d for d in deals if int(d.position_id) == ident and int(d.type) in (0, 1)]
            exits = [d for d in ledger if int(d.entry) in (1, 3)]
            volume = sum(float(d.volume) * (1 if int(d.type) == 0 else -1) for d in ledger)
            if exits and abs(volume) < 1e-8 and sum(_cash(d) for d in ledger) < 0:
                last_loss = max(last_loss, max(int(d.time_msc) for d in exits))
        recorded = ctx.journal.get("selected_last_loss_ms") or 0
        if last_loss < recorded:
            raise ValueError("cooldown_history_drift")
        if last_loss:
            ctx.journal.put("selected_last_loss_ms", last_loss)
        cooldown_ms = ctx.strategy.cooldown_bars * 15 * 60 * 1000
        if last_loss and int(first.time_msc) < last_loss + cooldown_ms:
            ctx.journal.put("last_bar", closed.isoformat())
            raise ValueError("cooldown")
        return first


class SelectedDemoRunner(DemoRunner):
    def __init__(self, *, config=None, cache_output=None, **kwargs):
        config = json.loads(CONFIG_PATH.read_text()) if config is None else config
        self.cache_output = cache_output
        super().__init__(strategy=SelectedStrategy(config), **kwargs)
        self._admission = SelectedAdmission(self)
        # Shared release hashing predates this adapter. Include every new module
        # so two adapter versions cannot share a forward cohort accidentally.
        digest = hashlib.sha256(self.release_hash.encode())
        for path in sorted(Path(__file__).parent.glob("*.py")):
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
        self.release_hash = digest.hexdigest()
        self.journal.audit_context["release_hash"] = self.release_hash
        self.cohort_id = self.release_hash + ":" + self.journal.audit_context["config_hash"]

    def export_cache(self, path):
        """Persist the exact completed causal prefix, not a bootstrap count claim."""
        bars = self.strategy.cache.bars
        if bars is None:
            return
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        bars.to_csv(temporary, index_label="bar_open_utc")
        temporary.replace(path)

    def cycle(self, *, now):
        result = super().cycle(now=now)
        result["research_rules_id"] = self.strategy.config["contract_id"]
        result["cooldown_minutes"] = int(timedelta(minutes=15 * self.strategy.cooldown_bars).total_seconds() / 60)
        if self.cache_output is not None:
            self.export_cache(self.cache_output)
        return result
