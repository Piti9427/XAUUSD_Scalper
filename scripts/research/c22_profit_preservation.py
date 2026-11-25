"""Offline native replay adapter with explicit account carry; never sends orders.

Compile guarded source insertions instead of maintaining another copy of the
native event loop. An upstream source change fails closed at the changed anchor.
"""

from copy import deepcopy
from dataclasses import asdict, replace
from decimal import Decimal
import inspect
import math

import pandas as pd

from . import breakout_replay as native


def passes(candidate, baseline):
    """Require every matched cell to preserve net/DD, and some strict net gain."""
    if not candidate or candidate.keys() != baseline.keys():
        return False
    improved = False
    for key, reference in baseline.items():
        cell = candidate[key]
        if not all(math.isfinite(row[metric]) for row in (cell, reference)
                   for metric in ('net', 'dd')):
            return False
        if cell['net'] < reference['net'] - 1e-8 or cell['dd'] > reference['dd'] + 1e-8:
            return False
        improved |= cell['net'] > reference['net'] + 1e-8
    return improved


def select(cells, training_segments):
    """Train-only maximin profit ranking, lexical tie-break, native fallback."""
    keys = [(g, v) for g in training_segments for v in ('base', 'stress')]
    baseline = {k: cells['native'][k] for k in keys}
    ranked = []
    for name, rows in cells.items():
        candidate = {k: rows[k] for k in keys}
        if name != 'native' and passes(candidate, baseline):
            score = min(sum(rows[(g, v)]['net'] - cells['native'][(g, v)]['net']
                            for g in training_segments) for v in ('base', 'stress'))
            ranked.append((-score, name))
    return min(ranked)[1] if ranked else 'native'


