"""Fixed-lot B1 controls on actual quotes; never a Hybrid execution certificate."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .b1_final import normalize_price, reference_bars


def run(times, bid, ask, frame, broker, *, cap, guards, scenario):
    balance = peak = 200.0
    max_dd = 0.0
    busy = -1
    halted = False
    rows = []
    rejected = {'busy': 0, 'halt': 0, 'day_loss': 0, 'quota': 0, 'tick_gap': 0}
    day_starts, quotas = {}, {}
    contract, lot = broker['trade_contract_size'], 0.01
    assert broker['volume_min'] <= lot <= broker['volume_max']
    assert np.isclose(lot / broker['volume_step'], round(lot / broker['volume_step']))
    for i in np.flatnonzero(frame.direction.to_numpy()):
        when = frame.index[i] + pd.Timedelta(minutes=15)
        j = int(np.searchsorted(times, when.value // 10**6))
        if j >= len(times) or times[j] - when.value // 10**6 >= 900000:
            rejected['tick_gap'] += 1
            continue
        if j <= busy:
            rejected['busy'] += 1
            continue
        if halted or balance <= 0:
            rejected['halt'] += 1
            continue
        day = int(times[j] // 86400000)
        day_starts.setdefault(day, balance)
        if guards and balance <= day_starts[day] * .85:
            rejected['day_loss'] += 1
            continue
        if guards and quotas.get(day, 0) >= 2:
            rejected['quota'] += 1
            continue
        direction = int(frame.direction.iloc[i])
        entry = float(ask[j] if direction == 1 else bid[j])
        stop = normalize_price(entry - direction * float(frame.atr.iloc[i]) * 2.5,
                               broker['trade_tick_size'])
        distance = abs(entry - stop)
        target = normalize_price(entry + direction * distance * 2.5, broker['trade_tick_size'])
        risk = distance * contract * lot
        fee = .1 * risk if scenario else 0.0
        budget = min(balance * .15, 30.0) if guards else 30.0
        quotes = bid if direction == 1 else ask
        start_day = pd.Timestamp(int(times[j]), unit='ms', tz='UTC').normalize()
        rolls = pd.date_range(start_day + pd.Timedelta(days=1),
                              pd.Timestamp(int(times[-1]), unit='ms', tz='UTC').normalize(), freq='D')
        weights = np.array([3 if d.dayofweek + 1 == broker['swap_rollover3days'] else 1 for d in rolls])
        roll_ms = np.array([d.value // 10**6 for d in rolls], dtype=np.int64)
        accrued = np.r_[0, np.cumsum(weights)]
        swap_unit = (broker['swap_long'] if direction == 1 else broker['swap_short']) * broker['point'] * contract * lot
        if not scenario or broker['swap_mode'] != 1:
            swap_unit = 0.0
        quotas[day] = quotas.get(day, 0) + 1
        reason = 'END_OF_SAMPLE'
        for left in range(j, len(times), 100000):
            right = min(left + 100000, len(times))
            q, ts = quotes[left:right], times[left:right]
            swaps = accrued[np.searchsorted(roll_ms, ts, side='right')] * swap_unit
            pnl = direction * (q - entry) * contract * lot + swaps - fee
            marks = balance + pnl
            peaks = np.maximum.accumulate(np.r_[peak, marks])[1:]
            sl = direction * (q - stop) <= 0
            tp = direction * (q - target) >= 0
            loss_cap = pnl <= -budget if cap else np.zeros(len(q), dtype=bool)
            hwm = marks <= peaks * .8 if guards else np.zeros(len(q), dtype=bool)
            depleted = marks <= 0
            hits = np.flatnonzero(sl | tp | loss_cap | hwm | depleted)
            count = int(hits[0]) + 1 if len(hits) else len(q)
            used_marks, used_ts = marks[:count].copy(), ts[:count]
            k = left + count - 1
            closed = bool(len(hits)) or right == len(times)
            if closed:
                n = count - 1
                reason = ('EQUITY_DEPLETED' if depleted[n] else 'HWM_HALT' if hwm[n]
                          else 'BASKET_SL' if loss_cap[n] else 'SL' if sl[n]
                          else 'TP' if tp[n] else 'END_OF_SAMPLE')
                exit_price = target if reason == 'TP' else float(q[n])
                swap = float(swaps[n])
                net = direction * (exit_price - entry) * contract * lot + swap - fee
                used_marks[-1] = balance + net
            used_peaks = np.maximum.accumulate(np.r_[peak, used_marks])[1:]
            max_dd = max(max_dd, float(np.max((used_peaks - used_marks) / used_peaks)))
            peak = max(peak, float(used_marks.max()))
            days = used_ts // 86400000
            firsts = np.r_[0, np.flatnonzero(np.diff(days)) + 1]
            for n in firsts:
                day_starts.setdefault(int(days[n]), float(used_marks[n]))
            if closed:
                break
        balance += net
        busy = k
        halted = guards and (reason == 'HWM_HALT' or balance <= peak * .8)
        rows.append(dict(signal_time=str(when), entry_time=str(pd.Timestamp(int(times[j]), unit='ms', tz='UTC')),
                         exit_time=str(pd.Timestamp(int(times[k]), unit='ms', tz='UTC')), direction=direction,
                         entry=entry, exit=exit_price, stop=stop, target=target, volume=lot,
                         risk_money=risk, basket_budget=budget if cap else None,
                         swap_scenario=swap, extra_cost_scenario=fee, net=net, balance=balance,
                         reason=reason, cumulative_tick_dd_pct=max_dd * 100))
    log = pd.DataFrame(rows)
    np.testing.assert_allclose(200.0 + log.net.cumsum(), log.balance, atol=1e-7)
    loss = -log.loc[log.net < 0, 'net'].sum()
    return log, dict(final_balance=balance, return_pct=(balance / 200 - 1) * 100,
                     trades=len(log), win_rate=float((log.net > 0).mean()),
                     pf=float(log.loc[log.net > 0, 'net'].sum() / loss) if loss else None,
                     max_tick_equity_dd_pct=max_dd * 100, halted=halted, rejections=rejected)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    baseline = json.loads((args.baseline / 'result.json').read_text())
    assert (args.baseline / 'COMPLETE').exists()
    capture = Path(baseline['capture'])
    assert hashlib.sha256((capture / 'manifest.json').read_bytes()).hexdigest() == baseline['capture_manifest_sha256']
    meta = json.loads((capture / 'manifest.json').read_text())
    t, b, a = [np.load(args.baseline / 'tape' / f'{k}.npy', mmap_mode='r') for k in ('time', 'bid', 'ask')]
    offset = 0
    for day in meta['days']:
        path = capture / (day['day'] + '.npz')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == day['sha256']
        with np.load(path) as z:
            n = day['ticks']
            for tape, key in ((t, 'time_msc'), (b, 'bid'), (a, 'ask')):
                np.testing.assert_array_equal(tape[offset:offset+n], z[key])
            offset += n
    assert offset == len(t)
    raw = pd.read_csv(args.baseline / 'reference_bars.csv')
    raw.index = pd.DatetimeIndex(pd.to_datetime(raw.pop('bar_open_utc'), utc=True))
    frame = reference_bars(raw)
    start, end = pd.Timestamp('2026-05-14', tz='UTC'), pd.Timestamp('2026-09-26', tz='UTC')
    available = frame.index + pd.Timedelta(minutes=15)
    frame.loc[~((available >= start) & (available < end)), 'direction'] = 0
    left, right = np.searchsorted(t, [start.value // 10**6, end.value // 10**6])
    rows = []
    contract = {'capital': 200, 'lot': .01, 'sl_atr': 2.5, 'tp_r': 2.5,
                'arms': ['PURE_FIXED', 'TICK_CAP30_ONLY', 'TICK_CAP_WITH_GUARDS'],
                'costs': ['observed_spread_only', 'archival_swap_plus_0.10R_scenario'],
                'recovery': False, 'production_parity': False,
                'limitations': ['Unmeasured historical margin/stop-out/commission/slippage',
                                'Ideal quote execution, not broker-approved fills',
                                'Previously exposed history; diagnostic controls, not selection',
                                'Fixed-lot exposure declared explicitly, not original 1% sizing',
                                'Daily guards apply to new entries; no external account activity'],
                'baseline': str(args.baseline), 'capture_manifest_sha256': baseline['capture_manifest_sha256'],
                'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (args.output / 'contract.json').write_text(json.dumps(contract, indent=2))
    for scenario in (False, True):
        for name, cap, guards in (('PURE_FIXED', False, False), ('TICK_CAP30_ONLY', True, False),
                                   ('TICK_CAP_WITH_GUARDS', True, True)):
            log, stats = run(t[left:right], b[left:right], a[left:right], frame, baseline['broker_snapshot'],
                             cap=cap, guards=guards, scenario=scenario)
            label = 'archival_cost_scenario' if scenario else 'observed_spread_only'
            log.to_csv(args.output / f'{name}_{label}.csv', index=False)
            rows.append(dict(arm=name, cost=label, **stats))
            print(json.dumps(rows[-1]), flush=True)
    (args.output / 'results.json').write_text(json.dumps(rows, indent=2))
    (args.output / 'COMPLETE').write_text('Diagnostic controls only; no recovery or live certification.\n')


if __name__ == '__main__':
    main()
