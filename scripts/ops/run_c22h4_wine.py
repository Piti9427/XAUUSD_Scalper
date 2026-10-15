"""Existing Wine host wrapper for C22H4 or read-only history probe."""

import sys
from scripts.ops.run_trial30_wine import main as run


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    probe = bool(args and args[0] == "--history-probe")
    if probe:
        args.pop(0)
    return run(args, entrypoint="c22h4_history_probe.py" if probe else "mt5_wine_c22h4.py")


if __name__ == "__main__":
    raise SystemExit(main())
