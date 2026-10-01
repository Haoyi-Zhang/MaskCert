"""Bounded proof-attack battery, not a deployed workload evaluation."""
from common import *
from casegen import base, arbitrary, mkrow
from pcs.producer import (floor_value,floor_transcript,intersect_rows,defects,
                          write_certificate,locate)
from pcs.checker import TranscriptReader,lattice,verify,check_witness
from pcs.model import Invalid,validate,loads
from pcs.oracle import enumerate_counters,replay_audit
from math import gcd
from copy import deepcopy
import argparse,io
p=argparse.ArgumentParser(); p.add_argument('--out'); p.add_argument('--regenerate',action='store_true'); args=p.parse_args()
bounded()
counts=dict(floor_oracles=0,crt_oracles=0,plan_oracles=0,prefix_oracles=0,
            witness_checks=0,certificate_mutations=0,schema_mutations=0,
            feistel_functions=0,feistel_point_checks=0)

def reject(fn):
    try: fn()
    except Invalid: return
    raise AssertionError('invalid input accepted')

for m in range(1,13):
    for n in range(9):
        for a in range(2*m+1):
            for b in range(m+3):
                actual=sum((a*x+b)//m for x in range(n))
                value,steps=floor_transcript(n,m,a,b)
                record=json.dumps([value,steps])
                assert actual==floor_value(n,m,a,b)==value
                assert TranscriptReader([record]).floor(n,m,a,b)==actual
                counts['floor_oracles']+=1

for s in range(1,9):
    for t in range(1,9):
        for r in range(s):
            for q in range(t):
                for lo,hi in ((0,19),(2,17),(7,7)):
                    left=mkrow(0,lo,hi,s,r,[[0,19]])
                    right=mkrow(0,0,19,t,q,[[0,19]])
                    expected=[x for x in range(lo,hi) if x%s==r and x%t==q]
                    for desc in (intersect_rows(left,right,19),lattice([left,right],19)):
                        first,step,num=desc
                        assert [first+step*j for j in range(num)]==expected
                    counts['crt_oracles']+=1

cases=[]
for n in range(1,9):
    for a in range(n):
        if gcd(a,n)!=1: continue
        for b in range(n):
            spec,plan=base(n,a,b,old=2,new=3)
            cases.append(dict(id=f'tiny-{n}-{a}-{b}',declaration=spec,plan=plan))
for i in range(96):
    spec,plan=arbitrary(110300+i,9+(i%56))
    cases.append(dict(id=f'mask-{i:03d}',declaration=spec,plan=plan))

# Deliberately non-partitioning source schedules that are valid after guards.
for name,spec,plan in [
    ('excluded-overlap',
     dict(n=8,a=3,b=1,epochs=[dict(allow=[[0,8]],exclude=[[1,2]])],history=[]),
     dict(context=dict(n=8,a=3,b=1),future=[mkrow(0,0,8,1,0,[[0,1],[2,8]]),
                                          mkrow(0,0,1,1,0,[[0,1],[2,8]])])),
    ('excluded-hole',
     dict(n=8,a=3,b=1,epochs=[dict(allow=[[0,8]],exclude=[[1,2]])],history=[]),
     dict(context=dict(n=8,a=3,b=1),future=[mkrow(0,1,8,1,0,[[0,1],[2,8]])])),
    ('disjoint-guards',
     dict(n=8,a=3,b=1,epochs=[dict(allow=[[0,8]],exclude=[])],history=[]),
     dict(context=dict(n=8,a=3,b=1),future=[mkrow(0,0,8,1,0,[[0,4]]),
                                          mkrow(0,0,8,1,0,[[4,8]])]))]:
    cases.append(dict(id=name,declaration=spec,plan=plan))
    assert defects(spec,plan)==[0]
spec,plan=base(67,5,3,old=3,new=5,epochs=16)
cases.append(dict(id='retry-epochs',declaration=spec,plan=plan))
# Functional faulty plans: not all textual mutations are actual violations.
base_cases=deepcopy(cases[:40])
for item in base_cases:
    for mode in ('remove','duplicate'):
        s=deepcopy(item['declaration']); p=deepcopy(item['plan'])
        if mode=='remove': p['future']=p['future'][:-1]
        else: p['future'].append(deepcopy(p['future'][-1]))
        cases.append(dict(id=item['id']+'-'+mode,declaration=s,plan=p))

if not args.regenerate:
    cases=json.loads((ROOT/'cases'/'validation.json').read_text())
safe=unsafe=0; checks=[]
for item in cases:
    spec,plan=item['declaration'],item['plan']; n=spec['n']
    exact,witness=enumerate_counters(spec,plan)
    assert defects(spec,plan)==exact==replay_audit(spec,plan)
    buffer=io.StringIO(); write_certificate(spec,plan,buffer)
    text=buffer.getvalue(); checked=verify(spec,plan,io.StringIO(text))
    assert list(checked.defects)==exact
    assert locate(spec,plan)==witness
    counts['plan_oracles']+=1
    for prefix in (0,n//2,n):
        assert defects(spec,plan,prefix)==enumerate_counters(spec,plan,prefix)[0]
        counts['prefix_oracles']+=1
    if witness:
        before=io.StringIO(); through=io.StringIO()
        write_certificate(spec,plan,before,witness['counter'])
        write_certificate(spec,plan,through,witness['counter']+1)
        assert check_witness(spec,plan,witness,io.StringIO(text),
                             io.StringIO(before.getvalue()),io.StringIO(through.getvalue()))
        counts['witness_checks']+=1; unsafe+=1
    else: safe+=1
    lines=text.splitlines(keepends=True)
    if checked.calls:
        changed=deepcopy(lines); rec=json.loads(changed[1]); rec[0]+=1
        changed[1]=json.dumps(rec)+'\n'
        reject(lambda: verify(spec,plan,changed)); counts['certificate_mutations']+=1
        changed=deepcopy(lines); rec=json.loads(changed[1]); rec[1][0][0]+=1
        changed[1]=json.dumps(rec)+'\n'
        reject(lambda: verify(spec,plan,changed)); counts['certificate_mutations']+=1
    for malformed in (lines[:-1],lines+['{}\n']):
        reject(lambda: verify(spec,plan,malformed)); counts['certificate_mutations']+=1
    checks.append(dict(id=item['id'],n=n,safe=checked.accepted,defects=exact,
                       certificate_bytes=checked.certificate_bytes,calls=checked.calls))

spec,plan=base(32,3,1)
mutations=[]
for f in ('n','a','b'):
    p=deepcopy(plan); p['context'][f]+=1; mutations.append((spec,p))
s=deepcopy(spec); s['a']=2; p=deepcopy(plan); p['context']['a']=2; mutations.append((s,p))
for field,bad in [('lo',-1),('hi',33),('step',0),('step',65),('residue',64),
                  ('epoch',1),('lo',True),('hi','32'),('lo',33)]:
    p=deepcopy(plan); p['future'][0][field]=bad; mutations.append((spec,p))
for mask in ([[3,3]],[[1,5],[4,8]],[[1,5],[5,8]],[[8,9],[1,2]],[[0,33]]):
    p=deepcopy(plan); p['future'][0]['guard']=mask; mutations.append((spec,p))
p=deepcopy(plan); p['unexpected']=0; mutations.append((spec,p))
for s,p in mutations:
    reject(lambda: validate(s,p)); counts['schema_mutations']+=1
for text in ('{"x":1,"x":2}','{"x":NaN}','{"x":'+('9'*41)+'}'):
    reject(lambda: loads(text)); counts['schema_mutations']+=1

# Two-round Feistel reduction; every Boolean function through 3 input bits.
# F(R) is embedded in the highest bit of the left word. Both rounds are bijective.
feistel=[]
for w in (1,2,3):
    width=1<<w; n=width*width; half=n//2
    for truth in range(1<<width):
        def f(r): return (truth>>r)&1
        outputs=[]; missing=0
        for x in range(n):
            l,r=divmod(x,width)
            # Round F: (r,l xor F(r)); round 0: (l xor F(r),r).
            y=((l^(f(r)<<(w-1)))<<w)|r
            outputs.append(y)
            if x<width and y>=half: missing+=1
            counts['feistel_point_checks']+=1
        assert len(set(outputs))==n
        assert missing==sum(f(r) for r in range(width))
        assert (missing==0)==(truth==0)
        feistel.append(dict(bits=w,truth_table=truth,missing_authorized=missing,
                             accepted=(missing==0)))
        counts['feistel_functions']+=1

# Negative-control ablations: mass alone and raw-index partitioning are insufficient.
ablations=[
    dict(case='mass-cancellation',multiplicities=[2,1,1,0],authorized=[1,1,1,1],
         mass=4,expected=4,defect=2,count_only_accepts=True,correct_accepts=False),
    dict(case='excluded-overlap',raw_partition_accepts=False,correct_accepts=True),
    dict(case='excluded-hole',raw_partition_accepts=False,correct_accepts=True),
    dict(case='disjoint-guards',raw_partition_accepts=False,correct_accepts=True)]
if args.regenerate:
    (ROOT/'cases'/'validation.json').write_text(json.dumps(cases,separators=(',',':'))+'\n')
(ROOT/'results'/'validation-cases.json').write_text(json.dumps(checks,indent=2)+'\n')
(ROOT/'results'/'feistel-cases.json').write_text(json.dumps(feistel,indent=2)+'\n')
(ROOT/'results'/'ablations.json').write_text(json.dumps(ablations,indent=2)+'\n')
finish('validation.json',dict(seed=110300,counts=counts,safe=safe,unsafe=unsafe,
     affine_case_records=len(cases),all_checks_passed=True,
     obligation_count=sum(v for k,v in counts.items() if k!='feistel_point_checks')),
     args.out)
