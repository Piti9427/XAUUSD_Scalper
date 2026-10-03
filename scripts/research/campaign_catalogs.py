"""Frozen catalog dispatcher; recursive seeds use same public contract API."""

from .catalog_m5 import build as m5
from .catalog_annual import build as annual
from .catalog_parent import build as parent
from .catalog_hybrid import build as hybrid
from .catalog_basic import build as basic


_BUILDERS = {
    "annual_m5_atr_reward": m5,
    "annual_m5_directional_sizing": m5,
    "annual_m5_hybrid_quality": m5,
    "annual_m5_hybrid": m5,
    "annual_m5_intraday": m5,
    "annual_m5_bounded24": m5,
    "annual_short_buy": annual,
    "annual_sizing": annual,
    "annual_fast_quality": annual,
    "annual_short_sell": annual,
    "annual_directional": annual,
    "annual_directional_trend": annual,
    "annual_directional_circuit": annual,
    "annual_directional_fine": annual,
    "annual_sessions": annual,
    "annual_hybrid_unpaused": annual,
    "annual_risk": annual,
    "annual_confirmation": annual,
    "annual_bidirectional": annual,
    "hybrid_parent_invalidation": parent,
    "hybrid_parent_protection": parent,
    "hybrid_parent_atr": parent,
    "hybrid_parent_risk": parent,
    "hybrid_parent_reward_fine": parent,
    "hybrid_parent_reward_pause": parent,
    "hybrid_parent_quality": parent,
    "hybrid_parent_trend": parent,
    "hybrid_parent_horizon": parent,
    "hybrid_atr_stop": hybrid,
    "hybrid_reward_geometry": hybrid,
    "hybrid_reward_quality": hybrid,
    "hybrid_reward_admission": hybrid,
    "hybrid_reward_session": hybrid,
    "hybrid_reward": hybrid,
    "hybrid_invalidation": hybrid,
    "hybrid_admission": hybrid,
    "hybrid_oscillator": hybrid,
    "oscillator": basic,
    "compression": basic,
    "horizon_quality": basic,
    "horizons": basic,
    "admission": basic,
    "tuning": basic,
    "symmetric": basic,
    "buy_setups": basic,
    "quality": basic,
}


def contracts(catalog="quality"):
    try:
        builder = _BUILDERS[catalog]
    except KeyError:
        raise ValueError("unknown catalog") from None
    return builder(catalog, contracts)
