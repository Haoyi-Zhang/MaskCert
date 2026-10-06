"""Exact finite validation of deterministic gate and fault-token semantics.
No external certified-counting solver is simulated or claimed to have run.
"""
from common import ROOT,bounded,peak_rss_kib,resource_observation
bounded()
from io import StringIO
from itertools import product
import json,time
from update_cases import selected_cases
from pcs.boolean_encoding import Circuit,encode_full,encode_update
from pcs.producer import write_certificate
from pcs.update_checker import establish_anchor
from pcs.oracle import enumerate_counters


def make_anchor(spec,plan):
    text=StringIO();write_certificate(spec,plan,text)
    return establish_anchor(spec,plan,StringIO(text.getvalue()))


def local_gate_tests():
    checks=0
    for operation in ('and','xor'):
        for a,b,v in product((False,True),repeat=3):
            if operation=='and':
                clauses=[(not v or a),(not v or b),(v or not a or not b)]
                semantic=(v==(a and b))
            else:
                clauses=[(not a or not b or not v),(a or b or not v),
                         (a or not b or v),(not a or b or v)]
                semantic=(v==(a!=b))
            assert all(clauses)==semantic
            checks+=1
    # Test all residues for representative arbitrary and power-of-two moduli.
    residue_checks=0
    for width in range(1,7):
        for modulus in range(1,17):
            c=Circuit();bits=c.input('x',width);rem=c.modulo(bits,modulus)
            for number in range(1<<width):
                values=c.evaluate({'x':number},False)
                actual=sum((values[abs(bit)] if bit>0 else not values[abs(bit)])<<j for j,bit in enumerate(rem))
                assert actual==number%modulus
                # All definitions, without a root constraint, must hold.
                assert c.evaluate({'x':number})
                residue_checks+=1
    return checks,residue_checks


def main():
    start=time.process_time();gate_checks,residue_checks=local_gate_tests()
    records=[];assignments=0
    inputs=[r for r in selected_cases()[:24] if r['declaration']['n']<=8]
    output=ROOT/'cases/cnf';output.mkdir(exist_ok=True)
    for record in inputs:
        spec,plan=record['declaration'],record['plan']
        anchor=make_anchor(record['old_declaration'],record['old_plan'])
        exact,_=enumerate_counters(spec,plan)
        for epoch,truth in enumerate(exact):
            for name,circuit in [('full',encode_full(spec,plan,epoch)),
                                 ('anchor',encode_update(anchor,spec,plan,epoch))]:
                count=0
                ranges=[range(1<<len(circuit.inputs[label])) for label in ('i','p','q')]
                for values in product(*ranges):
                    count+=circuit.evaluate(dict(zip(('i','p','q'),values)))
                    assignments+=1
                assert count==truth,(record['id'],epoch,name,count,truth)
                filename=f"{record['id']}-e{epoch}-{name}.cnf"
                with (output/filename).open('w') as stream:circuit.write_dimacs(stream)
                records.append({'case':record['id'],'epoch':epoch,'encoding':name,
                                'models':count,'variables':circuit.variables,
                                'clauses':len(circuit.clauses),'path':'cases/cnf/'+filename})
    # Correlated-summary impossibility control: same B,T,C,Q, unequal updates.
    # (2,0) and (0,2), U=both; add one occurrence at source zero.
    first=[2,0];second=[0,2]
    assert sum((m-1)**2 for m in first)==sum((m-1)**2 for m in second)==2
    assert sum(m*(m-1)//2 for m in first)==sum(m*(m-1)//2 for m in second)==1
    after_first=sum((m-1)**2 for m in [3,0]);after_second=sum((m-1)**2 for m in [1,2])
    assert (after_first,after_second)==(5,1)
    report={'observation_kind':'new_boolean_encoding_validation','all_checks_passed':True,
            'local_gate_truth_assignments':gate_checks,'modular_arithmetic_assignments':residue_checks,
            'plan_records':len(inputs),'encodings_compared':len(records),
            'primary_assignments_checked':assignments,'records':records,
            'generic_upstream_solver_executed':False,
            'summary_counterexample':{'old_counts_B_T_C_Q':[2,2,2,1],'old_defect':2,
                                      'after_same_addition_defects':[after_first,after_second]},
            'cpu_seconds':time.process_time()-start,'peak_rss_kib':peak_rss_kib(),
            **resource_observation()}
    (ROOT/'results/boolean-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='records'}))

if __name__=='__main__':main()
