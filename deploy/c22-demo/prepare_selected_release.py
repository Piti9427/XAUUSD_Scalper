"""Create a deterministic shadow-only release; no network or activation."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile


def build_release(root: Path, output: Path) -> dict:
    root, output = root.resolve(), output.resolve()
    if not output.is_relative_to(root / "runs") or output.exists():
        raise ValueError("Use a new ignored runs/ output directory")
    old = json.loads((root / "runs/c22-oracle-compat-2026-10-24/phase2-evidence/release-manifest.json").read_text())
    names = set(old["files"])
    names.update(str(path.relative_to(root)) for path in (root / "scripts/c22_selected").glob("*.py"))
    names.update({"config/c22-selected-demo.json", "scripts/ops/mt5_wine_c22_selected.py"})
    payload = {}
    for name in sorted(names):
        path = root / name
        if (not path.resolve().is_relative_to(root) or path.is_symlink()
                or path.suffix not in (".py", ".json") or not name.startswith(("scripts/", "config/", "deploy/"))):
            raise ValueError("Release path not permitted: " + name)
        payload[name] = path.read_bytes()
    config = json.loads(payload["config/c22-selected-demo.json"])
    if (config.get("contract_id") != "26b8bcd69e043653" or config.get("volume") != 0.01
            or config.get("real_money") != "PROHIBITED" or config.get("default_mode") != "shadow"):
        raise ValueError("Selected shadow config mismatch")
    for name, digest in config["source_hashes"].items():
        if name not in payload or hashlib.sha256(payload[name]).hexdigest() != digest:
            raise ValueError("Selected source binding mismatch: " + name)
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in payload.items()}
    release_id = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16]
    remote = "/home/ubuntu/c22-demo/releases/selected-" + release_id
    unit = f'''[Unit]
Description=Selected C22 26b8 Demo shadow (orders disabled)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Type=simple
User=ubuntu
WorkingDirectory={remote}
EnvironmentFile=/home/ubuntu/c22-private/c22-shadow.env
Environment=DEMO_TELEGRAM_TOKEN= DEMO_TELEGRAM_CHAT_ID= DEMO_HEALTHCHECK_URL=
UnsetEnvironment=DEMO_TELEGRAM_TOKEN DEMO_TELEGRAM_CHAT_ID DEMO_HEALTHCHECK_URL
ExecStartPre=/usr/bin/sha256sum --check --status release.sha256
ExecStartPre=/bin/sh -c '! systemctl is-active --quiet c22-demo-shadow.service && ! systemctl is-active --quiet c22-demo-execution.service'
ExecStartPre=/bin/sh -c 'test "$(readlink -f data)" = /home/ubuntu/c22-demo/releases/d091bc6b810e792c/data'
ExecStart=/usr/bin/env MT5_ENABLE_DEMO_ORDER_SEND=0 /usr/bin/xvfb-run -a ${{DEMO_WINE_BIN}} ${{DEMO_WINDOWS_PYTHON}} -u Z:{remote}/scripts/ops/mt5_wine_c22_selected.py --watch --initialize-timeout-ms 90000 --journal Z:/home/ubuntu/c22-demo/state/c22-selected-shadow.sqlite3 --cost-policy Z:/home/ubuntu/c22-demo/state/cost-policy-runtime.json --cache-output Z:/home/ubuntu/c22-demo/state/c22-selected-shadow-bars.csv
Restart=on-failure
RestartSec=10
KillSignal=SIGINT
KillMode=control-group
TimeoutStopSec=30
UMask=0077
NoNewPrivileges=true
Nice=5

[Install]
WantedBy=multi-user.target
'''
    payload["c22-selected-shadow.service"] = unit.encode()
    hashes["c22-selected-shadow.service"] = hashlib.sha256(unit.encode()).hexdigest()
    drift = [name for name, expected in old["files"].items() if hashes[name] != expected]
    manifest = {"release_id": release_id, "files": hashes, "changed_from_old_release": drift,
                "mode": "shadow-only", "execution_authorized": False, "remote_release": remote}
    payload["release-manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    checks = hashes | {"release-manifest.json": hashlib.sha256(payload["release-manifest.json"]).hexdigest()}
    payload["release.sha256"] = "".join(f"{digest}  {name}\n" for name, digest in sorted(checks.items())).encode()
    archive = io.BytesIO()
    with gzip.GzipFile(fileobj=archive, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as tar:
            for name, content in sorted(payload.items()):
                info = tarfile.TarInfo(name)
                info.size, info.mtime, info.mode = len(content), 0, 0o644
                tar.addfile(info, io.BytesIO(content))
    output.mkdir(parents=True)
    archive_bytes = archive.getvalue()
    (output / "release.tar.gz").write_bytes(archive_bytes)
    for name in ("release-manifest.json", "release.sha256", "c22-selected-shadow.service"):
        (output / name).write_bytes(payload[name])
    result = manifest | {"archive_sha256": hashlib.sha256(archive_bytes).hexdigest(), "archive": str(output / "release.tar.gz")}
    (output / "build.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_release(args.root, args.out)))
