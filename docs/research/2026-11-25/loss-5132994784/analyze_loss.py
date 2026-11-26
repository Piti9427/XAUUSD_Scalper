#!/usr/bin/env python3
"""Chart + condition analysis for C22 SELL ticket 5132994784 (box only, no VM).

Reproduces numbers from journal CSVs, Exness M15 bars, trade paths, and the
F2+F3 backtest candidate set. Does not change the live bot.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
JOURNAL = Path("/workspace/c22-trade-journal")
OUT = HERE
ICT = timezone(timedelta(hours=7))
TICKET = 5132994784
PREV = 5130044984
BAL0 = 400.0

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def to_ict(ts) -> datetime:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert(ICT).to_pydatetime()


def parse_ict_naive(s) -> datetime:
    return datetime.strptime(str(s), "%Y-%m-%d %H:%M:%S")


def parse_close_ict(s) -> datetime:
    t = str(s).replace("Z", "+00:00")
    return datetime.fromisoformat(t).astimezone(ICT).replace(tzinfo=None)


def ms(t) -> int:
    t = pd.Timestamp(t)
    if t.tzinfo is None:
        t = t.tz_localize("Asia/Bangkok")
    return int(t.timestamp() * 1000)


def fmt_n(x, nd=2):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    if isinstance(x, (int, np.integer)) or (isinstance(x, float) and x == int(x) and abs(x) >= 10):
        return str(int(x))
    return f"{x:.{nd}f}"


def rate_cell(lost, n, extra=""):
    if n == 0:
        return f"n=0{extra}"
    return f"{lost}/{n} = {100.0 * lost / n:.1f}%{extra}"


def flag_small(n, thresh=20):
    return " (ตัวอย่างเล็ก)" if n < thresh else ""


# ---------------------------------------------------------------------------
# portfolio (copied from f2f3-validate core.py; no import of m1)
# ---------------------------------------------------------------------------

def portfolio(c, start, end, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10, swap=-0.4743, slip_r=0.1):
    c = c[(c.ts >= ms(start)) & (c.ts < ms(end))]
    bal = bal0
    open_ = None
    dl = {}
    cool = 0
    daystart = {}
    res = []

    def nights(ts, tx):
        r0 = (ts - 75600000) // 86400000
        r1 = (tx - 75600000) // 86400000
        n = 0
        for x in range(int(r0) + 1, int(r1) + 1):
            n += 3 if pd.Timestamp(x * 86400000 + 75600000, unit="ms").weekday() == 2 else 1
        return n

    for k, r in zip(c.index, c.itertuples()):
        if open_ is not None and open_["tx"] <= r.ts:
            p = open_
            open_ = None
            bal += p["net"]
            if p["net"] < 0:
                day = p["tx"] // 86400000
                dl[day] = dl.get(day, 0) + 1
                cool = p["tx"] + int(cool_min * 60000)
            res.append(p)
        if open_ is not None or r.ts < cool:
            continue
        day = r.ts // 86400000
        if dl.get(day, 0) >= max_losses:
            continue
        daystart.setdefault(day, bal)
        if daystart[day] - bal >= daystart[day] * daily_stop:
            continue
        risk = r.R + slip_r
        if risk > bal * cap:
            continue
        sw = nights(r.ts, r.tx) * (swap if r.d == 1 else 0.0)
        open_ = dict(k=k, ts=r.ts, tx=r.tx, d=r.d, net=r.pnl + sw, R=risk, why=r.why,
                     pnl=r.pnl, entry=r.entry, atr=r.atr, atr_pct=r.atr_pct,
                     h4dist=r.h4dist, extension_atr=r.extension_atr, hour_ict=r.hour_ict,
                     session=r.session)
    if open_ is not None:
        res.append(open_)
    t = pd.DataFrame(res)
    if len(t):
        t["r"] = t.net / t.R
    return t


def run_yearly(c, start, end, **kw):
    segs = []
    y0, y1 = start.year, end.year
    for y in range(y0, y1 + 1):
        a = max(start, pd.Timestamp(f"{y}-01-01", tz="Asia/Bangkok"))
        z = min(end, pd.Timestamp(f"{y+1}-01-01", tz="Asia/Bangkok"))
        if a < z:
            segs.append((a, z))
    parts = [portfolio(c, a, z, **kw) for a, z in segs]
    parts = [p for p in parts if len(p)]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


# ---------------------------------------------------------------------------
# load live data
# ---------------------------------------------------------------------------

def load_live():
    feat = pd.read_csv(JOURNAL / "trade-features.csv")
    feat = feat.sort_values("entry_time_ict").reset_index(drop=True)
    feat["entry_dt"] = feat["entry_time_ict"].map(parse_ict_naive)
    feat["close_dt"] = feat["close_time_utc"].map(parse_close_ict)
    feat["minutes_since_prev_exit"] = (feat["entry_dt"] - feat["close_dt"].shift(1)).dt.total_seconds() / 60.0
    feat["prev_ticket"] = feat["ticket"].shift(1)
    feat["prev_exit_cause"] = feat["exit_cause"].shift(1)
    feat["prev_net_pl"] = feat["net_pl"].shift(1)
    feat["bar_range"] = feat["bar_high"] - feat["bar_low"]
    feat["bar_range_atr"] = feat["bar_range"] / feat["atr"]
    feat["extension_at_fill_atr"] = (feat["prior_low_48"] - feat["fill_price"]) / feat["atr"]
    # consecutive sells (all bot trades are SELL)
    feat["consecutive_sells"] = np.arange(1, len(feat) + 1)
    feat["day_ict"] = feat["entry_dt"].dt.strftime("%Y-%m-%d")
    feat["sell_index_today"] = feat.groupby("day_ict").cumcount() + 1
    return feat


def load_m15_exness():
    raw = pd.read_csv(JOURNAL / "_raw/bars_m15.csv", parse_dates=["bar_open_utc"])
    raw["bar_open_utc"] = pd.to_datetime(raw["bar_open_utc"], utc=True)
    raw = raw.set_index("bar_open_utc").sort_index()
    return raw


def wilder_atr(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    prev = c.shift(1)
    tr = pd.concat([(h - l), (h - prev).abs(), (l - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def atr_percentile_20d(atr: pd.Series) -> pd.Series:
    return atr.rolling(96 * 20, min_periods=96 * 5).rank(pct=True)


# ---------------------------------------------------------------------------
# post-exit (strict vs overlapping M15 bar)
# ---------------------------------------------------------------------------

def post_exit_stats(entry, sl, tp, exit_price, exit_dt_ict, r_dist, bars, side="SELL"):
    """Strict = only after exit timestamp. Overlap = include the M15 bar that contains the exit.
    SELL: favourable is down. Returns dict. Missing later bars are flagged.
    """
    last_bar_open = bars.index.max()
    last_bar_close = last_bar_open + pd.Timedelta(minutes=15)
    exit_utc = pd.Timestamp(exit_dt_ict).tz_localize(ICT).tz_convert("UTC")

    def fav(price):
        return (exit_price - price) if side == "SELL" else (price - exit_price)

    def against(price):
        return (price - exit_price) if side == "SELL" else (exit_price - price)

    # overlapping bar
    bar_open = (exit_utc.floor("15min") if exit_utc.tz is None else exit_utc.tz_convert("UTC").floor("15min"))
    # pandas floor on 15min
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    mins = int((exit_utc - epoch).total_seconds() // 60)
    bar_open = epoch + pd.Timedelta(minutes=(mins // 15) * 15)

    out = {
        "bars_end_ict": to_ict(last_bar_close).strftime("%Y-%m-%d %H:%M ICT"),
        "hours_of_bars_after_exit": (last_bar_close - exit_utc).total_seconds() / 3600.0,
        "overlap_fav_price": np.nan,
        "overlap_fav_r": np.nan,
        "strict_fav_price": np.nan,
        "strict_fav_r": np.nan,
        "strict_against_price": np.nan,
        "high_above_sl": np.nan,
        "reached_tp_hours": np.nan,
        "reached_tp": False,
        "data_complete_24h": bool((last_bar_close - exit_utc) >= pd.Timedelta(hours=24)),
    }

    if bar_open in bars.index:
        b = bars.loc[bar_open]
        if side == "SELL":
            out["overlap_fav_price"] = exit_price - b["low"]
            out["high_above_sl"] = b["high"] - sl
            # after exit, within same bar, we only know close and that high may be after or before
            # strict same-bar: we cannot split OHLC; only close vs exit if we assume nothing else
        else:
            out["overlap_fav_price"] = b["high"] - exit_price
            out["high_above_sl"] = sl - b["low"]
        out["overlap_fav_r"] = out["overlap_fav_price"] / r_dist if r_dist else np.nan

    # strict: bars whose OPEN is at or after the exit bar's NEXT bar, plus
    # same-bar close only as a lower bound for continuation after exit if close is favourable.
    next_open = bar_open + pd.Timedelta(minutes=15)
    later = bars[bars.index >= next_open]
    # same-bar close as the only strict post-exit print we have from M15 of the exit bar
    same_close = bars.loc[bar_open, "close"] if bar_open in bars.index else np.nan
    favs = []
    againsts = []
    if np.isfinite(same_close):
        favs.append(fav(same_close))
        againsts.append(against(same_close))
        # if side SELL and bar high > sl, overshoot is known from the exit bar high
        if side == "SELL" and bar_open in bars.index:
            againsts.append(against(bars.loc[bar_open, "high"]))
    tp_time = None
    for idx, row in later.iterrows():
        if side == "SELL":
            favs.append(fav(row["low"]))
            againsts.append(against(row["high"]))
            if row["low"] <= tp and tp_time is None:
                tp_time = idx
        else:
            favs.append(fav(row["high"]))
            againsts.append(against(row["low"]))
            if row["high"] >= tp and tp_time is None:
                tp_time = idx
    if favs:
        out["strict_fav_price"] = max(favs)
        out["strict_fav_r"] = out["strict_fav_price"] / r_dist if r_dist else np.nan
    if againsts:
        out["strict_against_price"] = max(againsts)
    if tp_time is not None:
        out["reached_tp"] = True
        out["reached_tp_hours"] = (tp_time - exit_utc).total_seconds() / 3600.0
        # conservative: TP may have occurred at bar open; use bar open as upper bound on wait
    return out


# ---------------------------------------------------------------------------
# backtest features
# ---------------------------------------------------------------------------

def load_backtest_sells():
    c = pd.read_pickle(JOURNAL / "research/f2f3-validate-20261124/cands_base.pkl").copy()
    b = pd.read_pickle(JOURNAL / "research/f2f3-validate-20261124/m15.pkl")
    low = b["low"].to_numpy()
    close = b["close"].to_numpy()
    # prior 48-bar low exclusive of signal bar i
    ll = pd.Series(low, index=b.index).shift(1).rolling(48, min_periods=48).min().to_numpy()
    ext = np.full(len(c), np.nan)
    i = c.i.to_numpy()
    d = c.d.to_numpy()
    atr = c.atr.to_numpy()
    # only defined for SELL (d==-1): (ll48 - close) / atr
    # for BUY: (close - hh48) / atr; we only need SELL here but compute both
    hh = pd.Series(b["high"].to_numpy(), index=b.index).shift(1).rolling(48, min_periods=48).max().to_numpy()
    ok = (i >= 0) & (i < len(close)) & np.isfinite(atr) & (atr > 0)
    sell = ok & (d == -1)
    buy = ok & (d == 1)
    ext[sell] = (ll[i[sell]] - close[i[sell]]) / atr[sell]
    ext[buy] = (close[i[buy]] - hh[i[buy]]) / atr[buy]
    c["extension_atr"] = ext
    # F2
    c2 = c[~(c.h4dist < 10)].copy()
    end = pd.Timestamp("2026-11-21", tz="Asia/Bangkok")  # cands end 2026-11-20 18:45 UTC
    start = pd.Timestamp("2015-03-02", tz="Asia/Bangkok")
    taken = run_yearly(c2, start, end, cool_min=30, max_losses=1, bal0=BAL0, cap=0.1, daily_stop=0.10)
    if len(taken) == 0:
        return taken
    taken = taken.sort_values("ts").reset_index(drop=True)
    taken["minutes_since_prev_exit"] = (taken["ts"] - taken["tx"].shift(1)) / 60000.0
    taken["prev_why"] = taken["why"].shift(1)
    taken["prev_net"] = taken["net"].shift(1)
    taken["prev_d"] = taken["d"].shift(1)
    taken["is_sell"] = taken["d"] == -1
    taken["is_loss"] = taken["net"] < 0
    taken["is_tp"] = taken["why"] == 2
    taken["is_sl"] = taken["why"] == 0
    taken["is_be"] = taken["why"] == 1
    taken["entry_ict"] = pd.to_datetime(taken["ts"], unit="ms", utc=True).dt.tz_convert("Asia/Bangkok")
    return taken, c, c2


def bucket_stats(df, pred, label):
    sub = df[pred].copy() if not isinstance(pred, pd.Series) else df[pred]
    n = len(sub)
    n_sl = int(sub["is_sl"].sum()) if n else 0
    n_tp = int(sub["is_tp"].sum()) if n else 0
    n_be = int(sub["is_be"].sum()) if n else 0
    n_loss = int(sub["is_loss"].sum()) if n else 0
    decided = n_sl + n_tp
    return {
        "label": label,
        "n": n,
        "n_sl": n_sl,
        "n_tp": n_tp,
        "n_be": n_be,
        "n_loss": n_loss,
        "sl_rate_all": (n_sl / n) if n else np.nan,
        "sl_rate_decided": (n_sl / decided) if decided else np.nan,
        "net": float(sub["net"].sum()) if n else 0.0,
        "flag": flag_small(n),
    }


# ---------------------------------------------------------------------------
# chart
# ---------------------------------------------------------------------------

def plot_candles(ax, df, width_min=12):
    w = pd.Timedelta(minutes=width_min)
    for t, row in df.iterrows():
        up = row["close"] >= row["open"]
        color = "#2e7d32" if up else "#c62828"
        ax.plot([t, t], [row["low"], row["high"]], color=color, lw=0.8, zorder=2)
        bottom = min(row["open"], row["close"])
        height = abs(row["close"] - row["open"])
        if height == 0:
            height = 0.05
        ax.add_patch(Rectangle((t - w / 2, bottom), w, height,
                               facecolor=color, edgecolor=color, lw=0.4, zorder=3, alpha=0.9))


def make_chart(feat_row, bars, path_prev, path_this, out_path):
    r = feat_row
    entry = float(r["fill_price"])
    sl = float(r["sl_initial"])
    tp = float(r["tp_initial"])
    prev_tp = 3498.257
    prev_entry = 3530.825
    prev_exit = 3497.585
    ll48 = float(r["prior_low_48"])
    ema50_sig = float(r["ema50"])
    atr = float(r["atr"])
    r_dist = float(r["sl_dist"])
    entry_utc = pd.Timestamp(r["entry_time_utc"])
    if entry_utc.tzinfo is None:
        entry_utc = entry_utc.tz_localize("UTC")
    close_utc = pd.Timestamp(str(r["close_time_utc"]).replace("Z", "+00:00"))

    start = pd.Timestamp("2026-11-25 05:30:00+00:00")
    end = bars.index.max()  # 12:00 UTC bar
    window = bars.loc[start:end].copy()
    # EMA50 on full exness series, then slice
    ema = bars["close"].ewm(span=50, adjust=False).mean()
    window["ema50"] = ema.reindex(window.index)
    rolling_ll = bars["low"].shift(1).rolling(48, min_periods=48).min()

    fig = plt.figure(figsize=(14.5, 10.2), dpi=140)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.25, 1.0], hspace=0.28)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    def style_axis(ax, ymin, ymax, title):
        ax.set_title(title, loc="left", fontsize=11, pad=6)
        ax.set_ylim(ymin, ymax)
        ax.grid(True, alpha=0.25, lw=0.5)
        ax.set_ylabel("XAUUSDm")
        # ICT ticks
        ticks = pd.date_range(ax.get_xlim() and window.index[0], window.index[-1] + pd.Timedelta(minutes=15), freq="30min")
        return ticks

    # ---- panel 1: M15 from 12:30–19:15 ICT ----
    plot_candles(ax1, window)
    ax1.plot(window.index + pd.Timedelta(minutes=7.5), window["ema50"], color="#1565c0", lw=1.2, label="EMA50 (M15)")
    ax1.axhline(ll48, color="#ef6c00", ls="--", lw=1.1, label=f"48-bar low / breakout  {ll48:.3f}")
    ax1.axhline(entry, color="#000000", ls="-", lw=0.9, label=f"Entry  {entry:.3f}")
    ax1.axhline(sl, color="#c62828", ls="-", lw=0.9, label=f"SL  {sl:.3f}")
    ax1.axhline(tp, color="#2e7d32", ls="-", lw=0.9, label=f"TP  {tp:.3f}")
    ax1.axhline(prev_tp, color="#6a1b9a", ls=":", lw=1.2, label=f"Previous TP  {prev_tp:.3f}")

    # previous entry / this entry / exit markers (times in UTC on x, which is bar opens)
    def x_at(ts):
        return pd.Timestamp(ts)

    ax1.scatter([x_at("2026-11-25 05:45:00+00:00")], [prev_entry], marker="v", s=40, color="#6a1b9a", zorder=5)
    ax1.scatter([x_at("2026-11-25 11:58:48+00:00")], [prev_exit], marker="o", s=28, color="#6a1b9a", zorder=5)
    ax1.scatter([close_utc], [sl], marker="x", s=70, color="#c62828", lw=1.6, zorder=6)
    ax1.scatter([entry_utc], [entry], marker="v", s=55, color="black", zorder=6)

    # overlay path (implied close-side) where available
    def overlay_path(ax, path, color="#424242", lw=0.7, alpha=0.85):
        if path is None or len(path) == 0:
            return
        ax.plot(path["t"], path["implied_close_side_price"], color=color, lw=lw, alpha=alpha, zorder=4)

    overlay_path(ax1, path_prev)
    overlay_path(ax1, path_this, color="#111111", lw=0.9)

    # shade signal bar 11:45 and exit bar 12:00
    sig_bar = pd.Timestamp("2026-11-25 11:45:00+00:00")
    ex_bar = pd.Timestamp("2026-11-25 12:00:00+00:00")
    ax1.axvspan(sig_bar, sig_bar + pd.Timedelta(minutes=15), color="#ffcc80", alpha=0.28, zorder=0)
    ax1.axvspan(ex_bar, ex_bar + pd.Timedelta(minutes=15), color="#ef9a9a", alpha=0.28, zorder=0)

    ymin1 = min(window["low"].min(), tp) - 8
    ymax1 = max(window["high"].max(), sl, window["ema50"].max()) + 8
    ax1.set_ylim(ymin1, ymax1)
    ax1.set_xlim(start - pd.Timedelta(minutes=5), end + pd.Timedelta(minutes=18))
    ax1.grid(True, alpha=0.25, lw=0.5)
    ax1.set_ylabel("XAUUSDm")
    ax1.set_title("M15  12:30–19:15 ICT  (grey line = trade-path implied close-side / ask)  |  shaded: signal bar 18:45–19:00, exit bar 19:00–19:15",
                  loc="left", fontsize=10, pad=6)

    # ICT x labels
    def set_ict_ticks(ax, t0, t1, freq):
        ticks = pd.date_range(t0, t1, freq=freq, tz="UTC")
        ax.set_xticks(ticks)
        ax.set_xticklabels([to_ict(t).strftime("%H:%M") for t in ticks], fontsize=8)
        ax.set_xlabel("Time (ICT, UTC+7)  25 Nov 2026")

    set_ict_ticks(ax1, start, end + pd.Timedelta(minutes=15), "30min")
    ax1.legend(loc="upper left", fontsize=7.5, ncol=2, framealpha=0.92)

    # annotations
    ax1.annotate("prev SELL entry 12:45", xy=(pd.Timestamp("2026-11-25 05:45:00+00:00"), prev_entry),
                 xytext=(pd.Timestamp("2026-11-25 06:20:00+00:00"), prev_entry + 12),
                 fontsize=7, color="#6a1b9a",
                 arrowprops=dict(arrowstyle="->", color="#6a1b9a", lw=0.7))
    ax1.annotate("prev TP 18:58", xy=(pd.Timestamp("2026-11-25 11:58:48+00:00"), prev_exit),
                 xytext=(pd.Timestamp("2026-11-25 10:30:00+00:00"), prev_exit - 18),
                 fontsize=7, color="#6a1b9a",
                 arrowprops=dict(arrowstyle="->", color="#6a1b9a", lw=0.7))
    ax1.annotate("signal bar low 3484.256\n(exhaustion wick, 2.46 ATR below breakout)",
                 xy=(sig_bar + pd.Timedelta(minutes=8), 3484.256),
                 xytext=(pd.Timestamp("2026-11-25 09:00:00+00:00"), 3472),
                 fontsize=7, color="#c62828",
                 arrowprops=dict(arrowstyle="->", color="#c62828", lw=0.7))

    # ---- panel 2: zoom 18:40–19:15 with path ----
    z0 = pd.Timestamp("2026-11-25 11:40:00+00:00")
    z1 = pd.Timestamp("2026-11-25 12:15:00+00:00")
    zw = bars.loc[pd.Timestamp("2026-11-25 11:30:00+00:00"):end]
    plot_candles(ax2, zw, width_min=6)
    ax2.plot(zw.index + pd.Timedelta(minutes=7.5), ema.reindex(zw.index), color="#1565c0", lw=1.1)
    ax2.axhline(ll48, color="#ef6c00", ls="--", lw=1.1)
    ax2.axhline(entry, color="#000000", ls="-", lw=0.9)
    ax2.axhline(sl, color="#c62828", ls="-", lw=0.9)
    ax2.axhline(tp, color="#2e7d32", ls="-", lw=0.9)
    ax2.axhline(prev_tp, color="#6a1b9a", ls=":", lw=1.2)
    ax2.axvspan(sig_bar, sig_bar + pd.Timedelta(minutes=15), color="#ffcc80", alpha=0.28, zorder=0)
    ax2.axvspan(ex_bar, ex_bar + pd.Timedelta(minutes=15), color="#ef9a9a", alpha=0.28, zorder=0)

    # path zoom
    pp = path_prev[path_prev["t"] >= z0] if path_prev is not None else None
    overlay_path(ax2, pp, color="#616161", lw=1.0)
    overlay_path(ax2, path_this, color="#111111", lw=1.15)
    ax2.scatter([entry_utc], [entry], marker="v", s=70, color="black", zorder=6, label="Entry 19:00:54")
    ax2.scatter([close_utc], [sl], marker="x", s=80, color="#c62828", lw=1.7, zorder=6, label="SL exit 19:14:29")
    ax2.scatter([pd.Timestamp("2026-11-25 11:58:48+00:00")], [prev_exit], marker="o", s=35, color="#6a1b9a", zorder=6)

    # annotate MFE and high above SL
    mfe_t = pd.Timestamp("2026-11-25 12:01:14.859+00:00")
    mfe_px = 3490.758
    ax2.annotate(f"MFE +0.04R\n{mfe_px:.3f}", xy=(mfe_t, mfe_px),
                 xytext=(pd.Timestamp("2026-11-25 12:02:30+00:00"), 3485.5),
                 fontsize=7, arrowprops=dict(arrowstyle="->", lw=0.7))
    bar_high = float(bars.loc[ex_bar, "high"])
    bar_close = float(bars.loc[ex_bar, "close"])
    ax2.annotate(f"M15 high {bar_high:.3f}\n(+{bar_high-sl:.3f} / 0.056R above SL)",
                 xy=(ex_bar + pd.Timedelta(minutes=12), bar_high),
                 xytext=(pd.Timestamp("2026-11-25 12:06:30+00:00"), 3521.8),
                 fontsize=7, color="#c62828", ha="left",
                 arrowprops=dict(arrowstyle="->", color="#c62828", lw=0.7))
    ax2.annotate(f"bar close {bar_close:.3f}\n({(sl-bar_close)/r_dist:.2f}R back from SL)",
                 xy=(ex_bar + pd.Timedelta(minutes=15), bar_close),
                 xytext=(pd.Timestamp("2026-11-25 12:06:00+00:00"), 3505.5),
                 fontsize=7, ha="left",
                 arrowprops=dict(arrowstyle="->", lw=0.7))

    # gap note: 18:58:48–19:00:55 no path; wick to 3484 happened in this gap / last ~70s of signal bar
    ax2.annotate("no path ticks 18:58:48–19:00:55\nwick low 3484.256 is in this gap",
                 xy=(pd.Timestamp("2026-11-25 11:59:20+00:00"), 3484.256),
                 xytext=(pd.Timestamp("2026-11-25 11:46:00+00:00"), 3479.8),
                 fontsize=7, color="#6d4c41", ha="left",
                 arrowprops=dict(arrowstyle="->", color="#6d4c41", lw=0.7))

    ax2.set_xlim(z0 - pd.Timedelta(minutes=1), z1 + pd.Timedelta(minutes=1))
    ax2.set_ylim(3478, 3524)
    ax2.grid(True, alpha=0.25, lw=0.5)
    ax2.set_ylabel("XAUUSDm")
    ax2.set_title("M1-detail zoom  18:40–19:15 ICT   |  path ends 19:14:26; M15 after 19:15 ICT is not on the box",
                  loc="left", fontsize=10, pad=6)
    set_ict_ticks(ax2, z0, z1, "5min")
    ax2.legend(loc="upper left", fontsize=7.5, framealpha=0.92)

    fig.suptitle("C22 SELL 5132994784  —  25 Nov 2026  (Exness XAUUSDm, times in ICT / UTC+7)",
                 fontsize=13, fontweight="bold", y=0.995)
    fig.text(0.01, 0.005,
             "Sources on the box: _raw/bars_m15.csv (last bar 19:00–19:15 ICT, close 3514.149, high 3517.741) + trade-paths 5130044984 / 5132994784.  "
             "No M1 series after 19:15 ICT.  Implied path is close-side (ask) for a SELL, so it sits slightly above M15 lows/closes.",
             fontsize=7, color="#444444")
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    feat = load_live()
    bars = load_m15_exness()
    atr_ex = wilder_atr(bars)
    atr_pct_ex = atr_percentile_20d(atr_ex)
    # attach 20d ATR percentile at the SIGNAL bar (11:45 UTC for this trade; generally the M15 bar that just closed)
    sig_bars = pd.to_datetime(feat["signal_bar_utc"], utc=True) - pd.Timedelta(minutes=15)
    # signal_bar_utc is the close time / next bar open (12:00) — the closed bar is 15m earlier
    # verify: for this ticket signal_bar_utc=12:00, bar ohlc matches 11:45
    feat["signal_closed_bar"] = sig_bars
    feat["atr_pctile_20d_exness"] = [float(atr_pct_ex.loc[t]) if t in atr_pct_ex.index and np.isfinite(atr_pct_ex.loc[t]) else np.nan
                                     for t in feat["signal_closed_bar"]]

    row = feat[feat["ticket"] == TICKET].iloc[0]
    prev = feat[feat["ticket"] == PREV].iloc[0]

    # paths
    def load_path(ticket):
        p = pd.read_csv(JOURNAL / "trade-paths" / f"{ticket}.csv")
        p["t"] = pd.to_datetime(p["time_utc"], utc=True)
        return p

    path_prev = load_path(PREV)
    path_this = load_path(TICKET)

    # ----- this trade numbers -----
    r_dist = float(row["sl_dist"])
    entry = float(row["fill_price"])
    sl = float(row["sl_initial"])
    tp = float(row["tp_initial"])
    atr = float(row["atr"])
    ll48 = float(row["prior_low_48"])
    exit_px = float(row["exit_price"])
    post = post_exit_stats(entry, sl, tp, exit_px, row["close_dt"], r_dist, bars, "SELL")

    # high of exit bar vs SL
    ex_bar = pd.Timestamp("2026-11-25 12:00:00+00:00")
    sig_bar = pd.Timestamp("2026-11-25 11:45:00+00:00")
    exit_bar = bars.loc[ex_bar]
    signal_bar = bars.loc[sig_bar] if sig_bar in bars.index else None
    # actually signal OHLC is already in features; confirm
    assert abs(float(row["bar_low"]) - 3484.256) < 1e-6
    wick_ext = (ll48 - float(row["bar_low"])) / atr
    close_ext = float(row["breakout_depth_atr"])
    fill_ext = float(row["extension_at_fill_atr"])
    high_above_sl = float(exit_bar["high"]) - sl
    close_vs_sl = sl - float(exit_bar["close"])
    # path MFE/MAE already in features
    # time since prev
    mins_since = float(row["minutes_since_prev_exit"])
    # ATR state
    atr_pct_price = float(row["atr_pct_of_price"])
    atr_pctile = float(row["atr_pctile_20d_exness"])

    # live tertile of atr_pct_of_price
    atrs = np.sort(feat["atr_pct_of_price"].to_numpy())
    q1, q2 = atrs[len(atrs) // 3], atrs[2 * len(atrs) // 3]

    # ----- live comparison -----
    # outcome groups
    sls = feat[feat["exit_cause"] == "SL"]
    tps = feat[feat["exit_cause"] == "TP"]
    bes = feat[feat["exit_cause"] == "breakeven stop"]
    wins = feat[feat["net_pl"] > 1]
    losses = feat[feat["exit_cause"] == "SL"]

    def live_bucket(mask, label):
        sub = feat[mask].copy()
        n = len(sub)
        n_sl = int((sub["exit_cause"] == "SL").sum())
        n_tp = int((sub["exit_cause"] == "TP").sum())
        n_be = int((sub["exit_cause"] == "breakeven stop").sum())
        decided = n_sl + n_tp
        return {
            "label": label, "n": n, "n_sl": n_sl, "n_tp": n_tp, "n_be": n_be,
            "sl_rate_all": n_sl / n if n else np.nan,
            "sl_rate_decided": n_sl / decided if decided else np.nan,
            "net": float(sub["net_pl"].sum()) if n else 0.0,
            "tickets": ",".join(sub["ticket"].astype(str)),
            "flag": flag_small(n),
        }

    live_rows = []
    live_rows.append(live_bucket(np.ones(len(feat), dtype=bool), "all bot SELL"))
    live_rows.append(live_bucket(feat["breakout_depth_atr"] > 1.5, "extension at close > 1.5 ATR"))
    live_rows.append(live_bucket(feat["extension_at_fill_atr"] > 1.5, "extension at fill > 1.5 ATR"))
    live_rows.append(live_bucket(feat["breakout_depth_atr"] > 1.0, "extension at close > 1.0 ATR"))
    m30 = feat["minutes_since_prev_exit"].notna() & (feat["minutes_since_prev_exit"] <= 30) & (feat["prev_exit_cause"] == "TP")
    live_rows.append(live_bucket(m30, "entry within 30 min after a TP"))
    m15 = feat["minutes_since_prev_exit"].notna() & (feat["minutes_since_prev_exit"] <= 15) & (feat["prev_exit_cause"] == "TP")
    live_rows.append(live_bucket(m15, "entry within 15 min after a TP"))
    live_rows.append(live_bucket(feat["atr_pct_of_price"] >= q2, f"ATR% of price in top third of 18 live trades (>= {q2:.3f}%)"))
    live_rows.append(live_bucket(feat["atr_pctile_20d_exness"] >= 2 / 3, "20-day ATR percentile >= 2/3 (Exness M15)"))
    live_rows.append(live_bucket((feat["breakout_depth_atr"] > 1.5) & m30, "extension > 1.5 ATR AND within 30 min after TP"))
    # MFE immediate
    live_rows.append(live_bucket(feat["mfe_r"] < 0.15, "MFE < 0.15R (almost no follow-through)"))
    live_cmp = pd.DataFrame(live_rows)

    # medians winners vs losers
    def med_table():
        rows = []
        for name, g in [("winners (TP)", tps), ("SL losses", sls), ("breakeven", bes), ("all 18", feat)]:
            rows.append({
                "group": name, "n": len(g),
                "extension_close_median": g["breakout_depth_atr"].median(),
                "extension_close_mean": g["breakout_depth_atr"].mean(),
                "extension_fill_median": g["extension_at_fill_atr"].median(),
                "atr_pct_price_median": g["atr_pct_of_price"].median(),
                "atr_pctile_20d_median": g["atr_pctile_20d_exness"].median(),
                "ema50_dist_atr_median": g["dist_close_ema50_atr"].median(),
                "macro_dist_atr_median": g["dist_close_macro_atr"].median(),
                "mfe_r_median": g["mfe_r"].median(),
                "minutes_since_prev_median": g["minutes_since_prev_exit"].median(),
                "bar_range_atr_median": g["bar_range_atr"].median(),
                "rsi7_median": g["rsi7"].median(),
            })
        return pd.DataFrame(rows)

    live_med = med_table()

    # ----- backtest -----
    taken, cands_all, cands_f2 = load_backtest_sells()
    sells = taken[taken["is_sell"]].copy()
    # windows
    def in_win(df, a, z):
        return df[(df["entry_ict"] >= a) & (df["entry_ict"] < z)]

    winspecs = {
        "2015-26 (yearly reset, through 2026-11-20)": (pd.Timestamp("2015-03-02", tz="Asia/Bangkok"), pd.Timestamp("2026-11-21", tz="Asia/Bangkok")),
        "2024-26": (pd.Timestamp("2024-01-01", tz="Asia/Bangkok"), pd.Timestamp("2026-11-21", tz="Asia/Bangkok")),
        "2025-26": (pd.Timestamp("2025-01-01", tz="Asia/Bangkok"), pd.Timestamp("2026-11-21", tz="Asia/Bangkok")),
    }
    bt_rows = []
    for wname, (a, z) in winspecs.items():
        s = in_win(sells, a, z)
        def add(pred, lab):
            # pred is a boolean array/series aligned to s
            bt_rows.append({**bucket_stats(s, pred, f"{wname} | {lab}"), "window": wname})
        add(np.ones(len(s), dtype=bool), "all F2+F3 SELL")
        add(s["extension_atr"] > 1.5, "extension > 1.5 ATR")
        add(s["extension_atr"] > 1.0, "extension > 1.0 ATR")
        add(s["minutes_since_prev_exit"].notna() & (s["minutes_since_prev_exit"] <= 30) & (s["prev_why"] == 2),
            "entry within 30 min after a TP")
        add(s["minutes_since_prev_exit"].notna() & (s["minutes_since_prev_exit"] <= 15) & (s["prev_why"] == 2),
            "entry within 15 min after a TP")
        add(s["atr_pct"] >= 2 / 3, "20-day ATR percentile >= 2/3")
        add((s["extension_atr"] > 1.5) & s["minutes_since_prev_exit"].notna() & (s["minutes_since_prev_exit"] <= 30) & (s["prev_why"] == 2),
            "extension > 1.5 ATR AND within 30 min after TP")
    bt_cmp = pd.DataFrame(bt_rows)

    # medians backtest 2024-26 and 2025-26 SELL
    bt_med_rows = []
    for wname, (a, z) in winspecs.items():
        s = in_win(sells, a, z)
        for name, g in [("TP", s[s["is_tp"]]), ("SL", s[s["is_sl"]]), ("BE", s[s["is_be"]]), ("all SELL", s)]:
            bt_med_rows.append({
                "window": wname, "group": name, "n": len(g),
                "extension_median": g["extension_atr"].median() if len(g) else np.nan,
                "extension_mean": g["extension_atr"].mean() if len(g) else np.nan,
                "atr_pctile_median": g["atr_pct"].median() if len(g) else np.nan,
                "h4dist_median": g["h4dist"].median() if len(g) else np.nan,
                "minutes_since_prev_median": g["minutes_since_prev_exit"].median() if len(g) else np.nan,
            })
    bt_med = pd.DataFrame(bt_med_rows)

    # ----- LOSS_REASONS backfill -----
    reason_rows = []
    for _, tr in feat.iterrows():
        if tr["exit_cause"] != "SL":
            continue
        post_i = post_exit_stats(float(tr["fill_price"]), float(tr["sl_initial"]), float(tr["tp_initial"]),
                                 float(tr["exit_price"]), tr["close_dt"], float(tr["sl_dist"]), bars, "SELL")
        mfe = float(tr["mfe_r"])
        primary = "immediate_reversal" if mfe < 0.15 else "failed_followthrough"
        tags = [primary]
        ext = float(tr["breakout_depth_atr"])
        if ext > 1.5:
            tags.append("late_extension_>1.5ATR")
        mins = tr["minutes_since_prev_exit"]
        if pd.notna(mins) and mins <= 30 and tr["prev_exit_cause"] == "TP":
            tags.append("reentry_within_30min_after_tp")
        if post_i["reached_tp"] and pd.notna(post_i["reached_tp_hours"]) and post_i["reached_tp_hours"] <= 24:
            tags.append("price_reached_orig_TP_within_24h")
        elif post_i["reached_tp"]:
            tags.append("price_reached_orig_TP_after_24h")
        elif not post_i["data_complete_24h"]:
            tags.append("followthrough_unknown_<24h_bars")
        notes = []
        notes.append(f"MFE {mfe:.3f}R, MAE {float(tr['mae_r']):.3f}R, hold {float(tr['holding_seconds'])/60:.1f} min")
        notes.append(f"extension_close {ext:.3f} ATR, ATR%price {float(tr['atr_pct_of_price']):.3f}, 20d ATR%ile {tr['atr_pctile_20d_exness']}")
        if pd.notna(mins):
            notes.append(f"minutes_since_prev_exit {mins:.2f}, prev {tr['prev_ticket']} {tr['prev_exit_cause']}")
        else:
            notes.append("first bot trade (no previous exit)")
        notes.append(f"session {tr['session_utc']} hour_ict {int(tr['entry_hour_ict'])}")
        if post_i["reached_tp"]:
            notes.append(f"after SL, M15 reached original TP in {post_i['reached_tp_hours']:.2f}h")
        notes.append(f"strict post-exit fav {post_i['strict_fav_r'] if pd.notna(post_i['strict_fav_r']) else 'n/a'}R "
                     f"(overlap-bar fav {post_i['overlap_fav_r'] if pd.notna(post_i['overlap_fav_r']) else 'n/a'}R is not used as post-exit; it includes the exit bar's pre-exit extreme)")
        notes.append(f"bars available until {post_i['bars_end_ict']} ({post_i['hours_of_bars_after_exit']:.2f}h after exit)")
        if int(tr["ticket"]) == TICKET:
            notes.append(f"signal-bar range {float(tr['bar_range_atr']):.2f} ATR, wick below breakout {wick_ext:.2f} ATR, "
                         f"exit-bar high {high_above_sl:.3f} above SL, bar close {close_vs_sl:.3f} below SL; "
                         f"entered {mins_since:.2f} min after previous TP ticket {PREV}")
        reason_rows.append({
            "ticket": int(tr["ticket"]),
            "side": tr["side"],
            "entry_time_ict": tr["entry_dt"].strftime("%Y-%m-%d %H:%M:%S"),
            "exit_time_ict": tr["close_dt"].strftime("%Y-%m-%d %H:%M:%S"),
            "pnl": float(tr["net_pl"]),
            "r": float(tr["r_multiple"]),
            "reason_category": primary,
            "tags": "|".join(tags),
            "extension_atr": ext,
            "mfe_r": mfe,
            "mae_r": float(tr["mae_r"]),
            "minutes_since_prev_exit": None if pd.isna(mins) else float(mins),
            "atr_pct": float(tr["atr_pct_of_price"]),
            "atr_pctile_20d": None if pd.isna(tr["atr_pctile_20d_exness"]) else float(tr["atr_pctile_20d_exness"]),
            "notes": "; ".join(notes),
        })
    reasons = pd.DataFrame(reason_rows)

    # ----- condition table for this ticket -----
    cond = pd.DataFrame([
        {"condition": "48-bar low breakout (SELL close < prior_low_48)",
         "value_at_signal": f"yes: close {float(row['bar_close']):.3f} < {ll48:.3f}",
         "threshold": "close below prior 48-bar low",
         "pass": "yes",
         "vs_live_SELL": "all 18 bot trades are SELL breakouts"},
        {"condition": "extension past breakout (close)",
         "value_at_signal": f"{close_ext:.3f} ATR ({float(row['breakout_depth']):.3f} pts)",
         "threshold": "none (no cap on live)",
         "pass": "n/a",
         "vs_live_SELL": f"winners median {tps['breakout_depth_atr'].median():.2f}; SL median {sls['breakout_depth_atr'].median():.2f}; this is the 2nd largest of 18"},
        {"condition": "extension past breakout (fill)",
         "value_at_signal": f"{fill_ext:.3f} ATR (fill {entry:.3f})",
         "threshold": "none",
         "pass": "n/a",
         "vs_live_SELL": f"winners median {tps['extension_at_fill_atr'].median():.2f}; SL median {sls['extension_at_fill_atr'].median():.2f}"},
        {"condition": "wick extension (signal-bar low vs breakout)",
         "value_at_signal": f"{wick_ext:.3f} ATR (low {float(row['bar_low']):.3f})",
         "threshold": "none",
         "pass": "n/a",
         "vs_live_SELL": f"signal-bar range {float(row['bar_range_atr']):.2f} ATR; live SL median range {sls['bar_range_atr'].median():.2f}, TP median {tps['bar_range_atr'].median():.2f}"},
        {"condition": "EMA50 (SELL: close below EMA50)",
         "value_at_signal": f"yes: close-EMA50 = {float(row['dist_close_ema50_atr']):.3f} ATR (EMA50 {float(row['ema50']):.3f})",
         "threshold": "close below EMA50",
         "pass": "yes",
         "vs_live_SELL": f"winners median {tps['dist_close_ema50_atr'].median():.2f} ATR; SL median {sls['dist_close_ema50_atr'].median():.2f}"},
        {"condition": "F2 macro distance |close-H4 EMA200|",
         "value_at_signal": f"{abs(float(row['dist_close_macro_atr'])):.3f} ATR (signed {float(row['dist_close_macro_atr']):.3f})",
         "threshold": ">= 10 ATR",
         "pass": "yes",
         "vs_live_SELL": f"winners median {tps['dist_close_macro_atr'].median():.2f}; SL median {sls['dist_close_macro_atr'].median():.2f}"},
        {"condition": "F3 max 1 loss / UTC day",
         "value_at_signal": "first loss of 2026-11-25 UTC (previous same-day trade was a TP)",
         "threshold": "block a second loss the same UTC day",
         "pass": "allowed",
         "vs_live_SELL": "after this SL, F3 blocks new entries until ~07:00 ICT 26 Nov"},
        {"condition": "ATR(14) M15",
         "value_at_signal": f"{atr:.3f}",
         "threshold": "none",
         "pass": "n/a",
         "vs_live_SELL": f"winners median {tps['atr'].median():.3f}; SL median {sls['atr'].median():.3f}"},
        {"condition": "ATR as % of price",
         "value_at_signal": f"{atr_pct_price:.3f}%",
         "threshold": "none",
         "pass": "n/a",
         "vs_live_SELL": f"top third of 18 live trades (cut {q2:.3f}%); winners median {tps['atr_pct_of_price'].median():.3f}%; SL median {sls['atr_pct_of_price'].median():.3f}%"},
        {"condition": "20-day ATR percentile (Exness M15, rank of 96*20 bars)",
         "value_at_signal": f"{atr_pctile:.3f}" if np.isfinite(atr_pctile) else "n/a",
         "threshold": "none (research cut often 2/3)",
         "pass": "n/a",
         "vs_live_SELL": f"winners median {tps['atr_pctile_20d_exness'].median():.3f}; SL median {sls['atr_pctile_20d_exness'].median():.3f}"},
        {"condition": "RSI7 at signal close",
         "value_at_signal": f"{float(row['rsi7']):.3f}",
         "threshold": "none on SELL",
         "pass": "n/a",
         "vs_live_SELL": f"winners median {tps['rsi7'].median():.2f}; SL median {sls['rsi7'].median():.2f}"},
        {"condition": "minutes since previous exit",
         "value_at_signal": f"{mins_since:.2f} min (prev ticket {PREV} TP +33.24 at 18:58:48 ICT)",
         "threshold": "cooldown 30 min applies after a loss only; after TP re-entry is allowed",
         "pass": "allowed",
         "vs_live_SELL": f"6 live SELLs entered within 30 min after a TP (see comparison table)"},
        {"condition": "consecutive SELLs",
         "value_at_signal": f"18th consecutive bot SELL; 2nd SELL on 25 Nov ICT",
         "threshold": "none (bot has no BUY fill in this journal)",
         "pass": "n/a",
         "vs_live_SELL": "all 18 bot trades are SELL"},
        {"condition": "session / time",
         "value_at_signal": "london_ny, 19:00 ICT (12:00 UTC, Wed)",
         "threshold": "none",
         "pass": "n/a",
         "vs_live_SELL": "london_ny live: 8 trades, 4 TP / 4 SL, net +2.53 (from TRADE_ANALYSIS)"},
        {"condition": "signal-to-fill delay",
         "value_at_signal": f"{float(row['signal_to_fill_ms'])/1000:.1f}s (10 quote-changed retries, 11 cycles)",
         "threshold": "n/a",
         "pass": "filled",
         "vs_live_SELL": f"spread {float(row['fill_spread']):.3f}, slippage {float(row['slippage']):.3f} (minus = filled better than request)"},
        {"condition": "risk cap 10%",
         "value_at_signal": f"risk {float(row['risk_usd']):.2f} USD = {float(row['risk_pct_of_equity']):.2f}% of equity {float(row['entry_equity']):.2f}",
         "threshold": "<= 10%",
         "pass": "yes",
         "vs_live_SELL": "lot 0.01 as usual"},
    ])

    # ----- write CSVs -----
    cond.to_csv(OUT / "conditions-5132994784.csv", index=False)
    live_cmp.to_csv(OUT / "live-comparison.csv", index=False)
    live_med.to_csv(OUT / "live-medians-winners-losers.csv", index=False)
    bt_cmp.to_csv(OUT / "backtest-f2f3-sell-comparison.csv", index=False)
    bt_med.to_csv(OUT / "backtest-f2f3-sell-medians.csv", index=False)
    # per-trade live snapshot used
    snap_cols = ["ticket", "entry_time_ict", "exit_cause", "net_pl", "r_multiple",
                 "breakout_depth_atr", "extension_at_fill_atr", "bar_range_atr", "atr", "atr_pct_of_price",
                 "atr_pctile_20d_exness", "dist_close_ema50_atr", "dist_close_macro_atr", "rsi7",
                 "session_utc", "mfe_r", "mae_r", "minutes_since_prev_exit", "prev_ticket", "prev_exit_cause",
                 "sell_index_today", "consecutive_sells"]
    feat[snap_cols].to_csv(OUT / "live-sells-features.csv", index=False)
    reasons.to_csv(OUT / "LOSS_REASONS.csv", index=False)
    # journal copy
    reasons.to_csv(JOURNAL / "LOSS_REASONS.csv", index=False)

    # chart
    chart_path = OUT / "chart-5132994784-m15-m1.png"
    make_chart(row, bars, path_prev, path_this, chart_path)

    # ----- REPORT.md (Thai) -----
    # helpers to pull bt rates
    def bt_line(window_substr, label_substr):
        hit = bt_cmp[(bt_cmp["window"].str.contains(window_substr, regex=False)) & (bt_cmp["label"].str.contains(label_substr, regex=False))]
        if len(hit) == 0:
            return "n/a"
        r = hit.iloc[0]
        return (f"{int(r['n_sl'])}/{int(r['n'])} = {100*r['sl_rate_all']:.1f}% SL จากทุกไม้"
                f"{r['flag']}; เมื่อตัด BE ออก {int(r['n_sl'])}/{int(r['n_sl'])+int(r['n_tp'])} = "
                f"{100*r['sl_rate_decided']:.1f}%" if (r['n_sl']+r['n_tp']) else f"{int(r['n_sl'])}/{int(r['n'])}{r['flag']}")

    def live_line(label_substr):
        hit = live_cmp[live_cmp["label"].str.contains(label_substr, regex=False)]
        r = hit.iloc[0]
        tickets = r["tickets"]
        return (f"{int(r['n_sl'])}/{int(r['n'])} = {100*r['sl_rate_all']:.1f}%{r['flag']}"
                f" (ตั๋ว: {tickets})" if r["n"] <= 8 else
                f"{int(r['n_sl'])}/{int(r['n'])} = {100*r['sl_rate_all']:.1f}%{r['flag']}")

    # rank of extension
    ext_rank = int((feat["breakout_depth_atr"] > close_ext).sum()) + 1  # 1 = largest

    report = f"""# บันทึกไม้แพ้ 5132994784 (โดน SL) — 25 พ.ย. 2026

