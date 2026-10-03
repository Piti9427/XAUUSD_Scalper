# Rounded-stop reward continuation

Owner requests further optimization; prior six gates and replay/qualification/resume seams remain. Starting e31a8e1; agreed review base develop. No runtime change.

## Evidence and hypothesis

Prior admission22 has full base net575.878/WR55.33%/DD24.11%, but realizedRR1.1002 and half DD32.81/35.79 fail. Its full SELL leg has meanwin26.5652 and meanloss24.0810; ATR-denominated target does not guarantee adequate realized payoff because entry ATR differs across wins/losses and trailing can reduce wins. Hypothesis: modest target distances from actual rounded initial stop, plus earlier protection, may retain hit rate while improving payoff/drawdown. This is a research hypothesis, not inferred future MFE after recorded exits.

## Frozen catalog

594 distinct contracts: rolling RSI BUY period7/14/21, lower25/30/35, EMA50+slope4; opposite unfiltered SELL D48 with parent conflict precedence. BUYpause2.5/5/10% from all-tick equity peak. Nominal target distance = abs(entry-rounded_initial_stop) * reward1.25/1.35/1.5/2.0 for both sides. No direction-specific exit workaround or calendar switching.

Each reward has protectionoff, or BE/trail activation0.5/1.0R; reward2 additionally activation1.5R. Activations>=nominal reward omitted because target is visited before completed-bar protection. Off uses one inert activation1.0 only. Thus22 reward/protection states *27 signal/admission states =594, no semantic duplicates from inactive protection settings.

SL2.5ATR/ATR14/fixed0.01/maxrisk10/daily20 unchanged. Risk admission includes existing rounded-stop/adverse-exit/commission math; protection threshold remains cost-inclusive frozen initial risk, whereas nominal reward uses geometric stop distance. Target1.25/1.35 only expands research enum; engine price/fee/risk formulas remain unchanged. Baseline remains original trial30 ATRtarget3, SELL-only; six baseline result files must match earlier archive byte-for-byte.

## Qualification and verification

All full/first_half/second_half base/stress independently: net/WR/realizedRR strictly above trial30; DD<=trial30 and<=30%; full>=60/halves>=20; actualBUY+SELL; risk<=10%. Same audited real Bid/Ask, broker and costs. Source/input/protocol frozen before evaluation; no winner until complete catalog. Exact full-result fresh reproduction including ledger/equity required, not copied metrics. Earlier data reused; swap omitted, commission0 assumed; untouched validation and cost/forward parity required before any runtime replacement. No sealed holdout opened.

Public literal tests cover BUY/SELL targets1.25/1.35 from independently worked rounded stop prices, fixedlot/risk. CLI594 freeze/prefix/resume and corruption tests retained. Review scopes research files only; existing operator/status changes excluded.
