"""One bounded, exactly specified update benchmark per process.

Original results/boundary.json is never written here. Timed runs use in-memory
inputs/transcripts, one batch warmup and five retained batch repeats. Cold means that the
base is fully reverified during each timed call; warm means a verified anchor
is already present. The encoding experiment measures CNF SIZE, not external
CPOG/VeriPB runtime.
"""
from common import ROOT,bounded,peak_rss_kib,resource_observation
bounded()
from copy import deepcopy
from io import StringIO
from pathlib import Path
import argparse,json,time,statistics
from casegen import mkrow
from pcs.model import Invalid
from pcs.producer import write_certificate,defects
from pcs.checker import verify
from pcs.update_producer import write_update,changed_rows
from pcs.update_checker import establish_anchor,verify_update
from pcs.boolean_encoding import encode_full,encode_update


def configurations():
    answer=[]
    for K in (8,16,32,64,120):answer.append(('fragments',1<<24,K,16,2))
    for E in (1,4,16,64,256):answer.append(('masks',1<<24,32,E,2))
    for N in (1<<12,1<<16,1<<20,1<<24,1<<32):answer.append(('domain',N,32,4,2))
    for edits in (2,8,16,32,64):answer.append(('edits',1<<24,64,16,edits))
    return answer


def inputs(N,K,E,edits):
    # Guard-partition stress family: all source ranges overlap, but the guards
    # partition each allowed target band. Thus the full checker cannot apply
    # the inherited empty-source-lattice shortcut to these pairs.
    period=N//E
    width=period//(K+1)
    if width<2 or edits%2 or edits>K:
        raise ValueError('benchmark construction bounds')
    exclusions=[[j*period+K*width,(j+1)*period] for j in range(E)]
    spec=dict(n=N,a=5 if N>5 else 1,b=7%N,
              epochs=[dict(allow=[[0,N]],exclude=exclusions)],history=[])
    rows=[mkrow(0,0,N,1,0,[[j*period+r*width,j*period+(r+1)*width]
                            for j in range(E)]) for r in range(K)]
    plan=dict(context={k:spec[k] for k in ('n','a','b')},future=rows)
    new=deepcopy(plan)
    # Shift boundaries within disjoint row pairs by one target. No row is
    # removed semantically and no result is selected by its measured runtime.
    for r in range(0,edits,2):
        for j in range(E):
            new['future'][r]['guard'][j][1]+=1
            new['future'][r+1]['guard'][j][0]+=1
    return spec,plan,deepcopy(spec),new


def full_text(spec,plan):
    stream=StringIO();write_certificate(spec,plan,stream)
    return stream.getvalue()


def update_text(os,op,s,p):
    stream=StringIO();write_update(os,op,s,p,stream)
    return stream.getvalue()