งานวิจัยบน box เท่านั้น ไม่ได้ SSH ไป Oracle VM และไม่ได้เปลี่ยนบอท live ไม่ได้ commit

- เวลาที่วิเคราะห์: {datetime.now(ICT).strftime('%Y-%m-%d %H:%M ICT')}
- แท่งราคาล่าสุดบน box: M15 ปิด 25 พ.ย. 2026 19:15 ICT (แท่งเปิด 12:00 UTC, close 3514.149, high 3517.741)
- ไม่มีแท่ง M1/M15 หลัง 19:15 ICT จึงวัดการไปต่อหลังออกได้แค่ประมาณ 30 วินาทีจนจบแท่งออก
- กราฟ: `chart-5132994784-m15-m1.png`

## สรุปเหตุผลหลัก

ไม้นี้เป็น SELL ที่เข้าช้าหลังแท่งสัญญาณแกว่งแรงผิดปกติ แล้วราคาสวนกลับทันทีจนโดน SL ใน 13 นาที โดยไม่เคยไปทางเราเกิน 0.04R

แท่งสัญญาณ 18:45–19:00 ICT มีช่วง 32.821 จุด = {float(row['bar_range_atr']):.2f} ATR (เปิด 3510.587, สูง 3517.077, ต่ำ 3484.256, ปิด 3490.673) ไม้ก่อนหน้า (5130044984) เพิ่งชน TP ที่ 3497.585 เวลา 18:58:48 ICT หลังจากนั้นราคายังพุ่งลงต่อในช่องที่ไม่มี path ประมาณ 70 วินาที ลงลึกถึง 3484.256 ซึ่งต่ำกว่าระดับ breakout 3508.531 ถึง {wick_ext:.2f} ATR แล้วเด้งปิดที่ 3490.673 (ทะลุ breakout แล้ว {close_ext:.2f} ATR) บอทเข้าที่ 3491.828 เวลา 19:00:54 ICT ช้ากว่าจุด breakout {fill_ext:.2f} ATR และห่างจากไม้ก่อนแค่ {mins_since:.2f} นาที ราคามีกำไรสูงสุดแค่ 3490.758 (+0.04R) เวลา 19:01:14 แล้ววิ่งขึ้นกลับไปชน SL 3516.363 เวลา 19:14:29 ICT ขาดทุน −24.53 USD (−1.00R)

