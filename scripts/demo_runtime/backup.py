"""Consistent SQLite backup, checksum and restore verification; seven local copies."""

from contextlib import closing
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
from tempfile import TemporaryDirectory

BUSY_TIMEOUT_SECONDS = 60
ATTEMPTS = 3
RETRY_DELAY_SECONDS = 20


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("backup_integrity_failed")
        counts = {
            table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("kv", "events", "audit_events")
        }
    return counts


def _copy_once(source, target):
    # One backup step = one read transaction = a consistent snapshot. Page-limited
    # steps are deliberately NOT used: SQLite restarts a stepped backup whenever any other
    # connection (the live sender writes every cycle) modifies the source, so a stepped
    # copy of a >1 GB journal would never finish. In rollback-journal mode the single step
    # holds a read lock; the sender now waits up to 60 s for it (journal.BUSY_TIMEOUT_SECONDS).
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True,
                                 timeout=BUSY_TIMEOUT_SECONDS)) as conn:
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_SECONDS * 1000}")
        with closing(sqlite3.connect(target)) as dest:
            conn.backup(dest)


def backup(source, directory, *, attempts=ATTEMPTS, retry_delay=RETRY_DELAY_SECONDS, sleep=time.sleep):
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = directory / f"demo-{stamp}.sqlite3"
    for attempt in range(1, attempts + 1):
        try:
            _copy_once(source, target)
            break
        except sqlite3.OperationalError:
            # Transient busy/locked source: drop the partial copy, retry, never touch the source.
            target.unlink(missing_ok=True)
            if attempt == attempts:
                raise
            sleep(retry_delay)
    counts = verify(target)
    with TemporaryDirectory(dir=directory) as temp:
        restored = Path(temp) / "restored.sqlite3"
        shutil.copyfile(target, restored)
        if verify(restored) != counts:
            raise ValueError("backup_restore_mismatch")
    manifest = dict(
        file=target.name,
        sha256=_sha256(target),
        tables=counts,
        restore_verified=True,
        captured_utc=stamp,
    )
    target.with_suffix(".json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    # Retain complete cumulative histories in each snapshot. Never prune source.
    for old in sorted(directory.glob("demo-*.sqlite3"))[:-7]:
        old.unlink()
        old.with_suffix(".json").unlink(missing_ok=True)
    return target, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--private-bucket")
    parser.add_argument("--namespace")
    args = parser.parse_args(argv)
    target, manifest = backup(args.journal, args.directory)
    if args.private_bucket:
        if not args.namespace:
            parser.error("--namespace required for private bucket upload")
        # Never create or change bucket ACLs. Verify existing private access first.
        command = [
            "oci",
            "os",
            "bucket",
            "get",
            "--namespace-name",
            args.namespace,
            "--bucket-name",
            args.private_bucket,
        ]
        bucket = json.loads(subprocess.check_output(command, text=True))
        if bucket["data"]["public-access-type"] != "NoPublicAccess":
            raise ValueError("private_bucket_required")
        for path in (target, target.with_suffix(".json")):
            subprocess.run(
                [
                    "oci",
                    "os",
                    "object",
                    "put",
                    "--namespace-name",
                    args.namespace,
                    "--bucket-name",
                    args.private_bucket,
                    "--name",
                    "c22-audit/" + path.name,
                    "--file",
                    str(path),
                ],
                check=True,
            )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
