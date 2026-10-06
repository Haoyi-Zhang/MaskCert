from __future__ import annotations
import json, os, platform, signal, sys, time
try:
    import resource
except ImportError:
    resource = None
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
START=time.process_time()

def bounded():
    if resource is None:
        # The portable repair driver supplies an outer wall bound. Do not
        # silently pretend that POSIX CPU/memory/alarm controls were applied.
        if os.environ.get('PCS_PORTABLE_BOUNDED_CHILD') != '1':
            raise RuntimeError('POSIX resource controls unavailable; use the bounded portable repair driver')
        return
    if hasattr(os,'sched_setaffinity'):
        os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS,(2500*1024*1024,2500*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(110,115))
    signal.alarm(115)

def peak_rss_kib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource is not None else None

def resource_observation():
    if resource is not None:
        return {}
    return {'host': {'platform': platform.platform(), 'python': sys.version,
                     'executable': sys.executable},
            'resource_controls': {'posix_cpu_limit': False, 'address_space_cap': False,
                                  'alarm': False, 'affinity': False,
                                  'outer_wall_limit_seconds': 120,
                                  'peak_rss_measured': False}}

def finish(name,payload,destination=None):
    payload=dict(payload,cpu_seconds=time.process_time()-START,
                 peak_rss_kib=peak_rss_kib(), workers=1, **resource_observation())
    out=Path(destination) if destination else ROOT/'results'/name
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2)+'\n')
    print(json.dumps(payload,sort_keys=True))
    return payload