จากแท่งออก 19:00–19:15 ICT ราคาสูงสุด 3517.741 สูงกว่า SL เพียง {high_above_sl:.3f} จุด (0.056R) แล้วปิดที่ 3514.149 ต่ำกว่า SL {close_vs_sl:.3f} จุด (0.09R) ยังไม่มีแท่งหลัง 19:15 ICT จึงยังไม่สรุปได้ว่าเป็นการกลับตัวที่ยั่งยืนหรือเป็นการกวาด SL แล้วจะลงต่อ ตัวเลข +1.09R หลังออกใน TRADE_ANALYSIS มาจากการนับทั้งแท่ง M15 ที่คร่อมเวลาออก ซึ่งโลว์ 3489.313 เกิดก่อนออกไม้ (ช่วง MFE) จึงไม่ใช่การไปต่อหลังโดน SL

## สิ่งที่เห็นบนกราฟ

- ไม้ก่อนเข้า 12:45 ICT ที่ 3530.825 แล้วลงต่อจนชน TP 18:58 ICT จังหวะนี้เป็นเทรนด์ลงที่ต่อเนื่องมาทั้งช่วงบ่าย
- แท่ง 18:45–19:00 ICT ดึงขึ้นก่อนไปสูงสุด 3517.075 ราว 18:51 ICT (จาก path ของไม้ก่อน) แล้วไหลลงมาชน TP และยังลงต่อเป็นไส้ยาวถึง 3484.256 ลักษณะนี้เข้าได้กับ exhaustion spike หลังไม้ TP มากกว่าการเบรกออกแล้วไล่ต่ออย่างเรียบ
- จุดเข้าอยู่ต่ำกว่าระดับ 48-bar low 3508.531 แล้ว 16.70 จุด และต่ำกว่า EMA50 {abs(float(row['dist_close_ema50_atr'])):.2f} ATR (EMA50 = {float(row['ema50']):.3f}) ระยะ F2 จาก H4 EMA200 อยู่ที่ {abs(float(row['dist_close_macro_atr'])):.1f} ATR ผ่านเกณฑ์ 10
- หลังเข้า ราคากลับขึ้นทะลุระดับ breakout 3508.531 ประมาณ 19:13 ICT แล้วชน SL ที่ 3516.363 ซึ่งอยู่ต่ำกว่าไส้บนของแท่งสัญญาณ (3517.077) เพียง 0.714 จุด
- ไส้บนของแท่งออกสูงกว่า SL แค่ {high_above_sl:.3f} จุด ยังไม่พอจะเรียกว่ามี overshoot ใหญ่แบบ stop-hunt ที่ชัด ประกอบกับแท่งออกปิดยังสูงใกล้จุดสูงสุด (3514.149) จึงเอนไปทางแรงซื้อกลับในระยะสั้น แต่ข้อมูลหลัง 19:15 ICT ไม่มี จึงยังไม่ตัดสินว่าเป็น reversal ระยะยาว
- ATR ตอนสัญญาณ 9.878 (คิดเป็น {atr_pct_price:.3f}% ของราคา, เปอร์เซ็นไทล์ 20 วันบนแท่ง Exness = {atr_pctile:.3f}) อยู่ในกลุ่มความผันผวนสูงของไม้ live ทั้ง 18 ไม้
- เซสชัน london_ny เวลา 19:00 ICT

