"""One native SMT route for one retained input; bounded and no baseline tuning."""
from common import ROOT,bounded,finish
bounded()
from io import StringIO
import json, argparse, re, time, statistics
from pcs.smt_baseline import smt_problem,Z3Session
from pcs.producer import write_certificate,defects
from pcs.update_checker import establish_anchor


def cert(s,p):
    out=StringIO();write_certificate(s,p,out);return out.getvalue()


def problem_data(case):
    record=json.loads((ROOT/'cases/update-bench'/f'bench-{case:02d}.json').read_text())
    return record['old_declaration'],record['old_plan'],record['declaration'],record['plan']


def local_defect(s,p,epoch,x):
    y=(s['a']*x+s['b'])%s['n'];e=s['epochs'][epoch]
    wanted=any(l<=y<h for l,h in e['allow']) and not any(l<=y<h for l,h in e['exclude'])
    mass=sum(r['epoch']==epoch and r['lo']<=x<r['hi'] and x%r['step']==r['residue']
             and any(l<=y<h for l,h in r['guard']) for r in s['history']+p['future'])
    return (mass-1)**2 if wanted else mass


def solve(s,p,epoch,text):
    wall=time.perf_counter_ns();cpu=time.process_time_ns()
    with Z3Session() as solver:
        output=solver.evaluate(text).strip()
        if output not in ('sat','unsat','unknown'):raise AssertionError(output)
        model=None;reason=None
        if output=='sat':
            raw=solver.evaluate('(get-value (i))')
            match=re.fullmatch(r'\s*\(\(i\s+(\d+)\)\)\s*',raw)
            if not match:raise AssertionError('unparsed model '+raw)
            model=int(match.group(1))
            if not 0<=model<s['n'] or local_defect(s,p,epoch,model)<=0:
                raise AssertionError('invalid native counterexample')
        elif output=='unknown':
            reason=solver.evaluate('(get-info :reason-unknown)').strip()
        version=solver.version
    return dict(status=output,native_output=output,model_counter=model,reason_unknown=reason,
                cpu_ns=time.process_time_ns()-cpu,wall_ns=time.perf_counter_ns()-wall,
                solver_version=version)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case',type=int,required=True)
    ap.add_argument('--route',choices=['full','reduced'],required=True);args=ap.parse_args()
    if not 0<=args.case<20:raise SystemExit('case bound')
    os,op,s,p=problem_data(args.case)
    anchor=establish_anchor(os,op,StringIO(cert(os,op))) if args.route=='reduced' else None
    start=time.process_time();text=smt_problem(s,p,0,anchor=anchor)
    construct=time.process_time()-start
    output=ROOT/'cases/smt';output.mkdir(exist_ok=True)
    name=f'bench-{args.case:02d}-{args.route}'
    (output/(name+'.smt2')).write_text(text)
    warmup=solve(s,p,0,text)
    samples=[solve(s,p,0,text) for _ in range(5)]
    assert all(r['status']!='sat' for r in samples+[warmup]), 'constructed safe guard partition'
    counts={label:sum(r['status']==label for r in samples) for label in ('sat','unsat','unknown')}
    times=[r['cpu_ns']/1e9 for r in samples]
    qs=statistics.quantiles(times,n=4,method='inclusive')
    report=dict(id=name,case=args.case,route=args.route,epoch=0,expected_safe=True,
                guarantee='trusted SMT safety decision; no certified count',
                construction_cpu_seconds=construct,formula_bytes=len(text.encode()),
                timeout_ms=10000,warmup=warmup,repetitions=samples,status_counts=counts,
                cpu_median_s=statistics.median(times),cpu_q1_s=qs[0],cpu_q3_s=qs[2],
                anchor_cost_timed=False,
                no_incorrect_sat_answer_observed=True,
                all_timed_decisions_completed=(counts['unknown']==0))
    finish('smt/'+name+'.json',report)

if __name__=='__main__':main()
