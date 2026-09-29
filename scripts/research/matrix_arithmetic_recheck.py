"""Reproduce quoted Matrix numbers from closed trades, not a market replay."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def main():
    source = Path('data/feedback_comparison_2026-09-28/continuous_B1_TP25_0.1.csv')
    frame = pd.read_csv(source)
    fixed_pnl = frame.net / frame.volume * .01
    methods = (
        ('pure', fixed_pnl, (613.89, 413.89, 206.9, 52.99)),
        ('losses_clipped_to_minus30', fixed_pnl.clip(lower=-30), (750.39, 550.39, 275.2, 46.95)),
        ('losses_clipped_winners_capped_at15', fixed_pnl.clip(lower=-30, upper=15),
         (-1520.75, -1720.75, -860.4, 845.74)),
    )
    rows = []
    for name, pnl, expected in methods:
        balance = np.r_[200., 200. + pnl.cumsum()]
        peaks = np.maximum.accumulate(balance)
        metrics = (float(balance[-1]), float(pnl.sum()), float(pnl.sum() / 2),
                   float(np.max((peaks - balance) / peaks) * 100))
        assert tuple(round(v, digits) for v, digits in zip(metrics, (2, 2, 1, 2))) == expected
        rows.append(dict(method=name, trades=len(pnl), final_balance=metrics[0], net=metrics[1],
                         return_pct=metrics[2], closed_balance_dd_pct=metrics[3],
                         first_nonpositive_trade=int(np.flatnonzero(balance <= 0)[0]) if (balance <= 0).any() else None))
    result = dict(source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  all_quoted_rounded_values_match=True,
                  losses_clipped=int((fixed_pnl < -30).sum()), winners_replaced=int((fixed_pnl > 0).sum()),
                  method='Post-hoc ledger transformations, no tick path or recovery simulation',
                  original_compare_script_inspected=True, rows=rows)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
