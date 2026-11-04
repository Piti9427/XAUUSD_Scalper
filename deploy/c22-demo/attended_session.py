"""Manual Mac console and verified off-VM snapshot; never start/stop a sender.

Run --watch only while an operator is present. Mac sleep, process exit or loss
of network ends observation. This is not an unattended alerting service.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

SSH = [
    "ssh",
    "-o",
    "BatchMode=yes",
    "-o",
    "IdentitiesOnly=yes",
    "-o",
    "StrictHostKeyChecking=yes",
    "-o",
    "UpdateHostKeys=no",
    "-o",
    "ConnectTimeout=10",
]
HOST = "ubuntu@158.178.243.98"
REMOTE_STATUS = r"""
import json,sqlite3,pathlib,subprocess,datetime
h=pathlib.Path.home()
conn=sqlite3.connect((h/'c22-demo/state/c22h4-shadow.sqlite3').as_uri()+'?mode=ro',uri=True)
conn.execute('PRAGMA query_only=ON'); conn.execute('BEGIN')
v={k:json.loads(p) for k,p in conn.execute('select key,value from kv')}
units={u:subprocess.run(['systemctl','is-active',u],capture_output=True,text=True).stdout.strip()
       for u in ('c22-demo-shadow.service','c22-demo-execution.service')}
print(json.dumps(dict(captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 last_result=v.get('last_result'),active=bool(v.get('active')),safety_halt=v.get('safety_halt'),
 pending_outbox=conn.execute('select count(*) from events where sent=0').fetchone()[0],
 units=units)))
conn.close()
"""


def classify(value):
    last = value.get("last_result") or {}
    try:
        stamp, now = (
            datetime.fromisoformat(v) for v in (last["captured_utc"], value["captured_utc"])
        )
        age = (now - stamp).total_seconds()
        fresh = stamp.tzinfo is not None and now.tzinfo is not None and 0 <= age <= 15
    except (ValueError, KeyError, TypeError):
        fresh = False
    if not fresh or last.get("critical") or last.get("position_protection") == "unknown":
        return "ATTENTION_PROTECTION_OR_HEARTBEAT"
    units = value.get("units", {})
    expected = "c22-demo-execution.service" if last.get("execute") else "c22-demo-shadow.service"
    if units.get(expected) != "active" or all(v == "active" for v in units.values()):
        return "ATTENTION_SERVICE_OWNERSHIP"
    if value.get("safety_halt"):
        return "ATTENTION_SAFETY_HALT"
    if last.get("position_protection") == "confirmed" and value.get("active"):
        return "POSITION_MANAGED"
    if last.get("status") == "BLOCKED":
        return "ENTRY_BLOCKED:" + str(last.get("reason"))
    return "WAITING_FOR_STRATEGY" if not value.get("active") else "ATTENTION_POSITION_STATE"


def snapshot(ssh, directory):
    # The existing installed backup service uses the writer's Windows SQLite.
    script = r"""
import subprocess,pathlib,json,hashlib
subprocess.run(['sudo','-n','systemctl','start','c22-demo-backup.service'],check=True,timeout=120)
p=sorted((pathlib.Path.home()/'c22-demo/backups').glob('demo-*.json'))[-1]
m=json.loads(p.read_text());b=p.with_suffix('.sqlite3')
assert m['restore_verified'] and hashlib.sha256(b.read_bytes()).hexdigest()==m['sha256']
print(json.dumps(dict(name=b.name,sha256=m['sha256'],tables=m['tables'])))
"""
    result = subprocess.run(
        ssh + [HOST, "python3 -"],
        input=script,
        text=True,
        capture_output=True,
        check=True,
        timeout=150,
    )
    meta = json.loads(result.stdout)
    name = meta["name"]
    if Path(name).name != name or not name.startswith("demo-") or not name.endswith(".sqlite3"):
        raise ValueError("unexpected backup name")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / name
    if target.exists():
        raise ValueError("snapshot already exists; never overwrite financial evidence")
    # Reuse pinned SSH arguments; remote path contains only a checked generated basename.
    with target.open("xb") as handle:
        target.chmod(0o600)
        subprocess.run(
            ssh + [HOST, "cat /home/ubuntu/c22-demo/backups/" + name],
            stdout=handle,
            check=True,
            timeout=60,
        )
    if hashlib.sha256(target.read_bytes()).hexdigest() != meta["sha256"]:
        raise ValueError("download checksum mismatch; retain failed copy for diagnosis")
    conn = sqlite3.connect(target.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("off-host restore integrity failed")
        for table, expected in meta["tables"].items():
            if (
                table not in ("kv", "events", "audit_events")
                or conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] != expected
            ):
                raise ValueError("off-host restore table mismatch")
    finally:
        conn.close()
    meta.update(off_host_restore_verified=True)
    target.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n")
    target.with_suffix(".json").chmod(0o600)
    return meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--key", type=Path, default=Path("/Users/nopparuj/ssh-keys/ssh-key-2026-06-16.key")
    )
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args(argv)
    ssh = SSH + ["-i", str(args.key)]
    if args.snapshot:
        print(json.dumps(snapshot(ssh, args.snapshot)))
    while True:
        try:
            proc = subprocess.run(
                ssh + [HOST, "python3 -"],
                input=REMOTE_STATUS,
                text=True,
                capture_output=True,
                check=True,
                timeout=20,
            )
            value = json.loads(proc.stdout)
            result = dict(status=classify(value), **value)
        except (subprocess.SubprocessError, ValueError, OSError) as exc:
            result = dict(
                status="ATTENTION_MONITOR_CONNECTION_LOST",
                error=type(exc).__name__,
                captured_utc=datetime.now(timezone.utc).isoformat(),
            )
        print(json.dumps(result), flush=True)
        if result["status"].startswith("ATTENTION"):
            print("\a", end="", flush=True)
        if not args.watch:
            return 2 if result["status"].startswith("ATTENTION") else 0
        time.sleep(10)


if __name__ == "__main__":
    raise SystemExit(main())
