"""Deterministic B1-FINAL-v1 reference, never an order-sending adapter."""
from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .strategies import Spec, wilder

APPROVED_CONFIG_SHA256 = '88c61fe344ffa0cb440fdce16f6a60a4dc5f81e0f328cba6b7d577e362d8b66e'


def load_contract(path):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != APPROVED_CONFIG_SHA256:
        raise ValueError('frozen contract drift; new reviewed build required')
    return yaml.safe_load(raw)


def resolve_initial_equity(account, simulated_deposit):
    """Change only research capital, preserving actual broker account metadata."""
    equity = account['equity'] if simulated_deposit is None else simulated_deposit
    if not math.isfinite(equity) or equity <= 0:
        raise ValueError('initial equity must be finite and positive')
    return float(equity)


def signal_direction(close, hh30, ll30, rsi, ready):
    if not ready or not all(math.isfinite(x) for x in (close, hh30, ll30, rsi)):
        return 0
    if close > hh30 and rsi <= 75:
        return 1
    if close < ll30 and rsi >= 25:
        return -1
    return 0


def reference_bars(completed):
    """Input is a hashed sequence of completed Bid M15 bars, oldest first.

    Missing intervals are absent, not fabricated. Indicators recurse across
    observed completed bars, including weekend gaps; NaNs fail closed.
    """
    idx = completed.index
    if not isinstance(idx, pd.DatetimeIndex) or idx.tz is None:
        raise ValueError('bars must have timezone-aware UTC index')
    if any(x.utcoffset() != pd.Timedelta(0) for x in idx):
        raise ValueError('bars must be UTC')
    if idx.has_duplicates or not idx.is_monotonic_increasing or (idx.as_unit('ns').asi8 % (900*10**9)).any():
        raise ValueError('invalid M15 chronology/alignment')
    f = completed[['open', 'high', 'low', 'close']].astype(float).copy()
    if not np.isfinite(f.to_numpy()).all() or (f.to_numpy() <= 0).any():
        raise ValueError('nonfinite/nonpositive OHLC')
    if ((f.high < f[['open','close']].max(axis=1)) |
        (f.low > f[['open','close']].min(axis=1)) | (f.high < f.low)).any():
        raise ValueError('invalid OHLC geometry')
    prior = f.close.shift()
    tr = pd.concat([f.high-f.low, (f.high-prior).abs(), (f.low-prior).abs()], axis=1).max(axis=1)
    delta = f.close.diff().fillna(0.)
    gain, loss = wilder(delta.clip(lower=0)), wilder(-delta.clip(upper=0))
    f['atr'] = wilder(tr)
    f['rsi'] = 100-100/(1+gain/loss)
    f.loc[(loss == 0) & (gain > 0), 'rsi'] = 100.
    f.loc[(loss == 0) & (gain == 0), 'rsi'] = 50.
    f['hh30'] = f.high.shift().rolling(30).max()
    f['ll30'] = f.low.shift().rolling(30).min()
    f['ready'] = (np.arange(len(f)) >= 99) & f[['atr','rsi','hh30','ll30']].notna().all(axis=1)
    f['direction'] = [signal_direction(c,h,l,r,ready) for c,h,l,r,ready in
                      zip(f.close,f.hh30,f.ll30,f.rsi,f.ready)]
    return f


def normalize_price(price, grid):
    if not math.isfinite(price) or price <= 0 or not math.isfinite(grid) or grid <= 0:
        raise ValueError('invalid price/tick grid')
    return math.floor(price/grid + .5)*grid


def compare_mql(reference, observed):
    """Gate A/B comparison on identical hashed bars; no trade-parity claim."""
    expected_epoch = reference.index.as_unit('ns').asi8//10**9
    if len(observed) != len(reference) or not np.array_equal(observed.bar_open_epoch,expected_epoch):
        return {'passed':False,'reason':'BAR_ALIGNMENT','bars':len(reference)}
    mismatches = {}
    for field in ('atr','rsi','hh30','ll30'):
        a = reference[field].to_numpy(float)
        b = observed[field].to_numpy(float)
        same_missing = np.isnan(a) & np.isnan(b)
        equal = same_missing | (np.isfinite(a) & np.isfinite(b) & (np.abs(a-b) <= 1e-8))
        mismatches[field] = int((~equal).sum())
    mismatches['direction'] = int((reference.direction.to_numpy() != observed.direction.to_numpy()).sum())
    return {'passed':not any(mismatches.values()),'bars':len(reference),
            'mismatches':mismatches,'absolute_tolerance':1e-8,'trade_parity_validated':False}


