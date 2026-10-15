"""Two isolated reconstructions from the supplied Relick summary. Research only."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .data import REVISION, acquire, load_year
from .engine import Costs, metrics, simulate
from .strategies import Spec, features


EMA_SPEC = Spec("Relick_EMA20_50_Stoch_M15", "ema_stoch", sl=2.0, tp=2.0)
GRID_NAME = "Relick_RSI14_Grid_30_70"
GRID_UNITS = (1.0, 2.0, 4.0, 8.0)  # Assumed Standard XAUUSDm: 0.01/0.02/0.04/0.08 lot.
GRID_SPACING = 4.0  # USD price distance; source summary did not specify.
GRID_TARGET = 2.0  # Basket cash profit in USD; source summary did not specify.
GRID_HARD_STOP = 55.0  # USD/basket as reported for a different $200 account.


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ema_stoch_signals(frame: pd.DataFrame) -> pd.DataFrame:
    """Completed M15 EMA trend + EMA20 touch + Stochastic 14/3/3 reversal."""
    close = frame.close
    ema20 = close.ewm(span=20, adjust=False, min_periods=50).mean()
    ema50 = close.ewm(span=50, adjust=False, min_periods=50).mean()
    lo = frame.low.rolling(14, min_periods=14).min()
    hi = frame.high.rolling(14, min_periods=14).max()
    fast_k = 100 * (close - lo) / (hi - lo).replace(0, np.nan)
    k = fast_k.rolling(3, min_periods=3).mean()
    d = k.rolling(3, min_periods=3).mean()
    adjacent = frame.index.to_series().diff().eq(pd.Timedelta(minutes=15))
    valid = adjacent & frame.atr.gt(0) & frame.high.gt(frame.low)
    long = valid & ema20.gt(ema50) & frame.low.le(ema20) & close.gt(ema20)
    long &= k.shift().le(d.shift()) & k.gt(d) & k.le(30)
    short = valid & ema20.lt(ema50) & frame.high.ge(ema20) & close.lt(ema20)
    short &= k.shift().ge(d.shift()) & k.lt(d) & k.ge(70)
    direction = np.select([long.fillna(False), short.fillna(False)], [1, -1], 0)
    return pd.DataFrame({"direction": direction, "limit": np.nan}, index=frame.index)


def grid_signals(frame: pd.DataFrame) -> pd.DataFrame:
    """One RSI zone-entry event, never a signal on an incomplete or gapped bar."""
    adjacent = frame.index.to_series().diff().eq(pd.Timedelta(minutes=15))
    valid = adjacent & frame.atr.gt(0) & frame.high.gt(frame.low)
    long = valid & frame.rsi.shift().gt(30) & frame.rsi.le(30)
    short = valid & frame.rsi.shift().lt(70) & frame.rsi.ge(70)
    return pd.DataFrame(
        {"direction": np.select([long.fillna(False), short.fillna(False)], [1, -1], 0)},
        index=frame.index,
    )


def _basket_pnl(exit_price: float, entries: list[tuple[float, float]], direction: int) -> float:
    return sum(direction * (exit_price - entry) * units for entry, units in entries)


def _basket_threshold(entries: list[tuple[float, float]], direction: int, cash: float) -> float:
    total = sum(units for _, units in entries)
    weighted = sum(entry * units for entry, units in entries) / total
    return weighted + direction * cash / total


def simulate_grid(
    m1: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    starting_balance: float = 100.0,
    slippage: float = 0.0,
) -> tuple[pd.DataFrame, float, float]:
    """M1 OHLC basket replay. Stop wins unresolved same-minute TP/grid ordering."""
    if not np.isfinite(starting_balance) or not np.isfinite(slippage) or slippage < 0:
        raise ValueError("invalid account or slippage")
    if starting_balance <= 0:
        return (
            pd.DataFrame(
                columns=[
                    "entry_time",
                    "exit_time",
                    "direction",
                    "legs",
                    "entry_orders",
                    "exit_orders",
                    "net",
                    "balance",
                    "reason",
                ]
            ),
            starting_balance,
            0.0,
        )
    idx = m1.index
    bid = m1[["bid_open", "bid_high", "bid_low", "bid_close"]].to_numpy(float)
    ask = m1[["ask_open", "ask_high", "ask_low", "ask_close"]].to_numpy(float)
    balance = peak = starting_balance
    max_dd = 0.0
    busy_until = -1
    trades = []
    for signal_time, row in signals.loc[signals.direction.ne(0)].iterrows():
        if balance < GRID_HARD_STOP:
            break
        direction = int(row.direction)
        available = signal_time + pd.Timedelta(minutes=15)
        start = int(idx.searchsorted(available))
        if start >= len(idx) or idx[start] != available or start <= busy_until:
            continue
        opening = ask if direction == 1 else bid
        closing = bid if direction == 1 else ask
        entries = [(float(opening[start, 0] + direction * slippage), GRID_UNITS[0])]
        pending_add = False
        exit_index = len(idx) - 1
        exit_price = float(closing[-1, 3] - direction * slippage)
        reason = "END_OF_SAMPLE"
        for j in range(start, len(idx)):
            if pending_add:
                entries.append(
                    (float(opening[j, 0] + direction * slippage), GRID_UNITS[len(entries)])
                )
                pending_add = False
            stop = _basket_threshold(entries, direction, -GRID_HARD_STOP)
            target = _basket_threshold(entries, direction, GRID_TARGET)
            open_price = float(closing[j, 0])
            adverse = float(closing[j, 2 if direction == 1 else 1])
            favorable = float(closing[j, 1 if direction == 1 else 2])
            if direction * (open_price - stop) <= 0:
                exit_index, exit_price, reason = (
                    j,
                    open_price - direction * slippage,
                    "HARD_STOP_GAP",
                )
                max_dd = max(max_dd, peak - (balance + _basket_pnl(exit_price, entries, direction)))
                break
            if direction * (open_price - target) >= 0:
                exit_index, exit_price, reason = j, target - direction * slippage, "BASKET_TP_OPEN"
                break
            if direction * (adverse - stop) <= 0:
                exit_index, exit_price, reason = j, stop - direction * slippage, "HARD_STOP"
                max_dd = max(max_dd, peak - (balance + _basket_pnl(exit_price, entries, direction)))
                break
            worst = _basket_pnl(adverse - direction * slippage, entries, direction)
            max_dd = max(max_dd, peak - (balance + worst))
            if direction * (favorable - target) >= 0:
                exit_index, exit_price, reason = j, target - direction * slippage, "BASKET_TP"
                break
            if len(entries) < len(GRID_UNITS) and j + 1 < len(idx):
                next_minute = idx[j] + pd.Timedelta(minutes=1)
                last_entry = entries[-1][0]
                if (
                    idx[j + 1] == next_minute
                    and direction * (float(closing[j, 3]) - last_entry) <= -GRID_SPACING
                ):
                    pending_add = True
        net = _basket_pnl(exit_price, entries, direction)
        balance += net
        peak = max(peak, balance)
        max_dd = max(max_dd, peak - balance)
        busy_until = exit_index
        trades.append(
            {
                "entry_time": idx[start],
                "exit_time": idx[exit_index],
                "direction": direction,
                "legs": len(entries),
                "entry_orders": len(entries),
                "exit_orders": len(entries),
                "net": net,
                "balance": balance,
                "reason": reason,
            }
        )
    return (
        pd.DataFrame(
            trades,
            columns=[
                "entry_time",
                "exit_time",
                "direction",
                "legs",
                "entry_orders",
                "exit_orders",
                "net",
                "balance",
                "reason",
            ],
        ),
        balance,
        max_dd,
    )


def summarize(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"baskets": 0, "orders": 0, "wins": 0, "win_rate": 0.0, "net": 0.0, "pf": 0.0}
    pnl = trades.net
    wins = int(pnl.gt(0).sum())
    loss = -float(pnl[pnl.lt(0)].sum())
    gain = float(pnl[pnl.gt(0)].sum())
    return {
        "baskets": len(trades),
        "orders": int((trades.entry_orders + trades.exit_orders).sum()),
        "wins": wins,
        "win_rate": 100 * wins / len(trades),
        "net": float(pnl.sum()),
        "pf": gain / loss if loss else None,
    }


def audit_trade_file(path: Path, expected: dict, *, grid: bool) -> None:
    recorded = pd.read_csv(path)
    expected_count = expected["baskets"] if grid else expected["trades"]
    if len(recorded) != expected_count or not np.isclose(recorded.net.sum(), expected["net"]):
        raise ValueError(f"trade reconciliation failed: {path}")
    if recorded.empty:
        return
    starts = pd.to_datetime(recorded.entry_time, utc=True)
    exits = pd.to_datetime(recorded.exit_time, utc=True)
    if (starts > exits).any() or not starts.is_monotonic_increasing:
        raise ValueError(f"trade chronology failed: {path}")
    if grid:
        if (
            int((recorded.net > 0).sum()) != expected["wins"]
            or int((recorded.entry_orders + recorded.exit_orders).sum()) != expected["orders"]
        ):
            raise ValueError(f"grid counts failed: {path}")


def run(cache: Path, output: Path, years: tuple[int, ...] = (2025, 2026)) -> dict:
    if output.exists():
        raise FileExistsError(output)
    if years != (2025, 2026):
        raise ValueError("this frozen comparison covers 2025 and partial 2026")
    sources = acquire(cache, years, download=False)
    output.mkdir(parents=True)
    (output / "trades").mkdir()
    audits, annual = [], []
    grid_balances = {"base": 100.0, "slip_0.10": 100.0}
    for year in years:
        m1, audit = load_year(cache, year)
        audits.append(audit)
        frame = features(m1, 15)
        ema_sig = ema_stoch_signals(frame)
        for scenario, slip in (("base", 0.0), ("slip_0.10", 0.10)):
            ema_trades, ema_dd = simulate(
                m1, frame, ema_sig, EMA_SPEC, Costs(slippage=slip), native=False
            )
            ema_stats = metrics(ema_trades, ema_dd)
            ema_path = output / "trades" / f"ema__{scenario}__{year}.csv"
            ema_trades.to_csv(ema_path, index=False)
            audit_trade_file(ema_path, ema_stats, grid=False)
            annual.append(
                {"strategy": EMA_SPEC.name, "scenario": scenario, "year": year, **ema_stats}
            )
        grid_sig = grid_signals(frame)
        for scenario, slip in (("base", 0.0), ("slip_0.10", 0.10)):
            initial = grid_balances[scenario]
            grid_trades, ending, grid_dd = simulate_grid(
                m1, grid_sig, starting_balance=initial, slippage=slip
            )
            grid_balances[scenario] = ending
            grid_stats = summarize(grid_trades)
            grid_path = output / "trades" / f"grid__{scenario}__{year}.csv"
            grid_trades.to_csv(grid_path, index=False)
            audit_trade_file(grid_path, grid_stats, grid=True)
            annual.append(
                {
                    "strategy": GRID_NAME,
                    "scenario": scenario,
                    "year": year,
                    **grid_stats,
                    "start_balance": initial,
                    "end_balance": ending,
                    "max_equity_dd_usd": grid_dd,
                }
            )
        print(f"{year}: paired M1={len(m1):,}, both variants done", flush=True)
    pd.DataFrame(annual).to_csv(output / "annual.csv", index=False)
    (output / "data-audit.json").write_text(json.dumps(audits, indent=2) + "\n")
    manifest = {
        "version": "relick-two-reconstructions-v1",
        "years": list(years),
        "source_revision": REVISION,
        "inputs": sources,
        "ema": {
            "spec": asdict(EMA_SPEC),
            "stochastic": "14/3/3; cross in <=30 or >=70 with EMA20 touch and EMA20/50 direction",
            "exit": "SL=2xATR14, TP=2R",
        },
        "grid": {
            "name": GRID_NAME,
            "rsi": "RSI14 crosses into <=30/>=70",
            "units_oz": GRID_UNITS,
            "spacing_price_usd": GRID_SPACING,
            "basket_target_usd": GRID_TARGET,
            "hard_stop_usd": GRID_HARD_STOP,
            "starting_balance_usd": 100.0,
            "cash_gate": "new basket only when realized balance >= 55 USD; no margin simulation",
        },
        "costs": "historical Bid/Ask spread; Standard commission assumed zero; extra slippage base=0/unmeasured, sensitivity=0.10 adverse per fill; swap and margin unavailable",
        "source_status": "user-supplied video summary; missing rules reconstructed, not video parity",
        "selection_status": "exploratory exposed historical data; not Demo-qualified",
        "code_sha256": {
            n: sha256(Path(__file__).with_name(n))
            for n in ("relick_variants.py", "engine.py", "data.py", "strategies.py")
        },
    }
    manifest["outputs_sha256"] = {
        str(path.relative_to(output)): sha256(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name not in {"manifest.json", "COMPLETE"}
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "COMPLETE").write_text("Research-only comparison complete.\n")
    return {"annual": annual, "manifest": manifest}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.cache, args.output)


if __name__ == "__main__":
    main()
