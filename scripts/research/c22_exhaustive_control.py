"""Start or inspect the fixed offline research process; no trading interfaces."""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'runs/c22-exhaustive-loop-2026-10-25'
SCRIPT = ROOT/'scripts/research/c22_exhaustive_loop.py'


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def write(path, value):
    pending=path.with_suffix(path.suffix+'.pending')
    pending.write_text(json.dumps(value,indent=2)+'\n')
    pending.replace(path)


def status():
    record=read(OUT/'process.json')
    alive=False
    if (OUT/'.lock').exists():
        with (OUT/'.lock').open('a+b') as campaign:
            try:
                fcntl.flock(campaign.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                fcntl.flock(campaign.fileno(),fcntl.LOCK_UN)
            except BlockingIOError:
                alive=True
    progress=read(OUT/'progress.json')
    complete=read(OUT/'COMPLETE.json')
    return dict(process_alive=alive,status_evidence='exclusive campaign lock',process=record,progress=progress,
                complete=({k:v for k,v in complete.items() if k!='artifacts'} if complete else None))


def start(workers):
    if workers not in (1,2,3,4):
        raise ValueError('Require1–4workers')
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'.process-control.lock').open('a+b') as control:
        fcntl.flock(control.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        current=status()
        if current['complete'] or current['process_alive']:
            return dict(action='UNCHANGED',**current)
        # The campaign lock also covers a process started outside this helper.
        with (OUT/'.lock').open('a+b') as campaign:
            try:
                fcntl.flock(campaign.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:
                return dict(action='CAMPAIGN_LOCKED',**current)
            fcntl.flock(campaign.fileno(),fcntl.LOCK_UN)
        if not SCRIPT.is_file():
            raise FileNotFoundError(SCRIPT)
        command=[sys.executable,'-u',str(SCRIPT),'--workers',str(workers)]
        environment=dict(os.environ,PYTHONPATH=str(ROOT))
        with (OUT/'execution.log').open('ab',buffering=0) as log:
            process=subprocess.Popen(command,cwd=ROOT,env=environment,stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
        record=dict(pid=process.pid,started_utc=datetime.now(timezone.utc).isoformat(),
                    command=command,offline_research_only=True)
        write(OUT/'process.json',record)
        return dict(action='STARTED',process=record)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('status','start'))
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    print(json.dumps(start(args.workers) if args.action=='start' else status(),indent=2))


if __name__=='__main__':
    main()