@dataclass
class RiskState:
    hwm: float
    equity: float = None
    hard_stop: bool = False
    max_dd: float = 0.

    def __post_init__(self):
        if self.equity is None:
            self.equity = self.hwm
        if not all(math.isfinite(x) for x in (self.hwm,self.equity,self.max_dd)) or self.hwm <= 0:
            raise ValueError('invalid equity state')
        if self.equity > self.hwm or not 0 <= self.max_dd or not isinstance(self.hard_stop,bool):
            raise ValueError('inconsistent equity state')
        if (self.hwm-self.equity)/self.hwm >= .12 or self.max_dd >= .12:
            self.hard_stop = True

    @property
    def drawdown(self):
        return (self.hwm-self.equity)/self.hwm

    @property
    def risk_pct(self):
        if self.hard_stop:
            return 0.
        # Compare equity thresholds directly to avoid subtraction error at 3/6/9%.
        for boundary,risk in ((.03,.01),(.06,.0075),(.09,.005),(.12,.0025)):
            if self.equity > self.hwm*(1-boundary):
                return risk
        return 0.

    def observe(self, equities):
        values = np.asarray(equities,dtype=float)
        if not values.size or not np.isfinite(values).all():
            raise ValueError('invalid equity observations')
        peaks = np.maximum.accumulate(np.r_[self.hwm,values])[1:]
        drawdowns = (peaks-values)/peaks
        self.max_dd = max(self.max_dd,float(drawdowns.max()))
        self.hard_stop = self.hard_stop or bool((values <= peaks*.88).any())
        self.hwm = float(peaks[-1])
        self.equity = float(values[-1])

    def save(self,path,config_hash):
        """Atomic local research checkpoint; broker recovery is a separate gate."""
        path = Path(path)
        temp = path.with_suffix(path.suffix+'.tmp')
        temp.write_text(json.dumps({'strategy_id':'B1-FINAL-v1','config_hash':config_hash,**asdict(self)},sort_keys=True)+'\n')
        temp.replace(path)

    @classmethod
    def load(cls,path,config_hash):
        try:
            state = json.loads(Path(path).read_text())
            if state.pop('strategy_id') != 'B1-FINAL-v1' or state.pop('config_hash') != config_hash:
                raise ValueError('state identity mismatch')
            if set(state) != {'hwm','equity','hard_stop','max_dd'}:
                raise ValueError('state schema mismatch')
            restored = cls(**state)
            if restored.max_dd+1e-12 < restored.drawdown:
                raise ValueError('inconsistent persisted drawdown')
            return restored
        except (KeyError,TypeError,OSError,json.JSONDecodeError) as exc:
            raise ValueError('state unavailable/corrupt; manual review required') from exc


