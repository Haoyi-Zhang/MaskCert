from common import ROOT,bounded,finish
bounded()
from copy import deepcopy
from io import StringIO
import argparse,json,time,statistics
from pcs.producer import write_certificate
from pcs.checker import verify
from pcs.update_producer import write_update
from pcs.update_checker import establish_anchor,verify_update
from pcs.model import certificate_lines


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case',choices=['split','remove','revoke'],required=True)
    args=ap.parse_args();label=args.case
    original=json.loads((ROOT/'cases/boundary.json').read_text())
    os,op=original['declaration'],original['plan'];s,p=deepcopy(os),deepcopy(op)
    if label=='split':
        first=p['future'].pop(0);second=deepcopy(first)
        midpoint=(first['lo']+first['hi'])//2
        first['hi']=midpoint;second['lo']=midpoint
        p['future'][0:0]=[first,second]
    elif label=='remove':p['future'].pop(0)
    else:
        for e in s['epochs']:
            for interval in e['exclude']:interval[0]-=1
    directory=ROOT/'cases/transfer';directory.mkdir(exist_ok=True)
    (directory/(label+'.json')).write_text(json.dumps(dict(id=label,old_declaration=os,old_plan=op,declaration=s,plan=p),indent=2)+'\n')
    out=ROOT/'results/transfer';out.mkdir(exist_ok=True)
    fullfile=out/(label+'-full.jsonl');updatefile=out/(label+'-update.jsonl')
    with fullfile.open('w') as stream:write_certificate(s,p,stream)
    with updatefile.open('w') as stream:write_update(os,op,s,p,stream)
    oldfile=ROOT/'results/boundary-certificate.jsonl'
    anchor=establish_anchor(os,op,certificate_lines(oldfile))
    # Timings include file opening and streaming in both paths.
    operations={'full_checker':lambda:verify(s,p,certificate_lines(fullfile)),
                'warm_update_checker':lambda:verify_update(anchor,s,p,certificate_lines(updatefile)),
                'cold_update_checker':lambda:verify_update(establish_anchor(os,op,certificate_lines(oldfile)),s,p,certificate_lines(updatefile))}
    measurements={};semantics=None
    for name,fn in operations.items():
        result=fn();raw=[]
        if semantics is None:semantics=result.defects
        assert result.defects==semantics
        for repeat in range(3):
            wall=time.perf_counter_ns();cpu=time.process_time_ns();result=fn()
            raw.append(dict(repetition=repeat,cpu_ns=time.process_time_ns()-cpu,wall_ns=time.perf_counter_ns()-wall))
            assert result.defects==semantics
        samples=[v['cpu_ns']/1e9 for v in raw]
        measurements[name]=dict(raw=raw,cpu_median_s=statistics.median(samples),
                                cpu_min_s=min(samples),cpu_max_s=max(samples),
                                floor_queries=result.calls,triples=result.steps,
                                certificate_bytes=result.certificate_bytes)
    assert (not any(semantics))==(label=='split')
    if label=='revoke':assert semantics==(1024,)
    finish('transfer/'+label+'.json',dict(id=label,observation_kind='new_transfer_not_original_table_III',
        domain=os['n'],history_fragments=len(os['history']),old_future_fragments=len(op['future']),
        new_future_fragments=len(p['future']),old_exclusions=1024,defects=semantics,
        warmup=1,timed_repeats=3,measurements=measurements,all_checks_passed=True))

if __name__=='__main__':main()