def timed(fn):
    # Single-call pilot times included zero CPU deltas on this host. Calibrate
    # an equal-size batch for this operation to at least 50 ms of CPU time.
    # Calibration uses no semantic outcome or target speedup threshold.
    iterations = 1
    calibration = []
    while True:
        start = time.process_time_ns()
        for _ in range(iterations): fn()
        elapsed = time.process_time_ns() - start
        calibration.append({'iterations': iterations, 'cpu_ns': elapsed})
        if elapsed >= 50_000_000 or iterations >= 4096: break
        iterations *= 2
    for _ in range(iterations): fn()
    records = []
    for repetition in range(5):
        wall = time.perf_counter_ns(); cpu = time.process_time_ns()
        for _ in range(iterations): fn()
        records.append({'repetition': repetition, 'iterations': iterations,
                        'wall_ns': time.perf_counter_ns() - wall,
                        'cpu_ns': time.process_time_ns() - cpu})
    samples = [x['cpu_ns']/iterations/1e9 for x in records]
    walls = [x['wall_ns']/iterations/1e9 for x in records]
    quartiles = statistics.quantiles(samples,n=4,method='inclusive')
    wallq = statistics.quantiles(walls,n=4,method='inclusive')
    return {'raw': records, 'calibration': calibration, 'batch_iterations': iterations,
            'calibration_target_cpu_ns': 50_000_000,
            'cpu_median_s': statistics.median(samples),
            'cpu_q1_s': quartiles[0], 'cpu_q3_s': quartiles[2],
            'cpu_iqr_s': quartiles[2]-quartiles[0],
            'wall_median_s': statistics.median(walls),
            'wall_q1_s': wallq[0], 'wall_q3_s': wallq[2]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',type=int,required=True)
    args=parser.parse_args()
    configs=configurations()
    if not 0<=args.case<len(configs):raise SystemExit('case out of range')
    group,N,K,E,edit=configs[args.case]
    oldspec,oldplan,spec,plan=inputs(N,K,E,edit)
    started=time.process_time()
    oldtext=full_text(oldspec,oldplan);newtext=full_text(spec,plan)
    update=update_text(oldspec,oldplan,spec,plan)
    anchor=establish_anchor(oldspec,oldplan,StringIO(oldtext))
    checked=verify(spec,plan,StringIO(newtext))
    increment=verify_update(anchor,spec,plan,StringIO(update))
    assert checked.accepted and increment.accepted and checked.defects==increment.defects
    operations={
        'full_producer':lambda:full_text(spec,plan),
        'update_producer':lambda:update_text(oldspec,oldplan,spec,plan),
        'direct_symbolic':lambda:defects(spec,plan),
        'full_checker':lambda:verify(spec,plan,StringIO(newtext)),
        'warm_update_checker':lambda:verify_update(anchor,spec,plan,StringIO(update)),
        'cold_update_checker':lambda:verify_update(establish_anchor(oldspec,oldplan,StringIO(oldtext)),spec,plan,StringIO(update)),
    }
    measurements={name:timed(operation) for name,operation in operations.items()}
    encodings={}
    for name,operation in [('full',lambda:encode_full(spec,plan)),
                           ('safe_anchor',lambda:encode_update(anchor,spec,plan))]:
        encoding_start=time.process_time()
        try:
            circuit=operation()
            encodings[name]={'status':'encoded_not_solved','variables':circuit.variables,
                             'clauses':len(circuit.clauses),'gates':len(circuit.gates),
                             'primary_bits':sum(map(len,circuit.inputs.values())),
                             'cpu_seconds':time.process_time()-encoding_start}
            del circuit
        except Invalid as error:
            encodings[name]={'status':'unsupported_encoding_bound','error':str(error),
                             'cpu_seconds':time.process_time()-encoding_start}
    name=f'bench-{args.case:02d}'
    case={'id':name,'group':group,'old_declaration':oldspec,'old_plan':oldplan,
          'declaration':spec,'plan':plan}
    out=ROOT/'cases/update-bench';out.mkdir(exist_ok=True)
    (out/(name+'.json')).write_text(json.dumps(case,indent=2)+'\n')
    report={'id':name,'observation_kind':'new_measured_update_benchmark',
            'group':group,'n':N,'base_fragments':K,'policy_exclusions':E,
            'guard_intervals_per_fragment':E,'removed':edit,'added':edit,
            'unchanged':K-edit,'safe':checked.accepted,
            'full_floor_queries':checked.calls,'update_floor_queries':increment.calls,
            'full_triples':checked.steps,'update_triples':increment.steps,
            'full_certificate_bytes':checked.certificate_bytes,
            'update_certificate_bytes':increment.certificate_bytes,
            'measurements':measurements,'boolean_encodings':encodings,
            'external_solver_executed':False,'workers':1,'warmup':1,'timed_repeats':5,
            'total_cpu_seconds':time.process_time()-started,
            'process_peak_rss_kib':peak_rss_kib(),**resource_observation()}
    out=ROOT/'results/update-bench';out.mkdir(exist_ok=True)
    (out/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='measurements'}))

if __name__=='__main__':main()
