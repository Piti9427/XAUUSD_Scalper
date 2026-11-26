import sys; sys.path.insert(0, '/workspace/c22-trade-journal/research/sell-entry-sl-20261125')
from entry_sl import *
CB = build(sell_rows())
A24 = T('2024-01-01'); A25 = T('2025-01-01')
for nm, a in (('2025-26', A25), ('2024-26', A24)):
    t = portfolio2(CB, a, END); s = stats_block(t, BAL0, calendar_months(a, END))
    print(nm, len(t), round(t.net.sum(), 2), s['win'], round(s['maxdd'], 2), int((t.net>0).sum()), int((t.net<0).sum()), int((t.net==0).sum()))
print(CB.columns.tolist()); print(len(CB), CB.d.value_counts().to_dict(), END)
print(CB[['ts','sig','tx','pnl','R','why','d','i']].head())
