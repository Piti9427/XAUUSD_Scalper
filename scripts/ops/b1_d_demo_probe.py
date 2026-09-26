"""Read-only MT5 target Demo probe; credentials remain in environment."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def main():
    import MetaTrader5 as mt5
    print(json.dumps({'stage':'import_ok','version':mt5.__version__}),flush=True)
    login=int(os.environ['XAUUSD_MT5_LOGIN'])
    server=os.environ['XAUUSD_MT5_SERVER']
    ok=mt5.initialize(path=os.getenv('MT5_TERMINAL_PATH',r'C:\Program Files\MetaTrader 5\terminal64.exe'),login=login,password=os.environ['XAUUSD_MT5_PASSWORD'],server=server,timeout=60000)
    result={'created_at_utc':datetime.now(timezone.utc).isoformat(),'initialized':bool(ok),'last_error':mt5.last_error(),'order_api_called':False}
    try:
        if ok:
            a=mt5.account_info()
            verified=bool(a and a.login==login and a.server==server and a.trade_mode==mt5.ACCOUNT_TRADE_MODE_DEMO)
            result['target_demo_verified']=verified
            if verified:
                result['account']={k:getattr(a,k) for k in ('server','currency','balance','equity','margin_mode','leverage','margin_free')}
                si=mt5.symbol_info('XAUUSDm')
                if si:
                    result['symbol_spec']={k:getattr(si,k) for k in ('name','trade_contract_size','trade_tick_size','trade_tick_value','trade_tick_value_profit','trade_tick_value_loss','volume_min','volume_step','volume_max','volume_limit','point','digits','trade_stops_level','trade_freeze_level','swap_long','swap_short','swap_mode','swap_rollover3days','trade_mode','trade_calc_mode','trade_exemode','filling_mode','currency_profit','currency_margin')}
                tick=mt5.symbol_info_tick('XAUUSDm')
                if tick: result['latest_tick']={k:getattr(tick,k) for k in ('time','time_msc','bid','ask')}
        dest=Path(os.environ['XAUUSD_PROBE_OUTPUT'])
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,indent=2))
        print(json.dumps(result),flush=True)
        return 0 if result.get('target_demo_verified') else 1
    finally:
        mt5.shutdown()

if __name__=='__main__':
    raise SystemExit(main())
