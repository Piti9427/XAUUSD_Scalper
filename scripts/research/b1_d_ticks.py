"""Account-risk replay of frozen B1/D reconstruction on real broker Bid/Ask ticks."""
import argparse
from dataclasses import replace, asdict
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .strategies import features, registry, signals


def replay(times, bid, ask, frame, signal, spec, broker, balance, extra_cost_r=0.0, *, risk_pct=0.005, delay_ms=0, slippage=0.0, _validated_tape=False, _exit_cache=None, risk_state=None, price_normalizer=None, entry_window_ms=None, decision_log=None):
    """One independent candidate/account; risk-flooring, no regime filter.

    Stops/targets rounded to observed tick grid. Historical leverage/margin and
    fees are not inferred. Swap scenario uses present specification and UTC
    midnight, not observed historical broker rollover.
    """
    if not np.isfinite(risk_pct) or not 0 < risk_pct < 1:
        raise ValueError('risk_pct must be finite and between zero and one')
    if delay_ms<0 or not np.isfinite(slippage) or slippage<0:
        raise ValueError('invalid latency or slippage')
    if entry_window_ms is not None and (not np.isfinite(entry_window_ms) or entry_window_ms <= 0):
        raise ValueError('invalid entry window')
    if frame.index.tz is None or any(value.utcoffset()!=pd.Timedelta(0) for value in frame.index):
        raise ValueError('signal timestamps must be timezone-aware UTC')
    if not frame.index.equals(signal.index):
        raise ValueError('signal/frame index mismatch')
    if not np.isfinite(balance) or balance<=0 or not np.isfinite(extra_cost_r) or extra_cost_r<0:
        raise ValueError('invalid account or cost scenario')
    if not _validated_tape and (not (len(times)==len(bid)==len(ask)) or not len(times) or (np.diff(times)<0).any()):
        raise ValueError('invalid tick chronology')
    if not _validated_tape and (not np.isfinite(bid).all() or not np.isfinite(ask).all() or (bid<=0).any() or (ask<bid).any()):
        raise ValueError('invalid Bid/Ask')
    contract=broker['trade_contract_size'];step=broker['volume_step'];minimum=broker['volume_min']
    if any(not np.isfinite(broker[key]) or broker[key]<=0 for key in ('trade_contract_size','volume_step','volume_min','volume_max','trade_tick_size','point')):
        raise ValueError('invalid broker specification')
    grid=broker['trade_tick_size'];point=broker['point']
    peak=balance;dd=0.0;busy=-1;trades=[];rejected={'tick_gap':0,'risk_below_min':0,'busy':0}
    normalize=(lambda value: round(value/grid)*grid) if price_normalizer is None else (lambda value: price_normalizer(value,grid))
    if risk_state is not None:
        if risk_state.equity != balance: raise ValueError('risk state/account mismatch')
        peak=risk_state.hwm;dd=risk_state.max_dd
        rejected['hard_dd_stop']=0
    for i in np.flatnonzero(signal.direction.to_numpy()):
        when=frame.index[i]+pd.Timedelta(minutes=15)
        decision={'signal_bar_open_utc':frame.index[i],'signal_time':when,
                  'direction':int(signal.direction.iloc[i]),'atr':float(frame.atr.iloc[i]),
                  'equity':balance,'outcome':'UNPROCESSED'}
        if decision_log is not None: decision_log.append(decision)
        stamp=when.value//1_000_000+delay_ms
        j=int(np.searchsorted(times,stamp))
        missing_tick=j>=len(times)
        if not missing_tick:
            missing_tick=(times[j]-stamp>60000) if entry_window_ms is None else (times[j]-stamp>=entry_window_ms)
        if missing_tick:
            decision['outcome']='TICK_GAP'
            rejected['tick_gap']+=1;continue
        if j<=busy:
            decision['outcome']='POSITION_OPEN'
            rejected['busy']+=1;continue
        effective_risk=risk_pct
        entry_dd=None
        if risk_state is not None:
            risk_state.observe([balance])
            effective_risk=risk_state.risk_pct
            entry_dd=risk_state.drawdown
            if effective_risk==0:
                decision.update({'outcome':'HARD_DD_STOP','risk_pct':0.,'entry_dd_pct':entry_dd*100})
                rejected['hard_dd_stop']+=1;continue
        direction=int(signal.direction.iloc[i]);entry=float(ask[j] if direction==1 else bid[j])+direction*slippage
        distance=float(frame.atr.iloc[i])*spec.sl
        stop=normalize(entry-direction*distance)
        distance=abs(entry-stop)
        if not np.isfinite(distance) or distance<=0:
            decision['outcome']='INVALID_STOP_DISTANCE';continue
        target=normalize(entry+direction*distance*spec.tp)
        budget=balance*effective_risk
        # Reserve extra scenario cost in admission budget; never clamp up to min.
        raw=budget/(distance*contract*(1+extra_cost_r))
        volume=min(broker['volume_max'],np.floor(raw/step+1e-10)*step)
        decision.update({'entry_time':pd.Timestamp(int(times[j]),unit='ms',tz='UTC'),
                         'entry':entry,'stop':stop,'target':target,'risk_pct':effective_risk,
                         'risk_budget':budget,'raw_volume':raw,'normalized_volume':volume,
                         'minimum_lot_stop_risk':distance*contract*minimum,
                         'entry_dd_pct':None if entry_dd is None else entry_dd*100})
        if volume<minimum or distance*contract*volume*(1+extra_cost_r)>budget+1e-9:
            decision['outcome']='RISK_BELOW_MINIMUM_LOT'
            rejected['risk_below_min']+=1;continue
        decision['outcome']='REPLAY_EXECUTED'
        quotes=bid if direction==1 else ask
        cache_key=(j,direction,stop,target)
        cached=None if _exit_cache is None else _exit_cache.get(cache_key)
        if cached is None:
            hit=None
            for left in range(j,len(times),100000):
                block=quotes[left:left+100000]
                where=np.flatnonzero((direction*(block-stop)<=0)|(direction*(block-target)>=0))
                if len(where): hit=left+int(where[0]);break
            k=len(times)-1 if hit is None else hit
            reason='END_OF_SAMPLE' if hit is None else ('SL' if direction*(quotes[k]-stop)<=0 else 'TP')
            exit_price=float(quotes[k])-direction*slippage if reason!='TP' else target
            if _exit_cache is not None: _exit_cache[cache_key]=(k,reason,exit_price)
        else:
            k,reason,exit_price=cached
        risk=distance*contract*volume
        gross=direction*(exit_price-entry)*contract*volume
        # Explicit sensitivity only. Current swap points, UTC midnight approximation.
        start_day=pd.Timestamp(int(times[j]),unit='ms',tz='UTC').normalize()
        end_day=pd.Timestamp(int(times[k]),unit='ms',tz='UTC').normalize()
        rollovers=pd.date_range(start_day+pd.Timedelta(days=1),end_day,freq='D')
        nights=sum(3 if (day.dayofweek+1)==broker['swap_rollover3days'] else 1 for day in rollovers)
        swap_points=broker['swap_long'] if direction==1 else broker['swap_short']
        swap=swap_points*point*contract*volume*nights if broker['swap_mode']==1 else 0.0
        fees=extra_cost_r*risk
        net=gross+swap-fees
        # Mark every actual tick, including exit. Reserve scenario fee throughout.
        marks=balance+direction*(quotes[j:k+1]-entry)*contract*volume-fees
        if len(rollovers):
            weights=np.array([3 if (day.dayofweek+1)==broker['swap_rollover3days'] else 1 for day in rollovers])
            accrued=np.r_[0,np.cumsum(weights)]
            counts=np.searchsorted(np.array([day.value//1_000_000 for day in rollovers]),times[j:k+1],side='right')
            if broker['swap_mode']==1: marks=marks+accrued[counts]*swap_points*point*contract*volume
        marks[-1]=balance+net
        if risk_state is not None: risk_state.observe(marks)
        peaks=np.maximum.accumulate(np.r_[peak,marks])[1:]
        dd=max(dd,float(np.max((peaks-marks)/peaks)))
        peak=max(peak,float(np.max(marks)))
        balance+=net;busy=k
        trades.append({'signal_time':when,'entry_time':pd.Timestamp(int(times[j]),unit='ms',tz='UTC'),
                       'exit_time':pd.Timestamp(int(times[k]),unit='ms',tz='UTC'),'direction':direction,
                       'entry':entry,'exit':exit_price,'stop':stop,'target':target,'volume':volume,
                       'risk_money':risk,'risk_budget':budget,'gross':gross,'swap_scenario':swap,
                       'cumulative_max_dd_pct':dd*100,'entry_regime':frame.regime.iloc[i] if 'regime' in frame else 'unclassified','extra_cost_scenario':fees,'net':net,'r':net/risk,'reason':reason,'balance':balance})
        if risk_state is not None:
            trades[-1].update({'risk_pct':effective_risk,'entry_dd_pct':entry_dd*100,'equity_hwm':risk_state.hwm,'hard_dd_stop':risk_state.hard_stop})
        if balance<=0: break
    stats={'final_balance':balance,'max_tick_equity_dd_pct':dd*100,'rejections':rejected}
    if risk_state is not None: stats.update({'hard_dd_stop':risk_state.hard_stop,'equity_hwm':risk_state.hwm})
    return pd.DataFrame(trades),stats


def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--risk-pcts',type=float,nargs='+',default=[0.005])
    p.add_argument('--rr',type=float,default=None)
    args=p.parse_args()
    if any(not np.isfinite(r) or not 0<r<1 for r in args.risk_pcts): p.error('invalid risk fraction')
    if args.rr is not None and (not np.isfinite(args.rr) or args.rr<=0): p.error('invalid RR')
    if not (args.capture/'COMPLETE').exists(): raise ValueError('capture incomplete')
    manifest=json.loads((args.capture/'manifest.json').read_text())
    if not manifest['target_demo_verified'] or manifest['symbol']!='XAUUSDm': raise ValueError('target mismatch')
    files=[]
    for day in manifest['days']:
        path=args.capture/(day['day']+'.npz')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=day['sha256']: raise ValueError('tick hash mismatch')
        files.append(np.load(path))
    times=np.concatenate([f['time_msc'] for f in files]);bid=np.concatenate([f['bid'] for f in files]);ask=np.concatenate([f['ask'] for f in files])
    if not len(times) or (np.diff(times)<0).any() or not np.isfinite(bid).all() or not np.isfinite(ask).all() or (bid<=0).any() or (ask<bid).any(): raise ValueError('invalid tick tape')
    rates_path=args.capture/'m1.npz'
    if hashlib.sha256(rates_path.read_bytes()).hexdigest()!=manifest['m1_sha256']: raise ValueError('rates hash mismatch')
    rates=pd.DataFrame(np.load(rates_path)['rates']);rates.index=pd.to_datetime(rates.time,unit='s',utc=True)
    if rates.index.duplicated().any() or not rates.index.is_monotonic_increasing: raise ValueError('invalid rates time')
    ohlc=rates[['open','high','low','close']]
    # Ask is not used to calculate strategy features; zero dummy spread only here.
    f=features(ohlc.add_prefix('bid_').join(ohlc.add_prefix('ask_')),15)
    specs=[replace(s,name=name,reconstruction=True) for s,name in [(next(s for s in registry() if s.name=='B_Donchian30_RSI'),'B1_reconstructed'),(next(s for s in registry() if s.name=='D_ATR1.5_RSI_FVG'),'D_reconstructed')]]
    if args.rr is not None:
        specs=[replace(s,tp=args.rr) for s in specs]
    if args.output.exists(): raise FileExistsError(args.output)
    partial=args.output.with_name(args.output.name+'.partial');partial.mkdir(parents=True,exist_ok=False)
    summaries=[]
    initial=manifest['account']['balance']
    for spec in specs:
        sig=signals(f,spec);sig.loc[(sig.index+pd.Timedelta(minutes=15))<pd.Timestamp(manifest['start']),'direction']=0
        for risk_pct in args.risk_pcts:
            for extra in (0.0,0.1):
                log,stats=replay(times,bid,ask,f,sig,spec,manifest['symbol_spec'],initial,extra,risk_pct=risk_pct)
                if log.empty: log=pd.DataFrame(columns=['signal_time','entry_time','net','r','volume','risk_money','risk_budget'])
                log.to_csv(partial/f'{spec.name}_risk_{risk_pct:g}_rr_{spec.tp:g}_extra_{extra}.csv',index=False)
                losses=-log.loc[log.net<0,'net'].sum();profits=log.loc[log.net>0,'net'].sum()
                summaries.append({'strategy':spec.name,'risk_pct':risk_pct,'rr':spec.tp,'extra_cost_r':extra,'initial_balance':initial,**stats,'trades':len(log),'net':float(log.net.sum()),'pf':float(profits/losses) if losses else None,'expectancy_r':float(log.r.mean()) if len(log) else None,'win_rate':float((log.net>0).mean()) if len(log) else None})
    result={'version':'b1-d-risk-rr-experiment-v1.1.0' if args.rr is not None or args.risk_pcts!=[0.005] else 'b1-d-reconstruction-v1.0.0','created_at_utc':pd.Timestamp.now(tz='UTC').isoformat(),'ticks':len(times),'first_tick':str(pd.Timestamp(int(times[0]),unit='ms',tz='UTC')),'last_tick':str(pd.Timestamp(int(times[-1]),unit='ms',tz='UTC')),'spread_median':float(np.median(ask-bid)),'spread_p99':float(np.quantile(ask-bid,.99)),
            'capture_manifest_sha256':hashlib.sha256((args.capture/'manifest.json').read_bytes()).hexdigest(),'code_sha256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in [Path(__file__),Path(__file__).with_name('strategies.py')]},'specs':[asdict(s) for s in specs],
            'limitations':['commission/slippage historical unmeasured','swap uses current specs and assumed UTC rollover, not historical realized costs','historical margin/leverage/stops changes unmeasured; no broker approval simulated','starting balance is current Demo snapshot, not historical balance','historical same-period exposed; not prospective OOS','no orders sent'],'production_ready':False,'results':summaries}
    (partial/'metrics.json').write_text(json.dumps(result,indent=2))
    for path in partial.glob('*.csv'):
        if not {'entry_time','net','risk_money'}.issubset(pd.read_csv(path,nrows=0).columns): raise RuntimeError('FAILED_REPORT')
    (partial/'COMPLETE').write_text('Real broker historical tick replay complete; unmeasured execution costs/margin prohibit qualification.\n');partial.rename(args.output)
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
