"""Read-only candidate journal/process status, no Wine or broker access."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main(argv=None):
    from scripts.ops.trial30_status import main as status

    return status(argv, name="c22h4")


if __name__ == "__main__":
    main()