## ตารางเงื่อนไขตอนสัญญาณ

ค่าตอนสัญญาณใช้แท่ง M15 ที่ปิด 19:00 ICT (เปิด 18:45) ตามบันทึกของบอท

| เงื่อนไข | ค่าตอนสัญญาณ | เกณฑ์ live | ผ่าน? | เทียบไม้ SELL ของบอท |
|---|---|---|---|---|
"""
    for _, c in cond.iterrows():
        report += f"| {c['condition']} | {c['value_at_signal']} | {c['threshold']} | {c['pass']} | {c['vs_live_SELL']} |\n"

    # comparison stats
    report += f"""

## เทียบสถิติไม้ SELL ของบอท (n=18, ตัวอย่างเล็กทั้งหมด)

ไม้ของบอทใน journal มี 18 ไม้ ล้วนเป็น SELL: ชนะ TP 11, โดน SL 6, เสมอที่ BE 1, net +165.26 USD การแบ่งกลุ่มจึงมี n เล็ก ใช้ดูลักษณะของไม้นี้ ไม่ใช้สรุปว่าควรเปลี่ยนกฎ live

| กลุ่ม | อัตราโดน SL (ทุกไม้) | หมายเหตุ |
|---|---|---|
| ไม้ SELL ทั้งหมด | {live_line('all bot SELL')} | ฐาน |
| ทะลุ breakout ตอนปิด > 1.5 ATR | {live_line('extension at close > 1.5 ATR')} | ไม้นี้เป็น 1 ใน 4; อีก 3 ไม้ชนะ |
| ทะลุตอนปิด > 1.0 ATR | {live_line('extension at close > 1.0 ATR')} | ค่ากลางไม้ชนะสูงกว่าไม้แพ้ |
| เข้าใน 30 นาทีหลังไม้ TP | {live_line('entry within 30 min after a TP')} | รวมไม้นี้และ 5076811730 ที่แพ้ |
| เข้าใน 15 นาทีหลังไม้ TP | {live_line('entry within 15 min after a TP')} | |
| ATR % ของราคาอยู่ใน 1/3 บนของ 18 ไม้ (>= {q2:.3f}%) | {live_line('ATR% of price in top third')} | |
| เปอร์เซ็นไทล์ ATR 20 วัน >= 2/3 | {live_line('20-day ATR percentile')} | คำนวณจากแท่ง Exness M15 บน box |
| ทะลุ > 1.5 ATR และเข้าใน 30 นาทีหลัง TP | {live_line('extension > 1.5 ATR AND within 30 min after TP')} | 3 ไม้: 5030440319 และ 5089857436 ชนะ, ไม้นี้แพ้ |
| MFE < 0.15R | {live_line('MFE < 0.15R')} | ไม้แพ้แบบสวนทันที 4 จาก 6 ครั้งที่โดน SL |

