"""Audit frozen observations before any fresh experiments run. Standard library only.

This checks inputs, reconstructed counts, saved transcripts and statistics;
it does not re-label UNSAT as a checked counting proof or UNKNOWN as success.
"""
from common import ROOT, bounded, finish
bounded()
from io import StringIO
import json, math, statistics
from pathlib import Path
from pcs.model import certificate_lines, validate
from pcs.checker import verify
from pcs.producer import write_certificate
from pcs.update_checker import establish_anchor, verify_update, _difference
from pcs.update_producer import write_update


def read(relative):
    return json.loads((ROOT / relative).read_text())


def median_check(measurement, batches):
    raw=measurement['raw']
    assert len(raw)==batches
    cpus=[]; walls=[]
    for j,row in enumerate(raw):
        assert row['repetition']==j and row['cpu_ns']>0 and row['wall_ns']>0
        iterations=row.get('iterations',1)
        assert type(iterations) is int and iterations>=1
        cpus.append(row['cpu_ns']/iterations/1e9)
        walls.append(row['wall_ns']/iterations/1e9)
    assert math.isclose(statistics.median(cpus),measurement['cpu_median_s'],rel_tol=1e-12,abs_tol=1e-12)
    if 'cpu_q1_s' in measurement:
        q1,_,q3=statistics.quantiles(cpus,n=4,method='inclusive')
        for key,value in [('cpu_q1_s',q1),('cpu_q3_s',q3),('cpu_iqr_s',q3-q1)]:
            assert math.isclose(value,measurement[key],rel_tol=1e-12,abs_tol=1e-12)
    if 'wall_median_s' in measurement:
        assert math.isclose(statistics.median(walls),measurement['wall_median_s'],rel_tol=1e-12,abs_tol=1e-12)
    if 'cpu_min_s' in measurement:
        assert min(cpus)==measurement['cpu_min_s'] and max(cpus)==measurement['cpu_max_s']


def text_certificate(spec,plan):
    out=StringIO();write_certificate(spec,plan,out);return out.getvalue()


