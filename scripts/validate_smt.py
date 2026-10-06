"""Finite semantic checks of the optional native SMT translation."""
from common import ROOT,bounded,finish
bounded()
from io import StringIO
import json
from pcs.producer import write_certificate
from pcs.update_checker import establish_anchor
from pcs.oracle import enumerate_counters
from pcs.smt_baseline import smt_problem
from benchmark_smt import solve


def main():
    cases=json.loads((ROOT/'cases/updates.json').read_text())[:12]
    records=[]
    directory=ROOT/'cases/smt-validation';directory.mkdir(exist_ok=True)
    for case in cases:
        os,op=case['old_declaration'],case['old_plan']
        s,p=case['declaration'],case['plan']
        stream=StringIO();write_certificate(os,op,stream)
        anchor=establish_anchor(os,op,StringIO(stream.getvalue()))
        defects,_=enumerate_counters(s,p)
        for epoch,defect in enumerate(defects):
            for route,base in [('full',None),('reduced',anchor)]:
                text=smt_problem(s,p,epoch,anchor=base)
                name=f'{case["id"]}-e{epoch}-{route}'
                (directory/(name+'.smt2')).write_text(text)
                result=solve(s,p,epoch,text)
                expected='unsat' if defect==0 else 'sat'
                assert result['status']==expected,(name,result,defect)
                records.append(dict(id=name,oracle_defect=defect,expected_status=expected,**result))
    finish('smt-validation.json',dict(observation_kind='new_finite_native_smt_validation',
        plan_records=len(cases),actual_comparisons=len(records),
        counts={s:sum(r['status']==s for r in records) for s in ('sat','unsat','unknown')},
        all_checks_passed=True,records=records,
        guarantee='Finite oracle agreement; solver unsat responses are not independently proof checked.'))

if __name__=='__main__':main()
