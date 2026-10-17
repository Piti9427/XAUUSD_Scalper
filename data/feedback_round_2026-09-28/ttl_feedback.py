"""Retrospective TTL diagnosis after observing seven expired pending orders."""
from pathlib import Path
import inspect,json
import pandas as pd
from scripts.smc import backtester as module,detection
from scripts.smc.gold_v2_demo import GOLD_V2_DEMO
from scripts.smc.structure import find_fractals_5bar
from scripts.research.feedback_smc import structure_states
out=Path('data/feedback_ttl_2026-09-28');out.mkdir(exist_ok=False)
(out/'contract.json').write_text(json.dumps({'ttls':[4,8,12],'capital':10000,'window':'2026-06-01/2026-09-01','reason':'seven baseline pending orders expired before fill','retrospective':True,'promotion_allowed':False},indent=2))
m=pd.read_csv('data/feedback_smc_2026-09-28/input_m5.csv');m.time=pd.to_datetime(m.time,utc=True)
h1=pd.read_csv('data/feedback_smc_2026-09-28/input_h1.csv');h1.time=pd.to_datetime(h1.time,utc=True)
bars=m[(m.time>=pd.Timestamp('2026-06-01',tz='UTC'))&(m.time<pd.Timestamp('2026-09-01',tz='UTC'))].reset_index(drop=True)
h,l,c=[bars[k].tolist() for k in ('high','low','close')];sh,sl=find_fractals_5bar(bars);states=structure_states(h,l,c,sh,sl)
original_replay=detection.replay_structure_until;original_class=module._RecordingOrchestrator
config={k:v for k,v in GOLD_V2_DEMO.items() if k in inspect.signature(module.SMCBacktester).parameters}
rows=[]
try:
    def lookup(highs,lows,closes,swing_highs,swing_lows,end_index_exclusive):
        assert closes[-1]==c[len(closes)-1]
        return states[min(end_index_exclusive,len(highs),len(lows),len(closes))]
    detection.replay_structure_until=lookup
    for ttl in (4,8,12):
        class ResearchOrchestrator(original_class):
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**{**kwargs,'ttl_expire_bars':ttl})
        module._RecordingOrchestrator=ResearchOrchestrator
        result=module.SMCBacktester(**{**config,'initial_balance':10000,'source_label':'exness_xauusdm'}).run(bars,h1)
        if ttl==4:
            expected=json.loads(Path('data/feedback_smc_2026-09-28/validation_GOLD_V2_10000_funnel.json').read_text())
            assert result.funnel==expected and result.total_trades==0
        result.trades_df.to_csv(out/f'ttl_{ttl}.csv',index=False)
        (out/f'ttl_{ttl}_funnel.json').write_text(json.dumps(result.funnel,indent=2))
        rows.append({'ttl_bars':ttl,'trades':result.total_trades,'return_pct':result.net_profit/100,'pf':result.profit_factor,'dd_pct':result.max_drawdown_pct,'funnel':result.funnel})
        print(ttl,result.total_trades,result.net_profit,flush=True)
finally:
    detection.replay_structure_until=original_replay
    module._RecordingOrchestrator=original_class
(out/'results.json').write_text(json.dumps(rows,indent=2))
(out/'COMPLETE').write_text('Exploratory TTL diagnosis only.\n')