def main():
    validation=read('results/updates.json');cases=read('cases/updates.json')
    assert validation['all_checks_passed'] and len(cases)==96
    records=validation['case_results'];assert len(records)==96
    assert [r['id'] for r in records]==[r['id'] for r in cases]
    assert sum(len(r['prefix_results']) for r in records)==validation['prefix_comparisons']==688
    assert sum(r['accepted'] for r in records)==40
    assert sum(r['witness'] is not None for r in records)==56
    suffixes={':truncate',':append',':changed-position',':bad-floor',':bad-quotient'}
    actual=sum(any(name.endswith(suffix) for suffix in suffixes) for name in validation['negative_controls'])
    assert actual==validation['actual_corruption_calls']==438
    boolean=read('results/boolean-validation.json')
    assert boolean['all_checks_passed'] and len(boolean['records'])==28
    for record in boolean['records']:
        path=ROOT/record['path']; lines=path.read_text().splitlines()
        header=next(line for line in lines if line.startswith('p cnf ')).split()
        assert int(header[2])==record['variables'] and int(header[3])==record['clauses']
        assert len([line for line in lines if line and line[0] not in 'cp'])==record['clauses']
    benchmark=[]
    for j in range(20):
        name=f'bench-{j:02d}';case=read('cases/update-bench/'+name+'.json')
        result=read('results/update-bench/'+name+'.json')
        os,op,s,p=(case[k] for k in ('old_declaration','old_plan','declaration','plan'))
        validate(os,op);validate(s,p)
        old=text_certificate(os,op)
        anchor=establish_anchor(os,op,StringIO(old))
        new=text_certificate(s,p);answer=verify(s,p,StringIO(new))
        delta=StringIO();write_update(os,op,s,p,delta)
        update=verify_update(anchor,s,p,StringIO(delta.getvalue()))
        assert answer.accepted and answer.defects==update.defects
        assert answer.calls==result['full_floor_queries']
        assert update.calls==result['update_floor_queries']
        assert len(new.encode())==result['full_certificate_bytes']
        assert len(delta.getvalue().encode())==result['update_certificate_bytes']
        for measurement in result['measurements'].values():median_check(measurement,5)
        removed,added=_difference(op,p)
        assert len(removed)==result['removed'] and len(added)==result['added']
        benchmark.append({'id':name,'defects':list(answer.defects),'full_queries':answer.calls,'update_queries':update.calls})
    original=read('cases/boundary.json')
    base=establish_anchor(original['declaration'],original['plan'],certificate_lines(ROOT/'results/boundary-certificate.jsonl'))
    transfer=[]
    for name,expected in [('split',0),('remove',44738560),('revoke',1024)]:
        case=read('cases/transfer/'+name+'.json'); result=read('results/transfer/'+name+'.json')
        assert case['old_declaration']==original['declaration'] and case['old_plan']==original['plan']
        s,p=case['declaration'],case['plan']
        whole=verify(s,p,certificate_lines(ROOT/f'results/transfer/{name}-full.jsonl'))
        update=verify_update(base,s,p,certificate_lines(ROOT/f'results/transfer/{name}-update.jsonl'))
        assert whole.defects==update.defects==(expected,)
        for key,answer in [('full_checker',whole),('warm_update_checker',update)]:
            m=result['measurements'][key]
            assert m['floor_queries']==answer.calls and m['triples']==answer.steps
            assert m['certificate_bytes']==answer.certificate_bytes
        for measurement in result['measurements'].values():median_check(measurement,3)
        transfer.append({'id':name,'defects':list(whole.defects),'full_queries':whole.calls,'update_queries':update.calls})
    smt_counts={route:{k:0 for k in ('sat','unsat','unknown')} for route in ('full','reduced')}
    # No native library is loaded: these are audits of the recorded observations.
    for j in range(20):
        for route in ('full','reduced'):
            name=f'bench-{j:02d}-{route}';result=read('results/smt/'+name+'.json')
            assert (ROOT/'cases/smt'/f'{name}.smt2').stat().st_size==result['formula_bytes']
            assert len(result['repetitions'])==5
            statuses={status:sum(x['status']==status for x in result['repetitions']) for status in ('sat','unsat','unknown')}
            assert statuses==result['status_counts'] and statuses['sat']==0
            times=[x['cpu_ns']/1e9 for x in result['repetitions']]
            q1,_,q3=statistics.quantiles(times,n=4,method='inclusive')
            assert statistics.median(times)==result['cpu_median_s']
            assert q1==result['cpu_q1_s'] and q3==result['cpu_q3_s']
            for x in result['repetitions']:
                assert x['native_output']==x['status']
                if x['status']=='unknown':assert x['reason_unknown']
            for status,count in statuses.items():smt_counts[route][status]+=count
    assert smt_counts=={'full':{'sat':0,'unsat':95,'unknown':5},'reduced':{'sat':0,'unsat':100,'unknown':0}}
    native=read('results/smt-validation.json')
    assert native['actual_comparisons']==len(native['records'])==48 and native['all_checks_passed']
    assert all(x['status']==x['expected_status'] for x in native['records'])
    full_largest=read('results/update-bench/bench-04.json')
    negative=read('results/update-bench/bench-19.json')
    def ratio(record):
        return record['measurements']['full_checker']['cpu_median_s']/record['measurements']['warm_update_checker']['cpu_median_s']
    result={'all_checks_passed':True,'observation_kind':'audit_of_frozen_new_results_not_a_new_benchmark',
            'update_cases':96,'prefix_comparisons':688,'witnesses':56,'actual_transcript_corruptions':438,
            'boolean_encodings':28,'boolean_backend_status':'encoded and finite-validated; upstream certified tools not run',
            'batched_cases':benchmark,'measurements_per_case':6,'batches_per_measurement':5,
            'transfer_cases':transfer,'transfer_repeats':3,
            'smt_timed_status_counts':smt_counts,'smt_finite_comparisons':48,
            'legacy_smt_semantic_result_verified_field':'meant no incorrect SAT answer observed; UNKNOWN is NOT a completed decision',
            'largest_K_full_over_warm_cpu_ratio':ratio(full_largest),
            'large_edit_full_over_warm_cpu_ratio':ratio(negative),
            'upstream_certified_counting_pipeline_executed':False}
    finish('extension-audit.json',result)

if __name__=='__main__':main()
