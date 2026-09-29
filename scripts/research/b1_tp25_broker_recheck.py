"""Replay B1_TP25 on verified broker quotes at $200, without invented prices."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .b1_d_comprehensive import load_capture, summarize, write_log
from .b1_d_ticks import replay
from .b1_final import RiskState, normalize_price, reference_bars
from .strategies import Spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    tape = args.output / 'tape'
    tape.mkdir()
    meta, times, bid, ask, bars = load_capture(args.capture, tape)
    frame = reference_bars(bars[['open', 'high', 'low', 'close']])
    for n in (150, 1000, len(frame) // 2):
        pd.testing.assert_frame_equal(frame.iloc[:n], reference_bars(bars.iloc[:n]))
    frame.to_csv(args.output / 'reference_bars.csv', index_label='bar_open_utc')
    start = pd.Timestamp('2026-05-14', tz='UTC')
    end = pd.Timestamp('2026-09-26', tz='UTC')
    available = frame.index + pd.Timedelta(minutes=15)
    signal = frame[['direction']].copy()
    signal.loc[~((available >= start) & (available < end)), 'direction'] = 0
    left, right = np.searchsorted(times, [start.value // 10**6, end.value // 10**6])
    # Actual Bid/Ask spread is included. Unknown historical charges are excluded,
    # not represented as measured zero charges or estimated current-spec swap.
    broker = dict(meta['symbol_spec'], swap_mode=0)
    decisions = []
    log, stats = replay(
        times[left:right], bid[left:right], ask[left:right], frame, signal,
        Spec('B1_TP25', 'donchian', lookback=30, filters=('rsi',), sl=2.5, tp=2.5),
        broker, 200.0, extra_cost_r=0.0, risk_state=RiskState(200.0),
        price_normalizer=normalize_price, entry_window_ms=900000,
        decision_log=decisions,
    )
    write_log(args.output / 'trades.csv', log)
    if not log.empty:
        np.testing.assert_allclose(200.0 + log.net.cumsum(), log.balance, atol=1e-7)
    pd.DataFrame(decisions).to_csv(args.output / 'decisions.csv', index=False)
    result = {
        'strategy': 'B1_TP25', 'initial_equity': 200.0,
        'return_pct_before_unmeasured_costs': (stats['final_balance'] / 200.0 - 1) * 100,
        **summarize(log, stats),
    }
    sources = [Path(__file__), Path('scripts/research/b1_d_ticks.py'),
               Path('scripts/research/b1_final.py'), Path('scripts/research/strategies.py'),
               Path('scripts/research/b1_d_comprehensive.py'), Path('scripts/research/data.py')]
    manifest = {
        'capture': str(args.capture), 'symbol': meta['symbol'],
        'capture_manifest_sha256': hashlib.sha256((args.capture / 'manifest.json').read_bytes()).hexdigest(),
        'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        'scoring_start_utc': str(start), 'scoring_end_exclusive_utc': str(end),
        'captured_ticks': len(times), 'scoring_ticks': int(right - left),
        'signal_count': int((signal.direction != 0).sum()),
        'risk_policy': 'B1 drawdown tiers: 1%, 0.75%, 0.5%, 0.25%; 12% entry halt',
        'sizing': 'Floor broker lot step; reject below minimum lot; no rounding up',
        'costs': 'Observed Bid/Ask spread only; commission, swap and slippage excluded as unmeasured',
        'broker_snapshot': meta['symbol_spec'],
        'limitations': ['Previously exposed history, not unseen validation',
                        'Python replay, not MT5 Strategy Tester or execution certification',
                        'No historical margin or stop-out reconstruction',
                        'Single position; no fixed-lot recovery basket'],
        'prefix_checks_passed': 3, 'result': result,
        'order_api_called': False, 'production_ready': False,
    }
    (args.output / 'result.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (args.output / 'COMPLETE').write_text('Verified broker quote replay completed.\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
