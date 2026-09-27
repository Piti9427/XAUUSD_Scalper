"""Compile MQL5 sources and run the local MT5 Strategy Tester through Wine.

The Strategy Tester simulates orders against historical broker data; this tool
never attaches an EA to a live chart. Credentials are not read: the terminal
reuses its saved login. A running terminal must be closed first because MT5
allows one instance per data folder.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5"
WINE = Path("/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine")
TERMINAL_DIR = PREFIX / "drive_c/Program Files/MetaTrader 5"
EXPERT_SUBDIR = "B1Final"
AGENT_FILES = TERMINAL_DIR / "Tester/Agent-127.0.0.1-3000/MQL5/Files"
MODELS = {"every_tick": 0, "ohlc_m1": 1, "open_prices": 2, "real_ticks": 4}


def win_path(path):
    path = Path(path).resolve()
    drive_c = (PREFIX / "drive_c").resolve()
    if path.is_relative_to(drive_c):
        return "C:\\" + str(path.relative_to(drive_c)).replace("/", "\\")
    return "Z:" + str(path).replace("/", "\\")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tester_ini(
    expert,
    symbol,
    period,
    model,
    start,
    end,
    deposit,
    leverage,
    report,
    set_file=None,
    delay_ms=0,
    currency="USD",
):
    """Return a Tester config; dates are MT5 `YYYY.MM.DD` strings."""
    if model not in MODELS.values():
        raise ValueError("unknown tester model")
    if not (deposit > 0 and leverage > 0 and delay_ms >= 0):
        raise ValueError("invalid tester economics")
    lines = [
        "[Tester]",
        f"Expert={EXPERT_SUBDIR}\\{expert}.ex5",
        f"Symbol={symbol}",
        f"Period={period}",
        "Optimization=0",
        f"Model={model}",
        f"FromDate={start}",
        f"ToDate={end}",
        "ForwardMode=0",
        f"Deposit={deposit:.2f}",
        f"Currency={currency}",
        "ProfitInPips=0",
        f"Leverage=1:{int(leverage)}",
        f"ExecutionMode={int(delay_ms)}",
        "Visual=0",
        f"Report={report}",
        "ReplaceReport=1",
        "ShutdownTerminal=1",
        "UseLocal=1",
        "UseRemote=0",
        "UseCloud=0",
    ]
    if set_file:
        lines.append(f"ExpertParameters={set_file}")
    return "\r\n".join(lines) + "\r\n"


def set_file_text(params):
    """MT5 .set format: name=value per line; values must not contain newlines."""
    out = []
    for key, value in params.items():
        text = str(value).lower() if isinstance(value, bool) else str(value)
        if "\n" in text or "=" in key:
            raise ValueError("invalid expert parameter")
        out.append(f"{key}={text}")
    return "\r\n".join(out) + "\r\n"


def load_env(path):
    values = {}
    if Path(path).is_file():
        for line in Path(path).read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip("\"'")
    return values


def resolve_params(params, env):
    """`env:NAME` values come from the ignored .env and are redacted in shared artifacts."""
    resolved, shared = {}, {}
    for key, value in params.items():
        if value.startswith("env:"):
            name = value[4:]
            if name not in env:
                raise SystemExit(f"missing private setting {name}")
            resolved[key], shared[key] = env[name], f"<{name}>"
        else:
            resolved[key] = shared[key] = value
    return resolved, shared


def run_segment(log_text):
    """Agent logs accumulate per day; keep lines from the last test start."""
    lines = log_text.splitlines()
    starts = [i for i, line in enumerate(lines) if "login (build" in line]
    return "\n".join(lines[starts[-1] if starts else 0 :]) + "\n"


def redact(text, env):
    for key, value in env.items():
        if value and any(tag in key for tag in ("LOGIN", "PASSWORD", "TOKEN", "SERVER")):
            text = text.replace(value, f"<{key}>")
    return text


def wine_env():
    env = os.environ.copy()
    env["WINEPREFIX"] = str(PREFIX)
    env["WINEDLLOVERRIDES"] = "mscoree,mshtml="
    return env


def compile_sources(sources, main):
    """Compile `main` and install the binary under MQL5/Experts/B1Final.

    MetaEditor's command line cannot take paths containing spaces, so builds
    happen in a space-free directory inside the Wine prefix.
    """
    build = PREFIX / "drive_c/b1build"
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    for src in sources:
        shutil.copy2(src, build / Path(src).name)
    log = build / (Path(main).stem + ".compile.log")
    subprocess.run(
        [
            str(WINE),
            str(TERMINAL_DIR / "metaeditor64.exe"),
            f"/compile:{win_path(build / Path(main).name)}",
            f"/log:{win_path(log)}",
        ],
        env=wine_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    text = log.read_bytes().decode("utf-16", errors="replace") if log.exists() else ""
    built = build / (Path(main).stem + ".ex5")
    ok = "Result: 0 errors" in text and built.exists()
    dest = TERMINAL_DIR / "MQL5/Experts" / EXPERT_SUBDIR
    dest.mkdir(parents=True, exist_ok=True)
    if ok:
        shutil.copy2(built, dest / built.name)
    return ok, text, dest / built.name


def tester_finished(since):
    logs = sorted((TERMINAL_DIR / "Tester/logs").glob("*.log"))
    if not logs or logs[-1].stat().st_mtime < since:
        return False
    return (
        "thread finished"
        in logs[-1].read_bytes().decode("utf-16", errors="replace").splitlines()[-1]
    )


def terminal_running():
    probe = subprocess.run(["pgrep", "-f", "terminal64.exe"], capture_output=True, text=True)
    return bool(probe.stdout.strip())


def run_tester(args):
    if terminal_running():
        raise SystemExit("terminal64.exe already running; close it before a Tester run")
    out = Path(args.output)
    if out.exists():
        raise SystemExit(f"output exists: {out}")
    sources = [ROOT / "mql5" / name for name in args.sources]
    ok, log, binary = compile_sources(sources, args.expert + ".mq5")
    if not ok:
        print(log)
        raise SystemExit("COMPILE_FAILED")
    if AGENT_FILES.exists():
        shutil.rmtree(AGENT_FILES)
    # Tester copies `#property tester_file` inputs from terminal MQL5/Files into the agent sandbox.
    for spec in args.input_file:
        local, _, name = spec.partition(":")
        shutil.copy2(local, TERMINAL_DIR / "MQL5/Files" / (name or Path(local).name))
    params = dict(p.split("=", 1) for p in args.param)
    resolved, shared = resolve_params(params, load_env(ROOT / ".env"))
    set_name = None
    if params:
        set_name = f"{args.expert}_run.set"
        profile = TERMINAL_DIR / "MQL5/Profiles/Tester" / set_name
        profile.write_text(set_file_text(resolved), encoding="utf-16")
    (TERMINAL_DIR / "reports").mkdir(exist_ok=True)
    report = f"reports\\{out.name}"
    ini = tester_ini(
        args.expert,
        args.symbol,
        args.period,
        MODELS[args.model],
        args.start,
        args.end,
        args.deposit,
        args.leverage,
        report,
        set_name,
        args.delay_ms,
    )
    config = TERMINAL_DIR / "config" / "b1_tester_run.ini"
    config.write_text(ini, encoding="utf-16")
    started = time.time()
    proc = subprocess.Popen(
        [str(WINE), str(TERMINAL_DIR / "terminal64.exe"), f"/config:{win_path(config)}"],
        env=wine_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    finished_at = None
    forced = False
    time.sleep(5)
    while proc.poll() is None or terminal_running():
        if time.time() - started > args.timeout:
            raise SystemExit("TESTER_TIMEOUT")
        if finished_at is None and tester_finished(started):
            finished_at = time.time()
        # MT5 under Wine sometimes never exits after a finished test.
        if finished_at is not None and time.time() - finished_at > 60:
            subprocess.run(
                [str(WINE), "taskkill", "/F", "/IM", "terminal64.exe"],
                env=wine_env(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            forced = True
            time.sleep(10)
        time.sleep(5)
    partial = out.with_name(out.name + ".partial")
    partial.mkdir(parents=True)
    # Compiles are not byte-reproducible; keep the exact binary that was tested.
    shutil.copy2(binary, partial / binary.name)
    collected = [binary.name]
    for path in AGENT_FILES.glob("*"):
        shutil.copy2(path, partial / path.name)
        collected.append(path.name)
    for suffix in (".htm", ".html", ".xml", ".png"):
        for path in (
            (TERMINAL_DIR / "reports").glob(out.name + "*" + suffix)
            if (TERMINAL_DIR / "reports").exists()
            else []
        ):
            shutil.copy2(path, partial / path.name)
            collected.append(path.name)
    agent_logs = sorted((AGENT_FILES.parents[1] / "logs").glob("*.log"))
    if agent_logs:
        journal = run_segment(agent_logs[-1].read_bytes().decode("utf-16", errors="replace"))
        (partial / "agent_journal.log").write_text(redact(journal, load_env(ROOT / ".env")))
    manifest = {
        "expert": args.expert,
        "symbol": args.symbol,
        "period": args.period,
        "model": args.model,
        "from": args.start,
        "to": args.end,
        "deposit": args.deposit,
        "leverage": args.leverage,
        "delay_ms": args.delay_ms,
        "params": shared,
        "terminal_exit_code": proc.returncode,
        "terminal_force_closed_after_finish": forced,
        "elapsed_seconds": round(time.time() - started, 1),
        "collected": sorted(collected),
        "source_sha256": {p.name: sha256(p) for p in sources},
        "binary_sha256": sha256(binary),
        "tester": "MT5 Strategy Tester (simulated orders)",
        "live_orders_sent": False,
    }
    (partial / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    partial.rename(out)
    print(json.dumps(manifest, indent=2))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compile")
    c.add_argument("expert")
    c.add_argument("--sources", nargs="+", required=True)
    r = sub.add_parser("run")
    r.add_argument("expert")
    r.add_argument("--sources", nargs="+", required=True)
    r.add_argument("--output", required=True)
    r.add_argument("--symbol", default="XAUUSDm")
    r.add_argument("--period", default="M15")
    r.add_argument("--model", choices=sorted(MODELS), default="real_ticks")
    r.add_argument("--start", required=True)
    r.add_argument("--end", required=True)
    r.add_argument("--deposit", type=float, required=True)
    r.add_argument("--leverage", type=int, default=1000)
    r.add_argument("--delay-ms", type=int, default=0)
    r.add_argument("--param", action="append", default=[])
    r.add_argument("--input-file", action="append", default=[])
    r.add_argument("--timeout", type=int, default=7200)
    args = p.parse_args()
    if args.cmd == "compile":
        ok, log, binary = compile_sources(
            [ROOT / "mql5" / n for n in args.sources], args.expert + ".mq5"
        )
        print(log.strip().splitlines()[-1] if log.strip() else "NO_LOG")
        if ok:
            print(json.dumps({"binary_sha256": sha256(binary)}))
        raise SystemExit(0 if ok else 1)
    run_tester(args)


if __name__ == "__main__":
    main()
