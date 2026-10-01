"""Read-only local trial30 status; no Wine/broker APIs or secrets."""

import argparse
import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--journal",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "data/trial30-demo.sqlite3",
    )
    args = parser.parse_args()
    conn = sqlite3.connect(args.journal.resolve().as_uri() + "?mode=ro", uri=True)
    values = {key: json.loads(value) for key, value in conn.execute("SELECT key,value FROM kv")}
    active = values.get("active")
    result = values.get("last_result", {})
    stamp = result.get("captured_utc")
    age = (
        (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds()
        if stamp
        else None
    )
    print(
        json.dumps(
            dict(
                last_result=result,
                heartbeat_age_seconds=age,
                day=values.get("day"),
                active={
                    k: active.get(k)
                    for k in ("status", "ticket", "position_id", "fill", "risk", "be_done")
                }
                if active
                else None,
                safety_halt=values.get("safety_halt"),
                broker_events=[
                    json.loads(row[0])
                    for row in conn.execute("SELECT payload FROM events ORDER BY id DESC LIMIT 10")
                ],
            ),
            indent=2,
        )
    )
    conn.close()


if __name__ == "__main__":
    main()
