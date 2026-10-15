# Review reports

โฟลเดอร์นี้เก็บเฉพาะรายงาน Markdown. โค้ด reproducers อยู่
[`scripts/debug/reviews/`](../../scripts/debug/reviews/README.md);
หลักฐาน JSON/text เก่าที่ version ไว้อยู่
[`data/research_output/review-fixtures/`](../../data/research_output/review-fixtures/README.md).
ผลทดลองใหม่, CSV, logs, checkpoints และ raw JSON เก็บ ignored `runs/<campaign>/`.

## Current work

| Report | Scope |
| --- | --- |
| [Codebase organization](2026-10-15-codebase-organization.md) | Folder layout, stable interfaces and regression evidence |
| [Profitable exits](2026-10-15-c22-profitable-exits-verdict.md) | Monthly net-profitable exits; modeled guard-rounding sensitivity |
| [Frequency first](2026-10-15-c22-frequency-first-verdict.md) | Monthly entry count and cash-consistency tradeoffs |
| [Demo vs tuned](2026-10-15-c22-demo-vs-tuned-backtest.md) | Same-input paired economic comparison |
| [Native implementation](2026-10-14-native-frequency-implementation.md) | Compile/host evidence; native economic run remains separate |
| [Runtime scrutiny](2026-10-14-c22h4-runtime-readiness-scrutiny.md) | Admission/readiness blockers |

Historical review filenames remain available in this folder. Their monetary
verdicts were not changed by organization; links to moved evidence/reproducers
follow current paths. [Architecture map](../architecture/codebase-layout.md).
