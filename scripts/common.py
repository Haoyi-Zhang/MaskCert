from __future__ import annotations
import json, os, resource, signal, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
START=time.process_time()

def bounded():
    if hasattr(os,'sched_setaffinity'):
        os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS,(2500*1024*1024,2500*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(110,115))
    signal.alarm(115)

def finish(name,payload,destination=None):
    payload=dict(payload,cpu_seconds=time.process_time()-START,
                 peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 workers=1)
    out=Path(destination) if destination else ROOT/'results'/name
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload,sort_keys=True))
    return payload