def main():
    from .b1_d_comprehensive import load_capture, STAGES, summarize
    from .b1_d_ticks import replay
    p = argparse.ArgumentParser()
    p.add_argument('--capture',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--compare-mql',type=Path)
    p.add_argument('--reference-bars',type=Path)
    p.add_argument('--initial-equity',type=float,help='Simulated backtest deposit; never modifies broker account')
    args = p.parse_args()
    if args.initial_equity is not None:
        try: resolve_initial_equity({},args.initial_equity)
        except ValueError as exc: p.error(str(exc))
    if args.compare_mql is not None:
        if args.reference_bars is None or args.output.exists():
            p.error('comparison requires --reference-bars and new --output JSON path')
        ref = pd.read_csv(args.reference_bars)
        ref.index = pd.DatetimeIndex(pd.to_datetime(ref.pop('bar_open_utc'),utc=True))
        result = compare_mql(ref,pd.read_csv(args.compare_mql))
        result['input_sha256'] = {str(x):hashlib.sha256(x.read_bytes()).hexdigest()
                                  for x in (args.reference_bars,args.compare_mql)}
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        if not result['passed']: raise SystemExit(1)
        return
    if args.capture is None: p.error('--capture required for replay')
    if args.output.exists() or args.output.with_suffix('.partial').exists():
        raise FileExistsError('output/partial already exists')
    out = args.output.with_suffix('.partial')
    (out/'tape').mkdir(parents=True)
    config = Path('config/B1-FINAL-v1.yaml')
    contract = load_contract(config)
    config_hash = hashlib.sha256(config.read_bytes()).hexdigest()
    # Fail closed on a changed contract; this engine has one frozen alpha/risk model.
    if contract['strategy']['target_rr'] != 3.5 or contract['strategy']['sl_atr'] != 2.5:
        raise ValueError('contract drift')
    meta,times,bid,ask,legacy_frame = load_capture(args.capture,out/'tape')
    frame = reference_bars(legacy_frame[['open','high','low','close']])
    frame.to_csv(out/'reference_bars.csv',index_label='bar_open_utc',float_format='%.17g')
    parity_input = frame[['open','high','low','close']].copy()
    parity_input.insert(0,'bar_open_epoch',frame.index.as_unit('ns').asi8//10**9)
    parity_input.to_csv(out/'parity_input.csv',index=False,float_format='%.17g')
    spec = Spec('B1-FINAL-v1','donchian',lookback=30,filters=('rsi',),sl=2.5,tp=3.5)
    rows = []
    initial_equity = resolve_initial_equity(meta['account'],args.initial_equity)
    for stage,(start,end) in STAGES.items():
        mask = (frame.index+pd.Timedelta(minutes=15) >= start) & (frame.index+pd.Timedelta(minutes=15) < end)
        sig = frame[['direction']].copy()
        sig.loc[~mask,'direction'] = 0
        a,b = np.searchsorted(times,[start.value//10**6,end.value//10**6])
        state = RiskState(initial_equity)
        decisions = []
        log,stats = replay(times[a:b],bid[a:b],ask[a:b],frame,sig,spec,meta['symbol_spec'],
                           state.equity,risk_state=state,price_normalizer=normalize_price,
                           entry_window_ms=900000,_validated_tape=True,decision_log=decisions)
        decision_frame = pd.DataFrame(decisions)
        if not decision_frame.empty:
            decision_frame['signal_id'] = [f'B1-FINAL-v1|{meta["symbol"]}|{row.signal_time.isoformat()}|{row.direction}'
                                            for row in decision_frame.itertuples()]
            if decision_frame.signal_id.duplicated().any(): raise RuntimeError('duplicate signal identity')
        decision_frame.to_csv(out/f'{stage}_decisions.csv',index=False,float_format='%.17g')
        if log.empty:
            log = pd.DataFrame(columns=['entry_time','exit_time','net','r','risk_money','risk_budget'])
        log.to_csv(out/f'{stage}_ledger.csv',index=False,float_format='%.17g')
        state.save(out/f'{stage}_risk_state.json',config_hash)
        rows.append({'stage':stage,'initial_equity':initial_equity,**summarize(log,stats)})
        print(f'{stage}: {len(log)} trades; DD {state.max_dd*100:.2f}%; hard stop {state.hard_stop}',flush=True)
    manifest = {'strategy_id':'B1-FINAL-v1','created_at_utc':pd.Timestamp.now(tz='UTC').isoformat(),
                'config_sha256':config_hash,'capture_manifest_sha256':hashlib.sha256((args.capture/'manifest.json').read_bytes()).hexdigest(),
                'source_sha256':{x:hashlib.sha256(Path(x).read_bytes()).hexdigest() for x in
                                 ['scripts/research/b1_final.py','scripts/research/b1_d_ticks.py','scripts/research/strategies.py','scripts/research/b1_d_comprehensive.py','scripts/research/data.py']},
                'artifacts_sha256':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in out.glob('*.csv')},
                'broker_snapshot':meta['symbol_spec'],'account_snapshot':meta['account'],'ticks':len(times),
                'initial_equity':initial_equity,'hypothetical_capital_override':args.initial_equity is not None,
                'results':rows,'tester_mode':'python_actual_bid_ask_tick_replay_NOT_MT5_Strategy_Tester',
                'cost_model':'observed_spread_plus_present_swap_spec_UTC_rollover_scenario',
                'limitations':['Historical dataset exposed; not untouched OOS','Actual commission/slippage/margin approval unknown',
                               'Swap current spec/UTC approximation, not realized broker ledger','EA order/restart parity not validated',
                               'Handoff GetData/OANDA/2012-2022 baseline source datasets unavailable'],
                'production_ready':False,'order_api_called':False}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False)+'\n')
    (out/'COMPLETE').write_text('Research replay complete; production NO-GO.\n')
    out.rename(args.output)


if __name__ == '__main__': main()
