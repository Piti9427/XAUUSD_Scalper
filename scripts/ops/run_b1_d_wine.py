"""Invoke a repository read-only capture/probe using Wine Python and ignored .env."""
import argparse
import os
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--script',default='scripts/ops/b1_d_demo_probe.py')
    parser.add_argument('--output',default='data/b1_d_demo_connection_2026-09-26.json')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    env=os.environ.copy()
    for line in (root/'.env').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key,value=line.split('=',1);env[key.strip()]=value.strip().strip('\"\'')
    env['WINEPREFIX']=str(Path.home()/'Library/Application Support/net.metaquotes.wine.metatrader5')
    env['WINEDLLOVERRIDES']='mscoree,mshtml='
    env['XAUUSD_PROBE_OUTPUT']='Z:'+str(root/args.output).replace('/','\\')
    env['XAUUSD_REPO_ROOT']='Z:'+str(root).replace('/','\\')
    env['PYTHONPATH']=env['XAUUSD_REPO_ROOT']
    cmd=['/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine',r'C:\tools\python312\python.exe','-u','Z:'+str(root/args.script).replace('/','\\')]
    p=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    secrets=[v for k,v in env.items() if any(x in k for x in ('PASSWORD','TOKEN','LOGIN')) and v]
    for line in p.stdout:
        for secret in secrets: line=line.replace(secret,'<REDACTED>')
        print(line,end='',flush=True)
    return p.wait()

if __name__=='__main__':
    raise SystemExit(main())
