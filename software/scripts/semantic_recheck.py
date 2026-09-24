#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

SOFTWARE=Path(__file__).resolve().parents[1]
ROOT=SOFTWARE.parent
sys.path.insert(0,str(SOFTWARE))
sys.path.insert(0,str(SOFTWARE/'scripts'))
from pcs.core import analyze, canonical_witness, check_certificate, explicit_defect, validate_plan
from benchmark import make_sparse_safe


def main():
    retained=json.loads((ROOT/'results/results.json').read_text(encoding='utf-8'))
    errors=[]; cases=[]
    for row in retained['scaling']:
        exp=row['universe_exponent']; f=row['fragment_count']; m=row['authorized_target_count']
        d,p=make_sparse_safe(1<<exp,f,m)
        got=analyze(d,p)
        expected={'B':row['B'],'T':row['T'],'C':row['C'],'Q':row['Q'],'D':row['D']}
        actual={k:getattr(got,k) for k in expected}
        if actual!=expected: errors.append(f'scaling 2^{exp}: {actual} != {expected}')
        if len(d.authorized)!=row['authorized_interval_count']: errors.append(f'scaling 2^{exp}: mask interval count changed')
        cert=ROOT/'results/certificates'/f'n2-{exp}-f-{f}-m-{m}.jsonl'
        try: checked=check_certificate(cert,d,p)
        except Exception as exc: errors.append(f'scaling 2^{exp}: certificate failed: {exc}')
        cases.append({'log2_N':exp,'fragments':f,'mask_intervals':len(d.authorized),'D':got.D,'safe':got.safe})
    baselines=[]
    for row in retained['enumeration_baseline']:
        exp=row['universe_exponent']; d,p=make_sparse_safe(1<<exp,32,256)
        fast=analyze(d,p).D; slow=explicit_defect(d,p)
        if fast!=0 or slow!=0 or fast!=slow: errors.append(f'baseline 2^{exp}: optimized={fast}, oracle={slow}')
        baselines.append({'log2_N':exp,'optimized_D':fast,'oracle_D':slow})
    d,p=make_sparse_safe(1<<32,125,1024)
    raw=json.loads(json.dumps(p.raw)); first=raw['fragments'][0]; raw['fragments'].append({**first,'id':'f9999','phase':'planned'})
    unsafe=validate_plan(raw,d); witness=canonical_witness(d,unsafe)
    retained_w=retained['large_witness']['witness']
    stable_fields=['category','target','source_counter','authorized','expected_multiplicity','actual_multiplicity','covering_fragments','prefix_defect_before','prefix_defect_at','total_defect']
    for key in stable_fields:
        if witness[key]!=retained_w[key]: errors.append(f'large witness field {key} changed')
    report={'status':'ok' if not errors else 'failed','scaling_cases':cases,'baseline_cases':baselines,'large_witness':{k:witness[k] for k in stable_fields},'errors':errors}
    out=ROOT/'qa/semantic-recheck.json'; out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(report,sort_keys=True))
    if errors: raise SystemExit(1)

if __name__=='__main__': main()