ค่ากลาง (median):

| กลุ่ม | n | ทะลุตอนปิด (ATR) | ATR % ราคา | เปอร์เซ็นไทล์ ATR 20 วัน | ห่าง EMA50 (ATR) | ห่าง macro (ATR) | MFE (R) | นาทีหลังไม้ก่อน | ช่วงแท่งสัญญาณ (ATR) |
|---|---|---|---|---|---|---|---|---|---|
"""
    for _, m in live_med.iterrows():
        report += (f"| {m['group']} | {int(m['n'])} | {m['extension_close_median']:.3f} | "
                   f"{m['atr_pct_price_median']:.3f} | {m['atr_pctile_20d_median']:.3f} | "
                   f"{m['ema50_dist_atr_median']:.3f} | {m['macro_dist_atr_median']:.3f} | "
                   f"{m['mfe_r_median']:.3f} | {('%.1f' % m['minutes_since_prev_median']) if pd.notna(m['minutes_since_prev_median']) else 'n/a'} | "
                   f"{m['bar_range_atr_median']:.3f} |\n")

    report += f"""

ไม้นี้ทะลุตอนปิด {close_ext:.2f} ATR ซึ่งมากกว่าค่ากลางไม้ชนะ (1.02) และเป็นลำดับที่ {ext_rank} จาก 18 ไม้ (มากเป็นอันดับ 2 รองจาก 5089857436 ที่ 2.48 ATR ซึ่งชนะหลังเข้า 3.3 นาทีหลัง TP) บนตัวอย่าง live ไม้ที่ทะลุตอนปิดเกิน 1.5 ATR โดน SL 1 จาก 4 ไม้ (25%) ต่ำกว่าฐาน 33% แต่ n=4 เล็กมาก ไม้นี้เป็นข้อยกเว้นที่เข้าลึกแล้วสวนทันที กลุ่มที่ทะลุเกิน 1.5 ATR และเข้าใน 30 นาทีหลัง TP มี 3 ไม้: 5030440319 และ 5089857436 ชนะ ส่วนไม้นี้แพ้

