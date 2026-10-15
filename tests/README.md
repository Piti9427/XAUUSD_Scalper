# Regression suites

All130 Python test modules are grouped by purpose. Assertions/test behavior are
preserved; source imports and repository/fixture paths follow the new folders.
Native C++ harness files keep their existing paths.

| Folder | Modules | Scope |
| --- | ---: | --- |
| application/ | 22 | Config, CLI, CI and tooling |
| demo/ | 9 | C22H4 and trial30 |
| native/ | 2 | Shared MQL5 host cases and replay |
| pure_b1/ | 12 | B1 target and frozen release/capture/parity |
| research/ | 30 | Economic replay, catalogs and qualification |
| smc/ | 48 | Detection, lifecycle, broker accounting and safety |
| webhook/ | 7 | Webhook lifecycle and setup |
| fixtures/ | — | Shared fixed inputs |

```bash
# Existing repository interface: every group discovered recursively.
.venv/bin/python -m unittest discover -s tests

# Focused interfaces with package-qualified imports.
.venv/bin/python -m unittest discover -s tests/demo -t .
.venv/bin/python -m unittest tests.research.test_c22_frequency
.venv/bin/python -m unittest tests.native.test_native_frequency_replay
make native-frequency-check
```

Old `tests/test_*.py` paths in historical run logs identify the original layout;
use the same filename beneath its family for current execution. Current coverage
inventory references the new locations. Test fixture imports use `tests.<family>`;
do not reintroduce `PYTHONPATH=tests` or duplicate compatibility test files.
No test command here authorizes native Tester economics or Demo order sending.
