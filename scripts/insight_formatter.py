def build_trade_insight(trade_data):
    signal_type = trade_data.get("type", "UNKNOWN")
    symbol = trade_data.get("symbol", "XAUUSD")
    entry = trade_data.get("entry")
    tp = trade_data.get("tp")
    sl = trade_data.get("sl")
    spread = trade_data.get("spread")
    rsi = trade_data.get("rsi")
    atr = trade_data.get("atr")
    rationale = trade_data.get("rationale", "Signal rules matched")

    risk_points = _abs_diff(entry, sl)
    reward_points = _abs_diff(tp, entry)
    rr = _ratio(reward_points, risk_points)

    return {
        "headline": f"{signal_type} {symbol}",
        "decision": "Review setup before entry",
        "setup": rationale,
        "levels": {
            "entry": _fmt_num(entry),
            "tp": _fmt_num(tp),
            "sl": _fmt_num(sl),
        },
        "risk": {
            "risk_points": _fmt_num(risk_points),
            "reward_points": _fmt_num(reward_points),
            "rr": f"1:{rr:.2f}" if rr else "n/a",
            "spread": _fmt_num(spread),
        },
        "context": {
            "rsi": _fmt_num(rsi),
            "atr": _fmt_num(atr),
        },
        "action": _trade_action(signal_type, spread, rr),
    }


def format_trade_for_telegram(trade_data):
    insight = build_trade_insight(trade_data)
    levels = insight["levels"]
    risk = insight["risk"]
    context = insight["context"]
    return (
        f"*{insight['headline']}* - {insight['decision']}\n"
        f"*Setup:* {insight['setup']}\n"
        f"*Levels:* Entry `{levels['entry']}` | TP `{levels['tp']}` | SL `{levels['sl']}`\n"
        f"*Risk:* {risk['rr']} | risk {risk['risk_points']} | reward {risk['reward_points']} | spread {risk['spread']}\n"
        f"*Context:* RSI {context['rsi']} | ATR {context['atr']}\n"
        f"*Action:* {insight['action']}"
    )


def format_trade_for_journal(trade_data):
    insight = build_trade_insight(trade_data)
    levels = insight["levels"]
    risk = insight["risk"]
    context = insight["context"]
    return (
        f"\n\n### {insight['headline']} - {trade_data.get('time')}\n"
        f"- Decision: {insight['decision']}\n"
        f"- Setup: {insight['setup']}\n"
        f"- Levels: Entry {levels['entry']}, TP {levels['tp']}, SL {levels['sl']}\n"
        f"- Risk: {risk['rr']}, risk {risk['risk_points']}, reward {risk['reward_points']}, spread {risk['spread']}\n"
        f"- Context: RSI {context['rsi']}, ATR {context['atr']}\n"
        f"- Action: {insight['action']}"
    )


def build_backtest_insight(trades):
    total = len(trades)
    wins = sum(1 for trade in trades if trade.get("result") == "TP")
    losses = sum(1 for trade in trades if trade.get("result") == "SL")
    open_trades = sum(1 for trade in trades if trade.get("result") == "OPEN")
    closed = wins + losses
    win_rate = (wins / closed * 100) if closed else 0

    if total == 0:
        decision = "No signal sample"
        action = "Check filters, session window, and candle data before tuning risk."
    elif closed == 0:
        decision = "Signals not resolved"
        action = "Extend backtest range or reduce TP/SL distance for validation."
    elif win_rate >= 55:
        decision = "Candidate setup"
        action = "Forward-test on demo before live alerts."
    else:
        decision = "Needs tuning"
        action = "Review spread/session/MSS filters before increasing alert frequency."

    return {
        "decision": decision,
        "total": total,
        "wins": wins,
        "losses": losses,
        "open": open_trades,
        "win_rate": win_rate,
        "action": action,
    }


def format_backtest_summary(trades):
    insight = build_backtest_insight(trades)
    return (
        "\nBACKTEST INSIGHT\n"
        f"Decision: {insight['decision']}\n"
        f"Signals: {insight['total']} | TP: {insight['wins']} | SL: {insight['losses']} | Open: {insight['open']}\n"
        f"Closed win rate: {insight['win_rate']:.2f}%\n"
        f"Action: {insight['action']}\n"
    )


def _trade_action(signal_type, spread, rr):
    if rr is not None and rr < 1.2:
        return "Skip or resize; reward is too close to risk."
    if spread is None:
        return "Confirm spread manually before acting."
    return f"Use predefined SL; do not chase if price moves beyond planned {signal_type} entry."


def _abs_diff(left, right):
    if left is None or right is None:
        return None
    return abs(float(left) - float(right))


def _ratio(reward, risk):
    if reward is None or risk in (None, 0):
        return None
    return reward / risk


def _fmt_num(value):
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"
