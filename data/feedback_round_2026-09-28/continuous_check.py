from pathlib import Path
import json
import numpy as np
import pandas as pd
import yaml
from scripts.research.feedback_round import directions
from scripts.research.b1_final import reference_bars, RiskState, normalize_price
from scripts.research.b1_d_ticks import replay
from scripts.research.b1_d_comprehensive import summarize
from scripts.research.strategies import Spec
root=Path('data/b1_feedback_baseline_2026-09-28')
out=Path('data/feedback_comparison_2026-09-28')
meta=json.loads((root/'manifest.json').read_text())
contract=json.loads((out/'contract.json').read_text())
f=pd.read_csv(root/'reference_bars.csv'); f.index=pd.DatetimeIndex(pd.to_datetime(f.pop('bar_open_utc'),utc=True)); f=reference_bars(f)
sigs=directions(f,yaml.safe_load(Path('config/settings.yaml').read_text()))
t,b,a=[np.load(root/'tape'/f'{k}.npy',mmap_mode='r') for k in ('time','bid','ask')]
start=pd.Timestamp('2026-05-14',tz='UTC'); end=pd.Timestamp('2026-09-26',tz='UTC')
l,r=np.searchsorted(t,[start.value//10**6,end.value//10**6]); mask=(f.index+pd.Timedelta(minutes=15)>=start)&(f.index+pd.Timedelta(minutes=15)<end)
rows=[]
for name,(key,sl,tp) in contract['candidates'].items():
    for cost in contract['costs_r']:
        log,stats=replay(t[l:r],b[l:r],a[l:r],f,sigs[key].where(mask,0).to_frame('direction'),Spec(name,'research',sl=sl,tp=tp),meta['broker_snapshot'],10000,extra_cost_r=cost,risk_state=RiskState(10000),price_normalizer=normalize_price,entry_window_ms=900000,_validated_tape=True)
        if not log.empty:
            assert (log.risk_money+log.extra_cost_scenario<=log.risk_budget+1e-8).all()
            np.testing.assert_allclose(10000+log.net.cumsum(),log.balance,atol=1e-7)
        log.to_csv(out/f'continuous_{name}_{cost}.csv',index=False)
        rows.append({'strategy':name,'cost_r':cost,'return_pct':(stats['final_balance']/10000-1)*100,**summarize(log,stats)})
    print(name,flush=True)
pd.DataFrame(rows).to_csv(out/'continuous_metrics.csv',index=False)
