import json

with open('data/b1_tick_sweep_results.json') as f:
    data = json.load(f)

data_cost = [d for d in data if d.get('cost') is True]
print(f"Total configurations tested with real cost: {len(data_cost)}")

print("\n--- TOP 10 BY RETURN (WITH SPREAD+FEE COST) ---")
sorted_ret = sorted(data_cost, key=lambda x: x['final_balance'], reverse=True)
for i, d in enumerate(sorted_ret[:10]):
    print(f"{i+1}. SL: {d['sl_mult']} | TP: {d['tp_mult']} | Cap: {d.get('max_risk_pct')} | Final: ${d['final_balance']:.2f} (+{d['return_pct']:.1f}%) | Max DD: {d['max_dd_pct']:.1f}% | WR: {d['win_rate']:.1f}% | PF: {d['profit_factor']:.2f} | Trades: {d['trades']}")

print("\n--- TOP 10 BY RISK-ADJUSTED (RETURN / MAX DD) ---")
sorted_calmar = sorted(data_cost, key=lambda x: x['return_pct'] / max(x['max_dd_pct'], 1), reverse=True)
for i, d in enumerate(sorted_calmar[:10]):
    ratio = d['return_pct'] / max(d['max_dd_pct'], 1)
    print(f"{i+1}. SL: {d['sl_mult']} | TP: {d['tp_mult']} | Cap: {d.get('max_risk_pct')} | Final: ${d['final_balance']:.2f} (+{d['return_pct']:.1f}%) | Max DD: {d['max_dd_pct']:.1f}% | Ratio: {ratio:.2f} | PF: {d['profit_factor']:.2f}")
