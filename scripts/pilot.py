from common import *
from casegen import base,arbitrary,mkrow
from pcs.producer import defects,write_certificate,locate
from pcs.checker import verify,check_witness
from pcs.oracle import enumerate_counters,replay_audit
from copy import deepcopy
import io
bounded()
pilot_cases=json.loads((ROOT/'cases'/'pilot.json').read_text())
rows=[]
# Both arbitrary unsafe cases and changed-modulus safe resumptions.
for j in range(24):
    spec,plan=pilot_cases[j]['declaration'],pilot_cases[j]['plan']
    exact,witness=enumerate_counters(spec,plan)
    symbolic=defects(spec,plan)
    stream=io.StringIO(); generated=write_certificate(spec,plan,stream)
    checked=verify(spec,plan,io.StringIO(stream.getvalue()))
    assert exact==symbolic==generated==list(checked.defects)==replay_audit(spec,plan)
    assert locate(spec,plan)==witness
    if witness:
        before=io.StringIO(); through=io.StringIO()
        write_certificate(spec,plan,before,witness['counter'])
        write_certificate(spec,plan,through,witness['counter']+1)
        assert check_witness(spec,plan,witness,io.StringIO(stream.getvalue()),
                             io.StringIO(before.getvalue()),io.StringIO(through.getvalue()))
    rows.append(dict(case=j,n=spec['n'],rows=len(spec['history'])+len(plan['future']),
                     accepted=checked.accepted,defects=exact,
                     certificate_bytes=checked.certificate_bytes,calls=checked.calls,steps=checked.steps))
# The largest symbolic domain, 64 shard residues, and the 32-bit arithmetic boundary.
spec,plan=pilot_cases[24]['declaration'],pilot_cases[24]['plan']
t=time.process_time(); stream=io.StringIO(); write_certificate(spec,plan,stream)
t1=time.process_time(); checked=verify(spec,plan,io.StringIO(stream.getvalue())); t2=time.process_time()
assert checked.accepted
# A missing+duplicated slot keeps the total count unchanged but must be rejected.
negative_spec=dict(n=4,a=1,b=0,epochs=[dict(allow=[[0,4]],exclude=[])],history=[])
negative_plan=dict(context=dict(n=4,a=1,b=0),future=[mkrow(0,0,3,1,0,[[0,4]]),mkrow(0,0,1,1,0,[[0,4]])])
assert defects(negative_spec,negative_plan)==[2]
finish('pilot.json',dict(seed=91015,tiny_cases=rows,
    safe=sum(r['accepted'] for r in rows),unsafe=sum(not r['accepted'] for r in rows),
    large_case=dict(n=spec['n'],rows=96,accepted=checked.accepted,
                    producer_cpu_s=t1-t,checker_cpu_s=t2-t1,
                    certificate_bytes=checked.certificate_bytes,calls=checked.calls,steps=checked.steps),
    count_only_negative=dict(total=4,expected=4,defect=2),all_checks_passed=True))
