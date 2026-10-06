"""Non-overwriting, resource-bounded scientific reproduction.

Default: inherited science, new finite tests, frozen-data arithmetic/statistical
recheck. --benchmarks reruns the 20+3 new timing inputs. --smt runs the optional
native Z3 comparison. --full selects both. No paper or network dependency.
"""
from __future__ import annotations
import argparse, ast, hashlib, json, os, re, resource, shutil, signal, subprocess, sys, tempfile, time
from pathlib import Path
from restore_inputs import restore_inputs
ROOT=Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS=120


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.digest()


def snapshot():
    # Internal non-mutation detector, never written as a hash manifest.
    return {p.relative_to(ROOT).as_posix():digest(p) for p in ROOT.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}


def scientific(value):
    if isinstance(value,dict):
        return {k:scientific(v) for k,v in value.items()
                if 'cpu_' not in k and k not in ('peak_rss_kib','workers')}
    if isinstance(value,list):return [scientific(v) for v in value]
    if isinstance(value,str):
        # OSError includes the random temporary test directory. Keep errno,
        # filename and all other output; only this non-semantic path varies.
        return re.sub(r"/tmp/mask-update-cli-[^/'\"\s]+", "<test-directory>", value)
    return value


def compare_json(staged,relative):
    x=json.loads((ROOT/relative).read_text());y=json.loads((staged/relative).read_text())
    if relative == 'results/dependency-audit.json':
        # Added reviewed scripts change this inventory, not the frozen science.
        # Reconstruct the current inventory before allowing the metadata delta.
        paths = [ROOT/'pcs.py', ROOT/'pcs-update.py']
        for folder in ('src', 'scripts', 'tests'):
            paths.extend(sorted((ROOT/folder).rglob('*.py')))
        imported = set()
        for path in paths:
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split('.')[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported.add(node.module.split('.')[0])
        if (y['python_files_parsed'] != len(paths)
            or y['imported_top_level_modules'] != sorted(imported)
            or y['external_runtime_or_test_dependencies'] != []
            or not y['standard_library_only'] or not y['all_checks_passed']):
            raise RuntimeError('current dependency inventory mismatch')
        for field in ('python_files_parsed', 'imported_top_level_modules'):
            x[field] = y[field]
    if relative == 'results/validation.json':
        # The frozen run checked producer/oracle prefixes, not every prefix
        # transcript. Require the added obligation without rewriting its record.
        if y.get('prefix_transcript_checks') != 909:
            raise RuntimeError('missing inherited prefix transcript checks')
        if 'prefix_transcript_checks' not in x:
            y.pop('prefix_transcript_checks')
    if scientific(x)!=scientific(y):raise RuntimeError('scientific field mismatch: '+relative)


def compare_bytes(staged,relative):
    if digest(ROOT/relative)!=digest(staged/relative):raise RuntimeError('exact evidence mismatch: '+relative)


def run(staged,script,*args,raw_output=None):
    command=[sys.executable,str(staged/'scripts'/script),*map(str,args)]
    start=time.monotonic()
    child=subprocess.Popen(command,cwd=staged,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                           start_new_session=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    timed_out=False
    try:stdout,stderr=child.communicate(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid,signal.SIGKILL);stdout,stderr=child.communicate()
        timed_out=True
    if raw_output is not None:
        # Preserve actual streams before any semantic comparison or failure.
        stem=script.removesuffix('.py')+''.join('-'+str(a) for a in args)
        stem=re.sub(r'[^A-Za-z0-9_.-]','_',stem)
        for suffix,value in [('stdout.txt',stdout),('stderr.txt',stderr)]:
            with (raw_output/(stem+'.'+suffix)).open('x',encoding='utf-8') as stream:
                stream.write(value)
        with (raw_output/(stem+'.command.json')).open('x',encoding='utf-8') as stream:
            json.dump({'command':command,'returncode':child.returncode,
                       'timed_out':timed_out,'wall_seconds':time.monotonic()-start},stream,indent=2)
            stream.write('\n')
    if timed_out:
        raise RuntimeError(f'{script} exceeded outer {TIMEOUT_SECONDS}s wall bound\n{stdout}\n{stderr}')
    if child.returncode:
        raise RuntimeError(f'{script} {args} exited {child.returncode}\n{stdout}\n{stderr}')
    tail=stdout.strip().splitlines()[-1] if stdout.strip() else ''
    # Keep the actual child summary and resource observations, not a made-up PASS marker.
    try:payload=json.loads(tail)
    except json.JSONDecodeError:payload={'last_stdout_line':tail}
    return {'script':script,'arguments':list(args),'returncode':0,'wall_seconds':time.monotonic()-start,
            'summary':payload,'stderr':stderr.strip()}


def compare_benchmark(staged,index):
    relative=f'results/update-bench/bench-{index:02d}.json'
    old=json.loads((ROOT/relative).read_text());new=json.loads((staged/relative).read_text())
    fields=('id','group','n','base_fragments','policy_exclusions','guard_intervals_per_fragment',
            'removed','added','unchanged','safe','full_floor_queries','update_floor_queries',
            'full_triples','update_triples','full_certificate_bytes','update_certificate_bytes')
    for key in fields:
        if old[key]!=new[key]:raise RuntimeError(relative+' changed '+key)
    compare_bytes(staged,f'cases/update-bench/bench-{index:02d}.json')
    # Batch sizes and timing observations are allowed to differ, not rewritten as old measurements.


def compare_transfer(staged,name):
    relative=f'results/transfer/{name}.json'
    old=json.loads((ROOT/relative).read_text());new=json.loads((staged/relative).read_text())
    for key in ('id','domain','history_fragments','old_future_fragments','new_future_fragments','old_exclusions','defects'):
        if old[key]!=new[key]:raise RuntimeError(relative+' changed '+key)
    for operation in old['measurements']:
        for field in ('floor_queries','triples','certificate_bytes'):
            if old['measurements'][operation][field]!=new['measurements'][operation][field]:
                raise RuntimeError(relative+' changed '+operation+'/'+field)
    compare_bytes(staged,f'cases/transfer/{name}.json')
    for kind in ('full','update'):compare_bytes(staged,f'results/transfer/{name}-{kind}.jsonl')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report',type=Path,help='new report file OUTSIDE source extraction')
    ap.add_argument('--raw-output',type=Path,help='new directory OUTSIDE source extraction for actual child streams, including failures')
    ap.add_argument('--quick',action='store_true',help='skip inherited boundary regeneration; not a complete core rerun')
    ap.add_argument('--benchmarks',action='store_true',help='fresh 20-case batching and three retained-input transfers')
    ap.add_argument('--smt',action='store_true',help='optional native Z3: finite validation and 40 solver configurations')
    ap.add_argument('--full',action='store_true',help='core plus --benchmarks and --smt')
    args=ap.parse_args()
    if args.full and args.quick:ap.error('--full and --quick are incompatible')
    args.benchmarks |= args.full;args.smt |= args.full
    if args.report:
        args.report=args.report.resolve()
        if args.report.exists() or args.report.is_relative_to(ROOT.resolve()):
            ap.error('--report must be a non-existing file outside the source extraction')
    if args.raw_output:
        args.raw_output=args.raw_output.resolve()
        if args.raw_output.exists() or args.raw_output.is_relative_to(ROOT.resolve()):
            ap.error('--raw-output must be a non-existing directory outside the source extraction')
        args.raw_output.mkdir(parents=True,exist_ok=False)
    if hasattr(os,'sched_setaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    # Materialize only omitted frozen files before the source snapshot/copy.
    # Existing files are byte-compared and never overwritten by the bootstrap.
    restore_inputs(ROOT)
    before=snapshot();start=time.monotonic();cpu=time.process_time()
    usage0=resource.getrusage(resource.RUSAGE_CHILDREN);reports=[]
    with tempfile.TemporaryDirectory(prefix='mask-aware-recheck-') as temporary:
        staged=Path(temporary)/'artifact'
        shutil.copytree(ROOT,staged,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        def checked_run(script,*arguments):
            return run(staged,script,*arguments,raw_output=args.raw_output)
        # These audits run on frozen inputs/results BEFORE any staged remeasurement.
        for script,result in [('audit_evidence.py','results/evidence-map.json'),
                              ('audit_extension.py','results/extension-audit.json')]:
            reports.append(checked_run(script));compare_json(staged,result)
        compare_bytes(staged,'docs/evidence-map.md')
        commands=[('audit_identity.py','identity-audit.json'),('audit_dependencies.py','dependency-audit.json'),
                  ('pilot.py','pilot.json'),('validate.py','validation.json')]
        if not args.quick:commands.append(('boundary.py','boundary.json'))
        commands += [('regress.py','regression.json'),('examples.py','examples.json'),
                     ('repair_checks.py','repair-checks.json'),('validate_updates.py','updates.json'),
                     ('test_update_contract.py','update-contract.json'),('validate_boolean.py','boolean-validation.json'),
                     ('generate_update_examples.py','update-examples.json')]
        for script,result in commands:
            reports.append(checked_run(script));compare_json(staged,'results/'+result)
        # Additional finite obligations have no frozen timing/result to match.
        reports.append(checked_run('finite_repair_checks.py'))
        exact=['results/validation-cases.json','results/feistel-cases.json','results/ablations.json',
               'results/prefix-defect.csv','cases/boundary.json','cases/exact-limit.json','cases/updates.json']
        if not args.quick:exact.append('results/boundary-certificate.jsonl')
        exact += [p.relative_to(ROOT).as_posix() for p in (ROOT/'examples').rglob('*') if p.is_file()]
        exact += [p.relative_to(ROOT).as_posix() for p in (ROOT/'cases/cnf').glob('*.cnf')]
        for relative in exact:compare_bytes(staged,relative)
        if args.benchmarks:
            for j in range(20):
                reports.append(checked_run('benchmark_updates.py','--case',j));compare_benchmark(staged,j)
            for name in ('split','remove','revoke'):
                reports.append(checked_run('benchmark_transfer.py','--case',name));compare_transfer(staged,name)
        fresh_smt_counts=None
        if args.smt:
            reports.append(checked_run('validate_smt.py'))
            finite=json.loads((staged/'results/smt-validation.json').read_text())
            if not finite['all_checks_passed'] or finite['actual_comparisons']!=48:
                raise RuntimeError('native finite solver validation failed')
            fresh_smt_counts={r:{s:0 for s in ('sat','unsat','unknown')} for r in ('full','reduced')}
            for j in range(20):
                for route in ('full','reduced'):
                    reports.append(checked_run('benchmark_smt.py','--case',j,'--route',route))
                    rel=f'results/smt/bench-{j:02d}-{route}.json'
                    new=json.loads((staged/rel).read_text())
                    if not new['no_incorrect_sat_answer_observed']:raise RuntimeError('wrong native solver answer')
                    for status,count in new['status_counts'].items():fresh_smt_counts[route][status]+=count
                    compare_bytes(staged,f'cases/smt/bench-{j:02d}-{route}.smt2')
            # UNKNOWN frequency is a fresh timeout observation; do not require the same
            # number of timeouts or timing wins on another host.
    if snapshot()!=before:raise RuntimeError('source extraction modified')
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    report={'project_key':'mask-aware-certificates-for-permutation-complete-stateless-scan-plans',
            'observation_kind':'fresh_clean_recheck_not_original_observation',
            'all_commands_passed':True,'complete_core_reproduction':not args.quick,
            'new_timing_cases_rerun':23 if args.benchmarks else 0,
            'native_smt_configurations_rerun':40 if args.smt else 0,
            'native_smt_fresh_status_counts':fresh_smt_counts,
            'frozen_evidence_audited_before_remeasurement':True,
            'scientific_fields_and_exact_inputs_matched':True,'source_extraction_unchanged':True,
            'upstream_certified_counting_tools_run':False,
            'outer_wall_timeout_seconds_per_child':TIMEOUT_SECONDS,'science_workers':1,
            'parent_cpu_seconds':time.process_time()-cpu,
            'children_cpu_seconds':usage.ru_utime+usage.ru_stime-usage0.ru_utime-usage0.ru_stime,
            'maximum_child_peak_rss_kib':usage.ru_maxrss,'wall_seconds':time.monotonic()-start,
            'commands':reports}
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        with args.report.open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps(report,sort_keys=True))
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (RuntimeError,OSError,ValueError) as error:raise SystemExit(str(error))
