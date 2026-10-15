"""Research selection and evidence integrity checks; no terminal required."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from scripts.pure_b1.provenance import sha256_file
from scripts.research.exness_walk_forward import audit_capture, choose


class WalkForwardTests(unittest.TestCase):
    def test_selection_prefers_return_per_drawdown_and_never_falls_back(self):
        def row(profit, dd, trades=20):
            return dict(return_pct=profit, max_tick_equity_dd_pct=dd,
                        trades=trades, donchian=48, target_atr=3.5)
        high_return = row(90, 40)
        efficient = row(75, 25)
        invalid = [row(200, 40.01), row(200, 10, 19), row(0, 10), row(-1, 10)]
        self.assertIs(choose([high_return, efficient] + invalid), efficient)
        self.assertIs(choose([high_return]), high_return)
        self.assertIsNone(choose(invalid))
        self.assertIsNone(choose([]))

    def test_audit_rebuilds_bars_and_rejects_tape_and_raw_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline, capture = root / 'baseline', root / 'capture'
            (baseline / 'tape').mkdir(parents=True)
            capture.mkdir()
            (capture / 'COMPLETE').touch()
            start = pd.Timestamp('2026-04-01', tz='UTC')
            times = start.value // 10**6 + np.arange(30) * 60000
            bid = 2000.0 + np.arange(30)
            ask = bid + .2
            raw = capture / '2026-04-01.npz'
            np.savez(raw, time_msc=times, bid=bid, ask=ask)
            for key, values in zip(('time', 'bid', 'ask'), (times, bid, ask)):
                np.save(baseline / 'tape' / f'{key}.npy', values)
            (capture / 'manifest.json').write_text(json.dumps(dict(
                target_demo_verified=True, days=[dict(day='2026-04-01', ticks=30,
                                                      sha256=sha256_file(raw))])))
            reference = pd.DataFrame(dict(open=[2000., 2015.], high=[2014., 2029.],
                low=[2000., 2015.], close=[2014., 2029.]),
                index=pd.date_range(start, periods=2, freq='15min'))
            result = audit_capture(baseline, capture, reference)
            self.assertEqual(result['canonical_m15_verified'], 2)
            self.assertEqual(result['raw_ticks_verified'], 30)
            self.assertTrue(result['raw_tape_exact_match'])
            changed = reference.copy()
            changed.iloc[0, 1] += 1
            with self.assertRaises(AssertionError):
                audit_capture(baseline, capture, changed)
            np.save(baseline / 'tape' / 'bid.npy', bid + .01)
            with self.assertRaisesRegex(ValueError, 'raw/tape mismatch'):
                audit_capture(baseline, capture, reference)
            raw.write_bytes(raw.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'raw hash mismatch'):
                audit_capture(baseline, capture, reference)


if __name__ == '__main__':
    unittest.main()
