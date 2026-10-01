"""Declared boundary cases; not representative scanner workloads."""
from common import *
from casegen import mkrow,base
from pcs.producer import write_certificate,defects
from pcs.checker import verify
from pcs.model import certificate_lines, EXPLICIT_ORACLE_LIMIT
from pcs.oracle import enumerate_counters,replay_audit
import time
bounded()
n=1<<32; block=n//1024
excluded=[[block*(i+1)-16,block*(i+1)] for i in range(1024)]
guards=[[block*i,block*(i+1)-16] for i in range(1024)]
cut=n//3
spec=dict(n=n,a=n-1,b=n-2,epochs=[dict(allow=[[0,n]],exclude=excluded)],
          history=[mkrow(0,0,cut,61,r,guards) for r in range(61)])
plan=dict(context=dict(n=n,a=n-1,b=n-2),
          future=[mkrow(0,cut,n,64,r,guards) for r in range(64)])
case=dict(id='bounded-mask',declaration=spec,plan=plan)
(ROOT/'cases'/'boundary.json').write_text(json.dumps(case,separators=(',',':'))+'\n')
path=ROOT/'results'/'boundary-certificate.jsonl'
t=time.process_time()
with path.open('w') as out:
    ds=write_certificate(spec,plan,out)
produce=time.process_time()-t
print(json.dumps({'stage':'produced','cpu_seconds':produce}),flush=True)
assert ds==[0]
t=time.process_time();checked=verify(spec,plan,certificate_lines(path));check=time.process_time()-t
assert checked.accepted
print(json.dumps({'stage':'checked','cpu_seconds':check}),flush=True)
# A separate maximum allowed exact truth domain, with low row count.
s,p=base(EXPLICIT_ORACLE_LIMIT,65537,3,old=1,new=1)
truthcase=dict(id='exact-limit',declaration=s,plan=p)
(ROOT/'cases'/'exact-limit.json').write_text(json.dumps(truthcase,separators=(',',':'))+'\n')
t=time.process_time();x,w=enumerate_counters(s,p);enumeration=time.process_time()-t
assert x==[0] and w is None
t=time.process_time();y=replay_audit(s,p);replay=time.process_time()-t
assert y==x==defects(s,p)
finish('boundary.json',dict(all_checks_passed=True,
 symbolic=dict(n=n,rows=125,old_shards=61,new_shards=64,exclusions=1024,
               guard_intervals=1024,certificate_bytes=checked.certificate_bytes,
               floor_calls=checked.calls,euclidean_steps=checked.steps,
               producer_cpu_seconds=produce,checker_cpu_seconds=check,defects=ds),
 exact=dict(n=EXPLICIT_ORACLE_LIMIT,rows=2,defects=x,enumeration_cpu_seconds=enumeration,
            replay_cpu_seconds=replay),case_records=2))