def replay(frame, ticks, broker, rules, costs, *, start, end, swap_policy,
           state=None, finalize=True, buy_be=None, gate=None, gate_name="native",
           capture_events=True, buy_be_max_risk_pct=None,
           buy_swap_be_fraction=0.0, buy_swap_be_min_cost_r=0.0, buy_target_rr=None,
           sell_target_rr=None, min_sell_target_risk_usd=None,
           conditional_sell_protect_after_r=None, entry_recipe_id=None, entry_guard=None,
           min_buy_target_risk_pct=None, buy_stop_atr=None, sell_stop_atr=None):
    """Run native $200 account, optionally continuing a previous chunk.

    buy_be is an optional (trigger_R, poll_seconds) BUY-only research hypothesis.
    buy_be_max_risk_pct optionally limits that hypothesis to entry-time risk_pct;
    it does not disable native bar-close protection or alter sizing/admission.
    buy_swap_be_fraction covers part of known accrued debit at native BUY BE;
    buy_swap_be_min_cost_r may require accrued debit / initial risk above a floor.
    buy_target_rr optionally selects an existing Rules BUY target profile only.
    sell_target_rr selects an existing SELL profile; native BUY target is retained.
    min_sell_target_risk_usd can apply that SELL target only above original SL risk.
    conditional_sell_protect_after_r couples a BE threshold to that same risk band.
    entry_recipe_id binds a prepared signal recipe across account chunks.
    entry_guard selects an existing completed-bar admission guard in Rules.
    min_buy_target_risk_pct can shorten BUY reward only near the unchanged risk cap.
    Side-specific stop widths use owner-authorized 1.5/2/2.5ATR profiles before admission.
    gate(row, quote_ms, balance, closed_ledger) may return a suppression reason.
    Only legacy holding mode is supported because other modes store tick indices.
    Supply the full prepared frame at every chunk to preserve prior-day context.
    """
    if swap_policy is None:
        raise ValueError("swap metadata is mandatory")
    if entry_recipe_id is not None and (not isinstance(entry_recipe_id, str) or not entry_recipe_id):
        raise ValueError("invalid entry recipe identity")
    if any(width not in (None, 1.5, 2.0, 2.5) for width in (buy_stop_atr, sell_stop_atr)):
        raise ValueError("unsupported research stop width")
    if buy_stop_atr is not None:
        rules = replace(rules, buy_stop_atr=buy_stop_atr)
    if sell_stop_atr is not None:
        rules = replace(rules, stop_atr=sell_stop_atr,
                        buy_stop_atr=rules.buy_stop_atr if rules.buy_stop_atr is not None else rules.stop_atr)
    if min_buy_target_risk_pct is not None and (
        buy_target_rr is None or not math.isfinite(min_buy_target_risk_pct)
        or not 0 <= min_buy_target_risk_pct <= 10
    ):
        raise ValueError("invalid conditional BUY target risk floor")
    if buy_target_rr is not None:
        proposed_buy = replace(rules, buy_target_rr=buy_target_rr)
        if min_buy_target_risk_pct is None:
            rules = proposed_buy
    if entry_guard is not None:
        rules = replace(rules, entry_guard=entry_guard)
    if min_sell_target_risk_usd is not None and (
        sell_target_rr is None or not math.isfinite(min_sell_target_risk_usd)
        or min_sell_target_risk_usd < 0
    ):
        raise ValueError("invalid conditional SELL target risk floor")
    if sell_target_rr is not None:
        candidate_rules = replace(rules, target_rr=sell_target_rr)
        if min_sell_target_risk_usd is None:
            rules = candidate_rules
    if conditional_sell_protect_after_r is not None:
        if sell_target_rr is None or min_sell_target_risk_usd is None:
            raise ValueError("coupled SELL protection requires a conditional target")
        replace(rules, protect_after_r=conditional_sell_protect_after_r)
    if rules.holding_mode != "legacy":
        raise ValueError("state carry supports legacy holding only")
    if buy_be is not None and (
        len(buy_be) != 2 or not all(math.isfinite(v) and v > 0 for v in buy_be)
    ):
        raise ValueError("invalid BUY BE hypothesis")
    if buy_be_max_risk_pct is not None and (
        buy_be is None or not math.isfinite(buy_be_max_risk_pct)
        or not 0 < buy_be_max_risk_pct <= 10
    ):
        raise ValueError("invalid BUY BE entry-risk limit")
    if (not math.isfinite(buy_swap_be_fraction) or not 0 <= buy_swap_be_fraction <= 1
            or not math.isfinite(buy_swap_be_min_cost_r) or buy_swap_be_min_cost_r < 0):
        raise ValueError("invalid accrued-swap BE hypothesis")
    if (rules.risk_cap != 0.1 or rules.buy_risk_cap not in (None, 0.1)
            or rules.sizing_mode != "fixed" or rules.buy_sizing_mode not in (None, "fixed")):
        raise ValueError("fixed 0.01 and 10% cap required")
    binding = dict(broker=broker, rules=asdict(rules), costs=asdict(costs),
                   swap=asdict(swap_policy), buy_be=buy_be, gate_name=gate_name,
                   buy_be_max_risk_pct=buy_be_max_risk_pct,
                   buy_swap_be_fraction=buy_swap_be_fraction,
                   buy_swap_be_min_cost_r=buy_swap_be_min_cost_r,
                   sell_target_rr=sell_target_rr,
                   min_sell_target_risk_usd=min_sell_target_risk_usd,
                   conditional_sell_protect_after_r=conditional_sell_protect_after_r,
                   entry_recipe_id=entry_recipe_id, buy_target_rr=buy_target_rr,
                   min_buy_target_risk_pct=min_buy_target_risk_pct)
    state = deepcopy(state)
    if state is not None:
        if state['end_utc'] != start.isoformat() or state['binding'] != binding:
            raise ValueError("non-contiguous window or changed account contract")
    options = dict(state=state, finalize=finalize, buy_be=buy_be, gate=gate,
                   buy_be_max_risk_pct=buy_be_max_risk_pct,
                   buy_swap_be_fraction=buy_swap_be_fraction,
                   buy_swap_be_min_cost_r=buy_swap_be_min_cost_r,
                   sell_target_rr=sell_target_rr,
                   min_sell_target_risk_usd=min_sell_target_risk_usd,
                   conditional_sell_protect_after_r=conditional_sell_protect_after_r,
                   buy_target_rr=buy_target_rr, min_buy_target_risk_pct=min_buy_target_risk_pct)
    source = inspect.getsource(native.replay)

    def insert(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError("native replay source anchor changed: " + old[:70])
        source = source.replace(old, new)

    insert('    balance = peak = 200.0\n', '''    balance = peak = 200.0
    if _options['state'] is not None:
        balance = _options['state']['balance']
        peak = _options['state']['peak']
''')
    insert('    signal_count = 0\n', '''    signal_count = 0
    if _options['state'] is not None:
        _s = _options['state']
        position = _s['position']
        max_dd = _s['max_dd']
        day_start = _s['day_start']
        daily_losses = _s['daily_losses']
        cooldown_until_ms = _s['cooldown_until_ms']
        flat_since = _s['flat_since']
        reset_range = _s['reset_range']
''')
    insert('    swap_schedule = swap_policy.schedule(start, end) if swap_policy is not None else None\n',
           '''    _born = start
    if _options['state'] is not None and _options['state']['position'] is not None:
        _born = min(start, pd.Timestamp(_options['state']['position']['entry_time_utc']))
    swap_schedule = swap_policy.schedule(_born, end)
''')
    insert('    if position is not None:\n        close(len(times) - 1, "END_OF_SAMPLE")\n',
           '    if position is not None and _options["finalize"]:\n        close(len(times) - 1, "END_OF_SAMPLE")\n')
    insert('        rejected[reason] += 1\n',
           '        rejected[reason] = rejected.get(reason, 0) + 1\n')
    insert('        target = plan.target\n', '''        target = plan.target
        if (direction == 1 and _options['min_buy_target_risk_pct'] is not None
                and plan.risk / balance * 100 >= _options['min_buy_target_risk_pct']):
            target = _level(entry + abs(entry - stop) * _options['buy_target_rr'],
                            broker['trade_tick_size'], 1)
        if (direction == -1 and _options['min_sell_target_risk_usd'] is not None
                and plan.risk >= _options['min_sell_target_risk_usd']):
            target = _level(entry - abs(entry - stop) * _options['sell_target_rr'],
                            broker['trade_tick_size'], -1)
''')
    insert('            if net_now >= rules.protect_after_r * p["risk_usd"]:\n', '''            _trigger_r = rules.protect_after_r
            if (p['direction'] == -1 and _options['conditional_sell_protect_after_r'] is not None
                    and p['risk_usd'] >= _options['min_sell_target_risk_usd']):
                _trigger_r = _options['conditional_sell_protect_after_r']
            if net_now >= _trigger_r * p['risk_usd']:
''')
    insert('        day = int(times[index] // 86400000)\n', '''        if _options['gate'] is not None:
            _history = [] if _options['state'] is None else _options['state']['gate_history']
            _why = _options['gate'](row, int(times[index]), balance, _history + ledger)
            if _why:
                reject(_why, direction, int(times[index]))
                continue
        day = int(times[index] // 86400000)
''')
    insert('            used = int(hits[0]) + 1 if len(hits) else len(pnl)\n', '''            used = int(hits[0]) + 1 if len(hits) else len(pnl)
            _activation = None
            _be = _options['buy_be']
            if (_be is not None and p['direction'] == 1
                    and not p['protection_active']
                    and (_options['buy_be_max_risk_pct'] is None
                         or p['risk_pct'] <= _options['buy_be_max_risk_pct'])
                    and (rules.buy_protect_mode or rules.protect_mode) != 'off'):
                _fee = costs.commission_per_lot * p['volume']
                _net = (quote - p['entry']) * factor - _fee - costs.slippage * factor
                _bucket = int(_be[1] * 1000)
                if _bucket < 1:
                    raise ValueError('poll interval below one millisecond')
                _prior = (times[cursor - 1] if cursor else
                          _options['state']['last_tick_ms'] if _options['state'] is not None
                          else p['entry_ms'])
                _poll = np.diff(np.r_[_prior // _bucket, times[cursor:stop] // _bucket]) > 0
                _ok = np.flatnonzero((_net >= _be[0] * p['risk_usd']) & _poll
                                     & (times[cursor:stop] > p['entry_ms']))
                if len(_ok) and (not len(hits) or _ok[0] < hits[0]):
                    _activation = int(_ok[0])
                    used = _activation + 1
                    hits = hits[:0]
''')
    insert('            cursor += used\n', '''            cursor += used
            if _activation is not None:
                _level_be = _level(p['entry'] + _fee / factor + costs.slippage,
                                   broker['trade_tick_size'], -1)
                if _level_be > p['stop'] and quote[used - 1] > _level_be:
                    p['stop'] = _level_be
                    p['stop_updates'] += 1
                    p['protection_active'] = True
''')
    insert('                candidate = break_even\n', '''                candidate = break_even
                if p['direction'] == 1 and _options['buy_swap_be_fraction']:
                    _debit = max(0.0, -float(swap_at(p, times[index])))
                    if (_debit > 0 and
                            _debit >= _options['buy_swap_be_min_cost_r'] * p['risk_usd']):
                        _amount = (Decimal(str(fee)) + Decimal(str(_debit))
                                   * Decimal(str(_options['buy_swap_be_fraction'])))
                        _price = (Decimal(str(p['entry'])) + Decimal(str(costs.slippage))
                                  + _amount / Decimal(str(factor)))
                        candidate = max(break_even, _level(
                            float(_price),
                            broker['trade_tick_size'], -1))
                        if executable <= candidate:
                            candidate = break_even
''')
    insert('    return result\n', '''    result['carry_state'] = dict(
        end_utc=end.isoformat(), binding=_binding, balance=balance, peak=peak,
        max_dd=max_dd, position=position, day_start=day_start,
        daily_losses=daily_losses, cooldown_until_ms=cooldown_until_ms,
        flat_since=flat_since, reset_range=reset_range, last_tick_ms=int(times[-1]),
        gate_history=([] if _options['state'] is None else _options['state']['gate_history']) + ledger)
    return result
''')
    scope = dict(native.__dict__, _options=options, _binding=deepcopy(binding), Decimal=Decimal)
    exec(compile(source, '<c22-profit-preservation>', 'exec'), scope)
    return scope['replay'](frame, ticks, broker, rules, costs, start=start, end=end,
                           swap_policy=swap_policy, capture_events=capture_events)
