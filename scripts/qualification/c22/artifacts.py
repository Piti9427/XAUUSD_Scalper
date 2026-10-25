"""Strict, provenance-bearing offline artifacts shared by preparation tools."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> Any:
    raise ValueError(f"Nonfinite JSON value: {value}")


def read_json(path: Path) -> Any:
    """Read evidence without silently accepting duplicate keys or NaN."""
    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=_invalid_constant,
    )


def parse_utc(value: str) -> datetime:
    """Require an aware timestamp and normalize to UTC."""
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an aware ISO8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Naive timestamp is not evidence")
    return parsed.astimezone(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_ref(path: Path, *, max_bytes: int = 32 * 1024 * 1024) -> dict[str, Any]:
    """Hash small artifacts; explicitly leave large input hashes unverified."""
    path = Path(path).resolve()
    stat = path.stat()
    hashed = stat.st_size <= max_bytes
    return {
        "path": str(path),
        "sha256": sha256_file(path) if hashed else None,
        "size_bytes": stat.st_size,
        "hash_limit_bytes": max_bytes,
        "hash_status": "VERIFIED" if hashed else "NOT_HASHED_SIZE_LIMIT",
    }


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def make_report(
    kind: str,
    status: str,
    *,
    sources: list[dict[str, Any]],
    coverage: dict[str, Any],
    reasons: list[str],
    candidate_id: str | None = None,
    cohort_id: str | None = None,
    **details: Any,
) -> dict[str, Any]:
    result = {
        "schema_version": 1,
        "artifact_type": kind,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "candidate_id": candidate_id,
        "cohort_id": cohort_id,
        "sources": sources,
        "coverage": coverage,
        "reasons": reasons,
        "data": details,
        "execution_authorized": False,
    }
    json.dumps(result, allow_nan=False)
    return result


def write_json(path: Path, value: Any) -> None:
    """Create a new artifact; never replace existing evidence."""
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_text(path: Path, value: str) -> None:
    """Create a new UTF8 artifact with exclusive creation and durable flush."""
    payload = value.encode("utf-8")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