## เทียบ backtest F2+F3 ฝั่ง SELL

ใช้ชุด candidate `cands_base.pkl` กรอง F2 (`h4dist >= 10`) แล้วจำลองพอร์ตแบบปีละ 400 USD, เพดาน 10%, หยุดวัน 10%, คูลดาวน์ 30 นาทีหลังไม้แพ้, F3 แพ้ได้ 1 ไม้ต่อวัน UTC ข้อมูลราคาของชุดนี้สิ้นสุดประมาณ 20 พ.ย. 2026 18:45 UTC จึงไม่มีไม้นี้ใน backtest ฝั่ง SELL นับไม้ที่พอร์ตรับจริงเท่านั้น why: 0 = SL, 1 = BE, 2 = TP

| ช่วง | กลุ่ม | n | SL | TP | BE | อัตรา SL (ทุกไม้) | อัตรา SL (ตัด BE) |
|---|---|---|---|---|---|---|---|
"""
    for _, rbt in bt_cmp.iterrows():
        lab = rbt["label"].split(" | ", 1)[-1]
        report += (f"| {rbt['window']} | {lab} | {int(rbt['n'])} | {int(rbt['n_sl'])} | {int(rbt['n_tp'])} | {int(rbt['n_be'])} | "
                   f"{(100*rbt['sl_rate_all']):.1f}%{rbt['flag']} | "
                   f"{(100*rbt['sl_rate_decided']):.1f}% |\n")

    report += """
