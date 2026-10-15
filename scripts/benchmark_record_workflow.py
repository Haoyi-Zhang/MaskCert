"""Offline record-job admission: identical inputs, decisions and whole-workflow costs.

The fixture is a deterministic, owned fixed-record file, not a network workload.
Preparation is outside timing; opening/reading the input, certificate production,
checking, progress reconciliation and actual record reads are inside timing.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from io import StringIO
import gzip
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pcs.model import Invalid
from pcs.producer import write_certificate
from pcs.update_producer import write_update
from pcs.record_admission import RecordGate

METHODS = ('direct', 'full', 'incremental')


def row(lo, hi, guard):
    return dict(epoch=0, lo=lo, hi=hi, step=1, residue=0, guard=guard)


def mask_without(guard, exclude):
    # Fixture construction, independent of the arithmetic producer/checker.
    result = []
    for lo, hi in guard:
        for a, b in exclude:
            if lo < min(hi, a):
                result.append([lo, min(hi, a)])
            lo = max(lo, b)
            if lo >= hi:
                break
        if lo < hi:
            result.append([lo, hi])
    return result


def fixture(n, fragments, cycles, *, dense=False, record_size=64):
    prefix = n // 64
    spec = dict(n=n, a=5, b=17 % n,
                epochs=[dict(allow=[[0, n]], exclude=[])], history=[])
    context = {k: spec[k] for k in ('n', 'a', 'b')}
    prelude = row(0, prefix, [[0, n]])

    def tail(excluded, shifted):
        edges = [n * j // fragments for j in range(fragments + 1)]
        for j in range(1, fragments):
            if shifted and (dense or j == fragments // 2):
                edges[j] += 1
        return [row(prefix, n, mask_without([[a, b]], excluded))
                for a, b in zip(edges, edges[1:])]

    plan = dict(context=context, future=[prelude] + tail([], False))
    checkpoint_spec = deepcopy(spec)
    checkpoint_spec['history'] = [deepcopy(prelude)]
    checkpoint_plan = dict(context=context, future=tail([], False))
    # Every prelude target is below 5*prefix+17; revocation is disjoint.
    exclusions = [[n // 2 + j * (n // 32), n // 2 + j * (n // 32) + 1]
                  for j in range(4)]
    proposals = []
    for cycle in range(cycles):
        current = deepcopy(checkpoint_spec)
        revoked = deepcopy(current)
        revoked['epochs'][0]['exclude'] = deepcopy(exclusions)
        stages = [
            ('repartition', current, tail([], True)),
            ('revoke-stale', revoked, tail([], True)),
            ('revoke-repair', revoked, tail(exclusions, True)),
            ('repartition-revoked', revoked, tail(exclusions, False)),
            ('restore-stale', current, tail(exclusions, False)),
            ('restore-repair', current, tail([], False)),
            ('duplicate', current, tail([], False) + [tail([], False)[0]]),
            ('duplicate-repair', current, tail([], False)),
        ]
        for label, ss, rows in stages:
            proposals.append(dict(name=f'{cycle + 1}:{label}', declaration=deepcopy(ss),
                                  plan=dict(context=context, future=rows)))
    return dict(n=n, fragments=fragments, cycles=cycles, dense=dense,
                record_size=record_size, prefix_records=prefix,
                declaration=spec, plan=plan,
                checkpoint_declaration=checkpoint_spec, checkpoint_plan=checkpoint_plan,
                proposals=proposals)


def literal(spec, plan):
    counts = Counter()
    for rr in spec['history'] + plan['future']:
        for i in range(rr['lo'], rr['hi']):
            target = (spec['a'] * i + spec['b']) % spec['n']
            if (i % rr['step'] == rr['residue']
                    and any(a <= target < b for a, b in rr['guard'])):
                counts[rr['epoch'], target] += 1
    desired = Counter({(e, y): 1 for e, pp in enumerate(spec['epochs'])
                       for y in range(spec['n'])
                       if any(a <= y < b for a, b in pp['allow'])
                       and not any(a <= y < b for a, b in pp['exclude'])})
    return counts == desired, desired


def prepare(directory, case):
    declaration = directory / 'job.json'
    declaration.write_text(json.dumps(case, sort_keys=True), encoding='utf-8')
    records = directory / 'records.bin'
    with records.open('wb') as stream:
        for target in range(case['n']):
            stream.write(bytes((target + 17 * j) % 256 for j in range(case['record_size'])))
    return declaration, records


def execute(input_path, records_path, method):
    stages = []
    total_start, cpu_start = time.perf_counter_ns(), time.process_time_ns()

    def stage(name, operation):
        wall, cpu = time.perf_counter_ns(), time.process_time_ns()
        try:
            return operation()
        finally:
            stages.append(dict(stage=name, wall_ns=time.perf_counter_ns() - wall,
                               cpu_ns=time.process_time_ns() - cpu))

    case = stage('acquire-input', lambda: json.loads(input_path.read_text(encoding='utf-8')))
    gate = stage('open-records', lambda: RecordGate(records_path, n=case['n'],
                   record_size=case['record_size'], method=method))
    old_spec, old_plan = case['declaration'], case['plan']
    certificate_bytes = 0

    def evidence(spec, plan, *, delta):
        nonlocal certificate_bytes
        if method == 'direct':
            return None
        def produce():
            nonlocal certificate_bytes
            out = StringIO()
            if delta and method == 'incremental':
                write_update(old_spec, old_plan, spec, plan, out)
            else:
                write_certificate(spec, plan, out)
            text = out.getvalue()
            certificate_bytes += len(text.encode('utf-8'))
            return StringIO(text)
        return stage('produce-update' if delta and method == 'incremental' else 'produce-full', produce)

    consumed = []
    try:
        initial_proof = evidence(old_spec, old_plan, delta=False)
        if not stage('initial-check', lambda: gate.admit(old_spec, old_plan, initial_proof)):
            raise RuntimeError('fixture initial job rejected')
        consumed += stage('consume-prelude', lambda: gate.consume(case['prefix_records']))
        # A policy proposal after progress must fence the unreconciled stream.
        before = gate.total_reads
        try:
            stage('progress-fence', lambda: gate.replace(old_spec, old_plan, None))
        except Invalid:
            pass
        else:
            raise RuntimeError('progress was not fenced')
        try:
            gate.consume(1)
        except Invalid:
            pass
        else:
            raise RuntimeError('held job performed a read')
        if gate.total_reads != before:
            raise RuntimeError('fence changed read count')
        ss, pp = case['checkpoint_declaration'], case['checkpoint_plan']
        proof = evidence(ss, pp, delta=False)
        if not stage('reconcile-progress', lambda: gate.reconcile(ss, pp, proof)):
            raise RuntimeError('observed progress could not be reconciled')
        old_spec, old_plan = ss, pp
        cold_end = time.perf_counter_ns()
        decisions = []
        for proposal in case['proposals']:
            ss, pp = proposal['declaration'], proposal['plan']
            proof = evidence(ss, pp, delta=True)
            accepted = stage('replacement-check', lambda: gate.replace(ss, pp, proof))
            reads_before = gate.total_reads
            if accepted:
                old_spec, old_plan = ss, pp
            else:
                try:
                    gate.consume(1)
                except Invalid:
                    pass
                else:
                    raise RuntimeError('rejected replacement left readable continuation')
                if gate.total_reads != reads_before:
                    raise RuntimeError('rejected replacement consumed a record')
            decisions.append(dict(name=proposal['name'], accepted=accepted,
                                  record_reads=gate.total_reads))
        warm_end = time.perf_counter_ns()
        consumed += stage('consume-remaining', lambda: gate.consume())
        checksum = stage('consume-result', lambda: sum(sum(item.payload) for item in consumed))
        output = [(item.epoch, item.counter, item.target) for item in consumed]
        actual_reads = gate.total_reads
    finally:
        stage('close-records', gate.close)
    elapsed = time.perf_counter_ns() - total_start
    return dict(method=method, total_wall_ns=elapsed,
                total_cpu_ns=time.process_time_ns() - cpu_start,
                cold_wall_ns=cold_end - total_start, warm_wall_ns=warm_end - cold_end,
                consumed_records=len(output), actual_record_reads=actual_reads,
                consumed_bytes=actual_reads * case['record_size'], payload_sum=checksum,
                certificate_bytes=certificate_bytes, decisions=decisions, stages=stages,
                emitted=output)


def configurations(quick=False):
    if quick:
        return [fixture(128, 4, 1), fixture(256, 8, 1, dense=True)]
    return [fixture(4096, k, c) for k in (8, 32, 64) for c in (1, 4)] + [
        fixture(8192, 64, 4), fixture(4096, 64, 1, dense=True)]


def run(quick, repetitions):
    results = []
    with tempfile.TemporaryDirectory(prefix='mask-record-workflow-') as temporary:
        parent = Path(temporary)
        for index, case in enumerate(configurations(quick)):
            directory = parent / str(index)
            directory.mkdir()
            input_path, records_path = prepare(directory, case)
            oracle_cache = {}
            oracle = []
            for proposal in case['proposals']:
                key = json.dumps([proposal['declaration'], proposal['plan']], sort_keys=True)
                if key not in oracle_cache:
                    oracle_cache[key] = literal(proposal['declaration'], proposal['plan'])[0]
                oracle.append(oracle_cache[key])
            _, desired = literal(case['proposals'][-1]['declaration'], case['proposals'][-1]['plan'])
            samples = []
            canonical = None
            # Rotate method order to avoid one route always acquiring the warmest cache.
            for repetition in range(repetitions):
                order = METHODS[repetition % 3:] + METHODS[:repetition % 3]
                for method in order:
                    observation = execute(input_path, records_path, method)
                    output = observation.pop('emitted')
                    if [p['accepted'] for p in observation['decisions']] != oracle:
                        raise RuntimeError('decision disagrees with finite pointwise oracle')
                    if Counter((e, y) for e, _, y in output) != desired:
                        raise RuntimeError('actual reads differ from final desired membership')
                    if canonical is None:
                        canonical = output
                    elif canonical != output:
                        raise RuntimeError('methods consumed different record sequences')
                    if observation['actual_record_reads'] != len(output):
                        raise RuntimeError('read count differs from actual record consumption')
                    observation['repetition'] = repetition
                    samples.append(observation)
            medians = {method: {field: statistics.median(s[field] for s in samples if s['method'] == method)
                                for field in ('total_wall_ns', 'total_cpu_ns', 'cold_wall_ns', 'warm_wall_ns')}
                       for method in METHODS}
            results.append(dict(case=index, input=case, pointwise_decisions=oracle,
                                samples=samples, medians=medians))
    return dict(all_checks_passed=True, workload='owned-fixed-record-job',
                quick=quick, repetitions=repetitions, cases=len(results),
                same_input_and_decisions=True, same_consumed_record_sequences=True,
                measurements_include=['input acquisition', 'record file open', 'certificate production',
                    'full/reduced checking', 'observed history reconciliation', 'actual record reads',
                    'payload aggregation', 'file close'],
                measurements_exclude=['fixture generation', 'pointwise oracle', 'report serialization'],
                environment=dict(platform=platform.platform(), python=sys.version,
                    executable=sys.executable, machine=platform.machine(), processor=platform.processor(),
                    logical_cpus=os.cpu_count(), timer='perf_counter_ns; process_time_ns',
                    wall_timer_resolution_seconds=time.get_clock_info('perf_counter').resolution,
                    cpu_timer_resolution_seconds=time.get_clock_info('process_time').resolution,
                    affinity='not set', peak_rss='not measured', persistence='buffered local reads'),
                results=results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--out', type=Path, required=True, help='new observation path; never overwritten')
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 30:
        parser.error('--repetitions must be in 1..30')
    if args.out.exists():
        parser.error('--out must not already exist')
    report = run(args.quick, args.repetitions)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if args.out.suffix == '.gz' else open
    with opener(args.out, 'xt', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('all_checks_passed', 'cases', 'repetitions', 'quick')}))


if __name__ == '__main__':
    main()
