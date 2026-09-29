"""Read-only comparison of week and daily MT5 historical tick queries."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np


def main():
    login = int(os.environ['XAUUSD_MT5_LOGIN'])
    server = os.environ['XAUUSD_MT5_SERVER']
    if not mt5.initialize(path=os.getenv('MT5_TERMINAL_PATH', r'C:\Program Files\MetaTrader 5\terminal64.exe'),
                          login=login, password=os.environ['XAUUSD_MT5_PASSWORD'], server=server, timeout=60000):
        raise RuntimeError('MT5 initialize failed')
    try:
        account = mt5.account_info()
        if not account or account.login != login or account.server != server or account.trade_mode != 0:
            raise RuntimeError('Demo identity mismatch')
        start = datetime(2026, 3, 28, tzinfo=timezone.utc)
        end = start + timedelta(days=7)
        weekly = mt5.copy_ticks_range('XAUUSDm', start, end - timedelta(milliseconds=1), mt5.COPY_TICKS_ALL)
        if weekly is None:
            raise RuntimeError('weekly history unavailable')
        root = Path(os.environ['XAUUSD_CAPTURE_ROOT'])
        daily = []
        day = start
        while day < end:
            with np.load(root / f'{day:%Y-%m-%d}.npz') as data:
                daily.append(data['time_msc'])
            day += timedelta(days=1)
        concat = np.concatenate(daily)
        weekly_ms = weekly['time_msc']
        only_week = np.setdiff1d(weekly_ms, concat)
        only_day = np.setdiff1d(concat, weekly_ms)
        print(json.dumps({'weekly_count': len(weekly_ms), 'daily_count': len(concat),
                          'only_week_unique_milliseconds': len(only_week),
                          'only_day_unique_milliseconds': len(only_day),
                          'only_week_first_utc': datetime.fromtimestamp(int(only_week[0])/1000, timezone.utc).isoformat() if len(only_week) else None,
                          'only_week_last_utc': datetime.fromtimestamp(int(only_week[-1])/1000, timezone.utc).isoformat() if len(only_week) else None,
                          'order_api_called': False}))
    finally:
        mt5.shutdown()


if __name__ == '__main__':
    main()
