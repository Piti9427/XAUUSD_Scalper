import pandas as pd

df = pd.read_csv("data/feedback_comparison_2026-09-28/continuous_B1_TP25_0.1.csv")
net_001 = df["net"] / df["volume"] * 0.01

balance = 200.0
peak = 200.0
max_dd = 0.0
dd_peak = 200.0
dd_trough = 200.0
low_bal = 200.0
low_trade = 0
peak_trade = 0

for idx, n in enumerate(net_001, 1):
    balance += n
    if balance > peak:
        peak = balance
        peak_trade = idx
    dd = (peak - balance) / peak * 100.0
    if dd > max_dd:
        max_dd = dd
        dd_peak = peak
        dd_trough = balance
    if balance < low_bal:
        low_bal = balance
        low_trade = idx

print("=" * 60)
print("EQUITY CURVE ANALYSIS: B1_TP25 (Fixed 0.01 Lot on $200)")
print("=" * 60)
print("Starting Balance:          $200.00")
print(
    f"Final Balance:             ${balance:.2f} (Net: +${balance - 200.0:.2f} / +{(balance / 200 - 1) * 100:.1f}%)"
)
print(f"Highest Balance Reached:   ${peak:.2f} (at Trade #{peak_trade})")
print(f"Lowest Balance from Start: ${low_bal:.2f} (at Trade #{low_trade})")
print("-" * 60)
print(f"Max Drawdown:              {max_dd:.2f}%")
print(f"Drawdown Peak:             ${dd_peak:.2f}")
print(f"Drawdown Trough (Low):     ${dd_trough:.2f}")
print(f"Money Lost in Drawdown:    -${dd_peak - dd_trough:.2f}")
print("=" * 60)
