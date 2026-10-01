"""Clean, non-overwriting scientific recheck.

The script stages a private temporary copy, runs every scientific component
there under the child limits declared in scripts/common.py, and compares the
new outputs with the retained evidence. The source extraction is never used as
an output directory. Paper compilation and figure export are intentionally
separate optional commands.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 120


def digest(path: Path) -> bytes:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.digest()


def source_snapshot():
    # Internal mutation detector only; no checksum manifest is written.
    excluded = {'__pycache__'}
    return {
        path.relative_to(ROOT).as_posix(): digest(path)
        for path in ROOT.rglob('*')
        if path.is_file() and not any(part in excluded for part in path.parts)
    }


def scientific(value):
    if isinstance(value, dict):
        return {
            key: scientific(item)
            for key, item in value.items()
            if 'cpu_' not in key and key not in ('peak_rss_kib', 'workers')
        }
    if isinstance(value, list):
        return [scientific(item) for item in value]
    return value


def run_child(staged: Path, script: str):
    process = subprocess.Popen(
        [sys.executable, str(staged / 'scripts' / script)],
        cwd=staged,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as ex:
        # Kill the entire child session, including any CLI subprocess spawned by
        # a contract test. Killing only the direct child would not be an outer
        # wall-time bound on the scientific command.
        if hasattr(os, 'killpg'):
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        stdout, stderr = process.communicate()
        raise SystemExit(
            f'{script} exceeded the {TIMEOUT_SECONDS}-second outer bound\n'
            f'--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}'
        ) from ex
    if process.returncode != 0:
        raise SystemExit(
            f'{script} failed with {process.returncode}\n'
            f'--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}'
        )
    return {
        'script': script,
        'returncode': process.returncode,
        'stdout_last_line': stdout.strip().splitlines()[-1] if stdout.strip() else '',
        'stderr': stderr.strip(),
    }


def compare_json(expected: Path, actual: Path, ignore_timing=True):
    left = json.loads(expected.read_text())
    right = json.loads(actual.read_text())
    if ignore_timing:
        left, right = scientific(left), scientific(right)
    if left != right:
        raise SystemExit(f'scientific-result mismatch: {expected.relative_to(ROOT)}')


def compare_bytes(expected: Path, actual: Path):
    if expected.stat().st_size != actual.stat().st_size or digest(expected) != digest(actual):
        raise SystemExit(f'byte mismatch: {expected.relative_to(ROOT)}')


def write_exclusive(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path,
                        help='optional non-existing path for the recheck report')
    parser.add_argument('--quick', action='store_true',
                        help='skip the large boundary run; not a full reproduction')
    args = parser.parse_args()

    if args.report is not None:
        report_path = args.report.resolve()
        if report_path.exists():
            raise SystemExit('report path already exists')
        if report_path.is_relative_to(ROOT.resolve()):
            raise SystemExit('report path must be outside the source extraction')
        args.report = report_path

    if hasattr(os, 'sched_setaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})

    before = source_snapshot()
    start_wall = time.monotonic()
    start_cpu = time.process_time()
    child_start = resource.getrusage(resource.RUSAGE_CHILDREN)

    expected_json = ['identity-audit.json', 'dependency-audit.json', 'pilot.json', 'validation.json', 'regression.json', 'examples.json']
    commands = ['audit_identity.py', 'audit_dependencies.py', 'pilot.py', 'validate.py']
    if not args.quick:
        commands.append('boundary.py')
        expected_json.append('boundary.json')
    commands.extend(['regress.py', 'examples.py'])

    exact_files = [
        'results/validation-cases.json',
        'results/feistel-cases.json',
        'results/ablations.json',
        'results/prefix-defect.csv',
        'cases/boundary.json',
        'cases/exact-limit.json',
        'examples/declaration.json',
        'examples/plan.json',
        'examples/certificate.jsonl',
        'examples/fault-declaration.json',
        'examples/fault-plan.json',
        'examples/witness/witness.json',
        'examples/witness/full.jsonl',
        'examples/witness/before.jsonl',
        'examples/witness/through.jsonl',
    ]
    if not args.quick:
        exact_files.append('results/boundary-certificate.jsonl')

    with tempfile.TemporaryDirectory(prefix='mask-aware-recheck-') as tmp:
        staged = Path(tmp) / 'mask-aware-certificates-artifact'
        shutil.copytree(
            ROOT,
            staged,
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'),
        )
        # Audit the copied retained evidence before any fresh experiment rewrites
        # timing fields in the staged results. This preserves the distinction
        # between original observations and the clean recheck.
        evidence = run_child(staged, 'audit_evidence.py')
        evidence_report = json.loads(evidence['stdout_last_line'])
        retained_evidence = json.loads((ROOT / 'results' / 'evidence-map.json').read_text())
        if not evidence_report.get('all_checks_passed'):
            raise SystemExit('evidence map audit failed')
        if evidence_report != retained_evidence:
            raise SystemExit('retained evidence-map result mismatch')
        compare_bytes(ROOT / 'docs' / 'evidence-map.md', staged / 'docs' / 'evidence-map.md')

        child_reports = [evidence]
        child_reports.extend(run_child(staged, command) for command in commands)

        for name in expected_json:
            compare_json(ROOT / 'results' / name, staged / 'results' / name)
        for relative in exact_files:
            compare_bytes(ROOT / relative, staged / relative)

        repair = run_child(staged, 'repair_checks.py')
        child_reports.append(repair)

        repair_report = json.loads(repair['stdout_last_line'])
        if not repair_report.get('all_checks_passed'):
            raise SystemExit('repair contract checks failed')
        retained_repair = json.loads((ROOT / 'results' / 'repair-checks.json').read_text())
        if repair_report != retained_repair:
            raise SystemExit('repair-contract result mismatch')

    after = source_snapshot()
    if before != after:
        raise SystemExit('source extraction changed during recheck')

    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {
        'project_key': 'mask-aware-certificates-for-permutation-complete-stateless-scan-plans',
        'observation_kind': 'fresh_clean_recheck_not_original_observation',
        'full_reproduction': not args.quick,
        'all_commands_passed': True,
        'scientific_fields_match_retained_evidence': True,
        'claim_critical_files_match_byte_for_byte': True,
        'repair_and_evidence_reports_match_retained_records': True,
        'source_extraction_unchanged': True,
        'sequential_commands': ['audit_evidence.py'] + commands + ['repair_checks.py'],
        'outer_timeout_seconds_per_child': TIMEOUT_SECONDS,
        'workers': 1,
        'parent_cpu_seconds': time.process_time() - start_cpu,
        'children_cpu_seconds': (
            children.ru_utime + children.ru_stime
            - child_start.ru_utime - child_start.ru_stime
        ),
        'maximum_child_peak_rss_kib': children.ru_maxrss,
        'wall_seconds': time.monotonic() - start_wall,
        'child_reports': child_reports,
    }
    text = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.report:
        write_exclusive(args.report, text)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
