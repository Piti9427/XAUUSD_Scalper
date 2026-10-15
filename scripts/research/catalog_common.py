"""Shared frozen catalog rule constructor."""

from dataclasses import asdict
from .breakout_models import Rules


def rules(guard, target, protection, activation):
    return asdict(
        Rules(
            entry_guard=guard,
            daily_loss_limit=0.2,
            target_atr=target,
            protect_mode=protection,
            protect_after_r=activation,
        )
    )
