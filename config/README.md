# Configuration contracts

| Files | Purpose |
| --- | --- |
| `c22h4-demo.json` | Active frozen Demo identity, strategy and source pins |
| `trial30-demo.json` | Retained rollback contract |
| `research-c22-*.json` | Research candidates; not adopted by Demo |
| `native-frequency/` | Tester presets, attestation gates remain explicit |
| `*_cost_policy*.json` | Cost assumptions/attestation inputs; never refresh timestamps without evidence |
| Other strategy files | Retained legacy/research configurations |

Names and locations are pinned by runtime/research protocols, so organization
keeps these paths stable. New folder names do not authorize changing an active
strategy. Secrets remain in ignored environment/private configuration files.