ค่ากลาง extension ของไม้ SELL ใน backtest:

| ช่วง | กลุ่ม | n | extension median (ATR) | เปอร์เซ็นไทล์ ATR 20 วัน (median) |
|---|---|---|---|---|
"""
    for _, m in bt_med.iterrows():
        if m["group"] not in ("TP", "SL", "all SELL"):
            continue
        report += (f"| {m['window']} | {m['group']} | {int(m['n'])} | "
                   f"{m['extension_median']:.3f} | {m['atr_pctile_median']:.3f} |\n")

    report += """
ใน backtest ช่วงยาว 2015-26 อัตราโดน SL ของไม้ที่ทะลุ > 1.5 ATR อยู่ที่ 54.5% (60/110) ใกล้กับฐาน 57.3% (472/824) แต่ช่วงสั้นกว่านั้นสูงกว่าฐาน: ปี 2024-26 อยู่ที่ 61.1% (11/18, ตัวอย่างเล็ก) เทียบฐาน 44.4% (60/135) และปี 2025-26 อยู่ที่ 53.3% (8/15, ตัวอย่างเล็ก) เทียบฐาน 40.8% (49/120) การเข้าใน 30 นาทีหลัง TP ช่วง 2015-26 อยู่ที่ 53.4% (126/236) ใกล้ฐาน ส่วน 2024-26 อยู่ที่ 50.0% (24/48) เทียบฐาน 44.4% และ 2025-26 อยู่ที่ 50.0% (22/44) เทียบฐาน 40.8% ตัวเลขเหล่านี้เป็นสถิติย้อนหลัง ไม่ใช่เหตุผลพอจะเปลี่ยนกฎ live ถ้าจะทดสอบต่อ ควรทำได้แค่แบบ shadow log หรือ backtest ตามสเปกที่ล็อกก่อนเห็นผล

