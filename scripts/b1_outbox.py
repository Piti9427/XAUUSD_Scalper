"""Durable consumer for the B1-FINAL EA outbox (append-only JSONL).

Runs outside the EA, so notification outages never touch position management.
Only broker-confirmed execution events become executed-trade cards. Delivery
state is persisted per event ID: acknowledged events are never resent, and a
send timeout is recorded as DELIVERY_UNKNOWN (no exactly-once claim).
"""

import argparse
import fcntl
import json
import os
from pathlib import Path

EXECUTED_TYPES = {"FILL_CONFIRMED", "SL_MODIFIED_CONFIRMED", "CLOSE_CONFIRMED"}
TITLES = {
    "FILL_CONFIRMED": "B1 FILL (broker-confirmed)",
    "SL_MODIFIED_CONFIRMED": "B1 STOP MOVED (broker-confirmed)",
    "CLOSE_CONFIRMED": "B1 CLOSE (broker-confirmed)",
}
CARD_FIELDS = {
    "FILL_CONFIRMED": ("direction", "volume", "fill_price", "sl", "tp", "partial"),
    "SL_MODIFIED_CONFIRMED": ("confirmed_sl",),
    "CLOSE_CONFIRMED": ("reason", "volume", "exit_price", "net_profit", "net_r"),
}


class NotSentError(Exception):
    """Sink proves request was never submitted; retry is safe."""


def read_events(path):
    """Complete lines only; an unterminated tail is still being written by the EA."""
    text = Path(path).read_text() if Path(path).exists() else ""
    lines = text.split("\n")
    tail = lines.pop()
    events = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"corrupt outbox line {number}; manual review required") from exc
    return events, bool(tail.strip())


def load_state(path):
    if not Path(path).exists():
        return {"events": {}}
    try:
        state = json.loads(Path(path).read_text())
        if not isinstance(state.get("events"), dict):
            raise ValueError
        return state
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("outbox state corrupt; refusing to resend or skip events") from exc


def save_state(path, state):
    temp = Path(str(path) + ".tmp")
    with temp.open("w") as handle:
        handle.write(json.dumps(state, sort_keys=True))
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    directory = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def card(event):
    """Shared payload only: private broker linkage never leaves the host."""
    fields = event.get("fields", {})
    lines = [TITLES[event["type"]], f"{event['version']} {event['symbol']} {event['utc']}"]
    lines += [f"{key}: {fields[key]}" for key in CARD_FIELDS[event["type"]] if key in fields]
    return "\n".join(lines)


def consume(events_path, state_path, sink):
    # One owner of the state/send transition; concurrent consumers must not race.
    with Path(str(state_path) + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _consume(events_path, state_path, sink)


def _consume(events_path, state_path, sink):
    events, incomplete = read_events(events_path)
    state = load_state(state_path)
    done = state["events"]
    result = {
        "delivered": 0,
        "diagnostic": 0,
        "delivery_unknown": 0,
        "pending": 0,
        "incomplete_tail": incomplete,
    }
    blocked = False
    for eid, status in list(done.items()):
        if status == "SENDING":
            done[eid] = "DELIVERY_UNKNOWN"
            result["delivery_unknown"] += 1
    save_state(state_path, state)
    for event in events:
        eid = event["event_id"]
        if eid in done:
            continue
        if blocked:
            result["pending"] += event["type"] in EXECUTED_TYPES and event.get("confirmed") is True
            continue
        if event.get("confirmed") is not True or event["type"] not in EXECUTED_TYPES:
            done[eid] = "DIAGNOSTIC"
            result["diagnostic"] += 1
            save_state(state_path, state)
            continue
        done[eid] = "SENDING"
        save_state(state_path, state)
        try:
            sink.send(card(event))
            done[eid] = "DELIVERED"
            result["delivered"] += 1
        except NotSentError:
            # Keep this and later cards pending, preserving order for the next run.
            del done[eid]
            save_state(state_path, state)
            blocked = True
            result["pending"] += 1
            continue
        except Exception:
            # Network/response errors cannot prove remote rejection.
            done[eid] = "DELIVERY_UNKNOWN"
            result["delivery_unknown"] += 1
        save_state(state_path, state)
    return result


class PrintSink:
    def send(self, text):
        print(text + "\n---")


def main():
    p = argparse.ArgumentParser(
        description="Dry-run B1 outbox consumer; prints cards, sends nothing."
    )
    p.add_argument("--events", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(consume(args.events, args.state, PrintSink())))


if __name__ == "__main__":
    main()
