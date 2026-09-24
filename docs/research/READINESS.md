# BotTradeGold evidence gate

The research runner and matrix are exploratory. No strategy in this package is
authorized for live trading. The baseline uses observed historical M1 Bid/Ask
spread; commission, slippage, swap, and order delay were set to zero because
broker measurements were unavailable. The implemented rules are reconstructed
from the supplied handoff; the historical 17-family search source/config was
not provided to this research run.

Run the evidence gate against a completed baseline and the *exact* cached price
files used by that baseline:

```sh
.venv/bin/python -m scripts.research.evidence_gate \
  --baseline /absolute/path/to/completed-baseline \
  --cache /absolute/path/to/verified-price-cache \
  --output /absolute/path/to/new-output-directory
```

It checks the baseline code hashes and reconciles annual/summary results with
every trade log through `matrix.audited_run`. It also checks every price file's
byte size and SHA-256 against the run manifest. The gate manifest also pins
the auditor code hashes. It then writes a 17-family
screen and a 120-spec screen. `nonpositive_reconstructed_native` means the
specific implemented native contract did not break even in this observed run;
it says nothing definitive about another implementation of the strategy.
`positive_reconstructed_only` means the result still needs independent
validation. Every row has `production_ready=False`.

`extra_cost_to_zero_per_unit_roundtrip` is algebraic headroom:
`native_net / (native_trades * units)`, only when native net is positive. It is
not an estimate of broker commission or slippage. Historical spread is already
inside the native net and must not be added twice. No threshold in this gate
claims a statistically validated edge.

Real-money selection still needs rule-level parity with the original source,
independent post-selection data, actual broker Bid/Ask ticks and measured fees,
swap, execution/rejection behavior, plus forward demo results. The locally
exported Exness `XAUUSDm` M5/H1 OHLC file has no Ask or tick path and cannot
establish executable P&L for these strategies.