## บันทึกเหตุผลไม้โดน SL ทั้งหมดของบอท

สร้าง `/workspace/c22-trade-journal/LOSS_REASONS.csv` และสำเนาในโฟลเดอร์นี้ ใช้วิธีเดียวกันทั้ง 6 ไม้

| ticket | เข้า (ICT) | ออก (ICT) | PnL | R | หมวด | ทะลุ (ATR) | MFE (R) | นาทีหลังไม้ก่อน | หมายเหตุย่อ |
|---|---|---|---|---|---|---|---|---|---|
"""
    for _, rr in reasons.iterrows():
        mins = "n/a" if pd.isna(rr["minutes_since_prev_exit"]) else f"{rr['minutes_since_prev_exit']:.1f}"
        short = rr["reason_category"]
        if "reentry_within_30min_after_tp" in rr["tags"]:
            short += ", เข้าหลัง TP ≤30 นาที"
        if "late_extension_>1.5ATR" in rr["tags"]:
            short += ", ทะลุ >1.5 ATR"
        if "price_reached_orig_TP_within_24h" in rr["tags"]:
            short += ", หลัง SL ราคาไปถึง TP เดิมใน 24 ชม."
        if "followthrough_unknown_<24h_bars" in rr["tags"]:
            short += ", ยังไม่ครบ 24 ชม."
        report += (f"| {rr['ticket']} | {rr['entry_time_ict']} | {rr['exit_time_ict']} | {rr['pnl']:.2f} | {rr['r']:.2f} | "
                   f"{rr['reason_category']} | {rr['extension_atr']:.3f} | {rr['mfe_r']:.3f} | {mins} | {short} |\n")

    report += f"""

หมวด `immediate_reversal` = MFE < 0.15R แล้วโดน SL; `failed_followthrough` = มีกำไรค้าง 0.15R จนเกือบ 1R แต่ไม่ถึงจุดเลื่อน BE แล้วโดน SL จาก 6 ไม้ มี 4 ไม้เป็นแบบสวนทันที

## ข้อจำกัดของข้อมูล

- แท่ง M15 บน box มีถึง 19:15 ICT เท่านั้น ไม่มีแท่งหลังออกเกินประมาณ 30 วินาที จึงยังไม่รู้ว่าหลังโดน SL ราคาลงต่อเป็น +1R หรือขึ้นต่อ
- รายละเอียด M1 ได้จาก trade path ของไม้ 5130044984 (ถึง 18:58:48 ICT) และไม้นี้ (19:00:55–19:14:26 ICT) ช่อง 18:58:48–19:00:55 ไม่มี tick จึงไม่เห็นลำดับไส้ 3484.256 แบบวินาที
- path เป็นราคาฝั่งปิดไม้ SELL (ask) จึงสูงกว่าโลว์/ปิดของแท่ง M15 เล็กน้อย
- ตัวอย่าง live มี 18 ไม้ ทุกอัตราด้านบนเป็นตัวอย่างเล็ก
- backtest ใช้แท่งชุด f2f3 (คนละฟีดกับ Exness, ช่วงซ้อนกันต่างกันเฉลี่ยประมาณ 0.18 จุด) และสิ้นสุด 20 พ.ย. 2026
- ไม่ได้เสนอให้เปลี่ยนบอท live ตัวกรองที่เป็นไปได้ (เช่น ไม่เข้าถ้าทะลุเกิน 1.5 ATR หรือเว้นหลัง TP) เป็นแค่สมมติฐานสำหรับ shadow log / backtest บนตัวอย่าง live เอง การข้ามไม้ที่ทะลุเกิน 1 ATR จะช่วยไม้นี้แต่ในภาพรวมของ 18 ไม้แล้วแย่ลง ตามที่ TRADE_ANALYSIS คำนวณไว้แล้ว (−142.55 USD)

## ไฟล์ในโฟลเดอร์นี้

- `analyze_loss.py` — สคริปต์ที่รันได้ซ้ำ
- `chart-5132994784-m15-m1.png` — กราฟ M15 พร้อมรายละเอียด path แบบ M1
- `REPORT.md` — ไฟล์นี้
- `conditions-5132994784.csv`
- `live-comparison.csv`, `live-medians-winners-losers.csv`, `live-sells-features.csv`
- `backtest-f2f3-sell-comparison.csv`, `backtest-f2f3-sell-medians.csv`
- `LOSS_REASONS.csv` (สำเนาเดียวกับที่ journal ราก)
"""

    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print("WROTE", OUT / "REPORT.md")
    print("CHART", chart_path, "size", chart_path.stat().st_size)
    print("LIVE CMP")
    print(live_cmp.to_string(index=False))
    print("BT CMP")
    print(bt_cmp.to_string(index=False))
    print("REASONS")
    print(reasons[["ticket", "reason_category", "extension_atr", "mfe_r", "minutes_since_prev_exit", "tags"]].to_string(index=False))
    print("ATR pctile this trade", atr_pctile, "q2 live atr%", q2)
    print("post this trade", post)
    print("wick_ext", wick_ext, "fill_ext", fill_ext, "high_above_sl", high_above_sl)


if __name__ == "__main__":
    main()
