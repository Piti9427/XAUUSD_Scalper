"""Build auditable Pine calendar data from normalized Trading Economics rows."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Iterable, Mapping


@dataclass(frozen=True)
class CalendarArtifact:
    pine: str
    sha256: str
    event_count: int
    coverage_start_utc: datetime
    coverage_end_utc: datetime


def _parse_utc(value: str | datetime) -> datetime:
    parsed = (
        datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("event_time_utc must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def build_calendar_artifact(
    rows: Iterable[Mapping], coverage_start_utc: datetime, coverage_end_utc: datetime
) -> CalendarArtifact:
    start, end = _parse_utc(coverage_start_utc), _parse_utc(coverage_end_utc)
    if end < start:
        raise ValueError("calendar coverage end precedes start")
    normalized = []
    ids = set()
    for row in rows:
        event_time = _parse_utc(row["event_time_utc"])
        if str(row["currency"]).upper() != "USD" or int(row["impact"]) != 3:
            continue
        if not start <= event_time <= end:
            raise ValueError("high-impact USD event lies outside declared coverage")
        event_id = str(row["event_id"])
        if event_id in ids:
            raise ValueError(f"duplicate event_id: {event_id}")
        ids.add(event_id)
        normalized.append(
            {
                "event_id": event_id,
                "event_time_utc": event_time.isoformat(),
                "title": str(row["title"]),
            }
        )
    normalized.sort(key=lambda row: (row["event_time_utc"], row["event_id"]))
    lines = [
        "// Generated Trading Economics USD high-impact calendar. UTC only.",
        "var int[] newsUtc = array.new_int()",
        "if barstate.isfirst",
    ]
    for row in normalized:
        dt = _parse_utc(row["event_time_utc"])
        lines.append(
            f'    array.push(newsUtc, timestamp("UTC", {dt.year}, {dt.month}, {dt.day}, {dt.hour}, {dt.minute})) // {row["event_id"]}'
        )
    canonical = json.dumps(
        {
            "coverage_start_utc": start.isoformat(),
            "coverage_end_utc": end.isoformat(),
            "events": normalized,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return CalendarArtifact(
        "\n".join(lines) + "\n",
        hashlib.sha256(canonical.encode()).hexdigest(),
        len(normalized),
        start,
        end,
    )
