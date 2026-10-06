"""Finite differential and malformed-transcript checks for safe-anchor updates."""
from common import ROOT, bounded, peak_rss_kib, resource_observation
bounded()
from copy import deepcopy
from dataclasses import FrozenInstanceError
from io import StringIO
import json, time
from update_cases import selected_cases
from pcs.model import Invalid
from pcs.producer import defects, locate, write_certificate
from pcs.checker import verify
from pcs.oracle import enumerate_counters, replay_audit
from pcs.update_producer import changed_rows, update_defects, write_update, locate_update
from pcs.update_checker import (SafeAnchor, establish_anchor, verify_update,
                               advance_anchor, check_update_witness)


def full(spec, plan, prefix=None):
    stream = StringIO(); write_certificate(spec, plan, stream, prefix)
    return stream.getvalue()

def delta(record, prefix=None):
    stream = StringIO()
    write_update(record['old_declaration'], record['old_plan'],
                 record['declaration'], record['plan'], stream, prefix)
    return stream.getvalue()


def must_reject(fn, label):
    try:
        fn()
    except (Invalid, FrozenInstanceError, AttributeError):
        return label
    raise AssertionError('accepted negative control: ' + label)


def main():
    started = time.process_time()
    cases = selected_cases()
    results, negative = [], []
    comparisons = witnesses = mutations = 0
    algebra = 0
    for u in (0,1):
        for v in (0,1):
            for r in range(u+1):
                for a in range(129):
                    m=u-r+a
                    truth=(m-1)**2 if v else m
                    value=u+v-2*u*v-r+2*r*v+a-2*a*v*(1-u)+v*a*(a-1)-2*v*a*r
                    assert truth==value and value>=0
                    algebra += 1
    for record in cases:
        oldspec, oldplan = record['old_declaration'], record['old_plan']
        spec, plan = record['declaration'], record['plan']
        base = full(oldspec, oldplan)
        anchor = establish_anchor(oldspec, oldplan, StringIO(base))
        prefixes = list(range(spec['n']+1)) if spec['n']<=17 else sorted({0,1,spec['n']//3,spec['n']//2,spec['n']})
        saved = []
        for prefix in prefixes:
            text = delta(record, prefix)
            answer = verify_update(anchor, spec, plan, StringIO(text), prefix)
            whole = verify(spec, plan, StringIO(full(spec,plan,prefix)), prefix)
            exact,_ = enumerate_counters(spec,plan,prefix)
            assert list(answer.defects)==exact==list(whole.defects)
            assert exact==update_defects(oldspec,oldplan,spec,plan,prefix)==defects(spec,plan,prefix)
            comparisons += 1
            saved.append({'prefix':prefix,'defects':exact,'floor_queries':answer.calls,
                          'triples':answer.steps,'certificate_bytes':answer.certificate_bytes})
        finaltext=delta(record)
        answer=verify_update(anchor,spec,plan,StringIO(finaltext))
        assert list(answer.defects)==replay_audit(spec,plan)
        witness=locate_update(oldspec,oldplan,spec,plan)
        assert witness==locate(spec,plan)==enumerate_counters(spec,plan)[1]
        if witness is not None:
            before,through=delta(record,witness['counter']),delta(record,witness['counter']+1)
            assert check_update_witness(anchor,spec,plan,witness,StringIO(finaltext),StringIO(before),StringIO(through))
            negative.append(must_reject(lambda:check_update_witness(anchor,spec,plan,witness,StringIO(finaltext),StringIO(through),StringIO(before)),record['id']+':swapped-prefix'))
            false=deepcopy(witness); false['rows']=[999]
            negative.append(must_reject(lambda:check_update_witness(anchor,spec,plan,false,StringIO(finaltext),StringIO(before),StringIO(through)),record['id']+':wrong-row'))
            witnesses += 1
            negative.append(must_reject(lambda:advance_anchor(anchor,spec,plan,StringIO(finaltext)),record['id']+':unsafe-advance'))
        else:
            nextanchor=advance_anchor(anchor,spec,plan,StringIO(finaltext))
            echo=dict(old_declaration=spec,old_plan=plan,declaration=spec,plan=plan)
            assert verify_update(nextanchor,spec,plan,StringIO(delta(echo))).accepted
        lines=finaltext.splitlines(keepends=True)
        # Transcript corruption counts are actual calls; floor-only corruptions
        # are attempted only when a floor record exists.
        candidates=[('truncate',''.join(lines[:-1])),('append',finaltext+'{}\n')]
        header=json.loads(lines[0]); header['added']=header['added']+[999]
        candidates.append(('changed-position',json.dumps(header)+'\n'+''.join(lines[1:])))
        if len(lines)>2:
            row=json.loads(lines[1]); row[0]+=1
            candidates.append(('bad-floor',lines[0]+json.dumps(row)+'\n'+''.join(lines[2:])))
            row=json.loads(lines[1]); row[1][0][0]+=1
            candidates.append(('bad-quotient',lines[0]+json.dumps(row)+'\n'+''.join(lines[2:])))
        for label,text in candidates:
            negative.append(must_reject(lambda:verify_update(anchor,spec,plan,StringIO(text)),record['id']+':'+label))
            mutations+=1
        # Context/history and untrusted-anchor negative paths are independent
        # of whether the plan contains arithmetic records.
        altered=deepcopy(spec); altered['history']=[] if spec['history'] else [{'epoch':0,'lo':0,'hi':0,'step':1,'residue':0,'guard':[]}]
        negative.append(must_reject(lambda:verify_update(anchor,altered,plan,StringIO(finaltext)),record['id']+':history'))
        results.append({'id':record['id'],'group':record['group'],'accepted':answer.accepted,
                        'defects':list(answer.defects),'witness':witness,
                        'removed_added':list(changed_rows(oldspec,oldplan,spec,plan)),
                        'prefix_results':saved})
    # Independent anchor misuse controls.
    rec=cases[0]; ss=rec['old_declaration']; pp=rec['old_plan']
    safe=establish_anchor(ss,pp,StringIO(full(ss,pp)))
    negative.append(must_reject(lambda:SafeAnchor(None,'{}','{}'),'direct-constructor'))
    negative.append(must_reject(lambda:verify_update({'accepted':True},ss,pp,StringIO('')),'untrusted-json-anchor'))
    negative.append(must_reject(lambda:setattr(safe,'_declaration','{}'),'frozen-anchor'))
    ss2,pp2=deepcopy(ss),deepcopy(pp)
    snapshot=establish_anchor(ss2,pp2,StringIO(full(ss2,pp2)))
    pp2['future'].clear(); ss2['epochs'].clear()
    assert snapshot.inputs()==(ss,pp)
    # A safe prefix is insufficient even if its numeric zero is genuine.
    negative.append(must_reject(lambda:establish_anchor(ss,pp,StringIO(full(ss,pp,0))),'prefix-not-full-anchor'))
    badspec={'n':2,'a':1,'b':0,'epochs':[{'allow':[[0,2]],'exclude':[]}],'history':[]}
    badplan={'context':{'n':2,'a':1,'b':0},'future':[]}
    negative.append(must_reject(lambda:establish_anchor(badspec,badplan,StringIO(full(badspec,badplan))),'unsafe-base'))
    report={'observation_kind':'new_safe_anchor_validation','all_checks_passed':True,
            'cases_attempted':len(cases),'cases_retained':len(cases),'cases_compared':len(results),
            'safe_new_plans':sum(x['accepted'] for x in results),'unsafe_new_plans':witnesses,
            'prefix_comparisons':comparisons,'least_witness_comparisons':witnesses,
            'actual_corruption_calls':mutations,'negative_controls':negative,
            'pointwise_algebra_checks':algebra,'case_results':results,
            'cpu_seconds':time.process_time()-started,
            'peak_rss_kib':peak_rss_kib(), **resource_observation()}
    (ROOT/'cases/updates.json').write_text(json.dumps(cases,indent=2)+'\n')
    (ROOT/'results/updates.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:value for key,value in report.items() if key not in ('negative_controls','case_results')}))

if __name__=='__main__':main()
