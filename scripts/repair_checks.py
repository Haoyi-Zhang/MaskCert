"""Repair-specific contract checks, separate from the frozen Table-II counts.

This script is read-only with respect to retained inputs and results unless an
explicit, non-existing --out path is supplied. It does not modify paper assets.
"""
from __future__ import annotations

import argparse
import ast
import copy
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from common import ROOT, bounded
from casegen import mkrow
from pcs.checker import TranscriptReader, check_witness, verify
from pcs.model import (
    EXPLICIT_ORACLE_LIMIT,
    MAX_CERTIFICATE_BYTES,
    MAX_CERTIFICATE_LINE_BYTES,
    MAX_INPUT_BYTES,
    MAX_EPOCHS,
    MAX_INTERVALS,
    MAX_N,
    MAX_ROWS,
    MAX_STEP,
    MAX_TRANSCRIPT_INTEGER,
    Invalid,
    certificate_lines,
    load,
    validate,
)
from pcs.oracle import enumerate_counters, replay_audit, require_explicit_domain
from pcs.producer import defects, locate, write_certificate


def reject(fn, label: str) -> str:
    try:
        fn()
    except Invalid as exc:
        return str(exc)
    raise AssertionError(f'{label}: invalid object accepted')


def certificate(spec, plan, prefix=None) -> str:
    stream = io.StringIO()
    write_certificate(spec, plan, stream, prefix)
    return stream.getvalue()


def checked_defects(spec, plan, prefix=None):
    text = certificate(spec, plan, prefix)
    return verify(spec, plan, io.StringIO(text), prefix), text


def semantic_controls():
    controls = []

    # Unauthorized multiplicity is linear m, not m^2.
    spec = dict(n=4, a=1, b=0, epochs=[dict(allow=[], exclude=[])], history=[])
    repeated = mkrow(0, 0, 1, 1, 0, [[0, 4]])
    plan = dict(context=dict(n=4, a=1, b=0), future=[repeated, copy.deepcopy(repeated)])
    check, _ = checked_defects(spec, plan)
    exact, witness = enumerate_counters(spec, plan)
    assert exact == replay_audit(spec, plan) == defects(spec, plan) == [2]
    assert not check.accepted and witness == {
        'epoch': 0, 'counter': 0, 'target': 0, 'kind': 'forbidden', 'rows': [0]
    }
    controls.append(dict(case='empty-authorization-repeated-output', defects=exact,
                         unauthorized_multiplicity=2,
                         linear_penalty=2, squared_penalty_not_used=4))

    # An empty fragment is a distinct row position but contributes no occurrence.
    spec = dict(n=4, a=1, b=0, epochs=[dict(allow=[[0, 4]], exclude=[])], history=[])
    plan = dict(context=dict(n=4, a=1, b=0), future=[
        mkrow(0, 0, 4, 1, 0, [[0, 4]]),
        mkrow(0, 2, 2, 1, 0, [[0, 4]]),
    ])
    check, _ = checked_defects(spec, plan)
    assert check.accepted and defects(spec, plan) == [0]
    controls.append(dict(case='empty-fragment', accepted=True, defects=[0]))

    # Raw source overlap at an excluded target is harmless after both guards.
    spec = dict(n=8, a=3, b=1,
                epochs=[dict(allow=[[0, 8]], exclude=[[1, 2]])], history=[])
    guard = [[0, 1], [2, 8]]
    plan = dict(context=dict(n=8, a=3, b=1), future=[
        mkrow(0, 0, 8, 1, 0, guard),
        mkrow(0, 0, 1, 1, 0, guard),
    ])
    check, _ = checked_defects(spec, plan)
    assert check.accepted and defects(spec, plan) == [0]
    controls.append(dict(case='overlap-only-at-exclusion', accepted=True, defects=[0]))

    # Identical source ranges can be safe when guards are mutually exclusive.
    spec = dict(n=8, a=3, b=1,
                epochs=[dict(allow=[[0, 8]], exclude=[])], history=[])
    plan = dict(context=dict(n=8, a=3, b=1), future=[
        mkrow(0, 0, 8, 1, 0, [[0, 4]]),
        mkrow(0, 0, 8, 1, 0, [[4, 8]]),
    ])
    check, _ = checked_defects(spec, plan)
    assert check.accepted and defects(spec, plan) == [0]
    controls.append(dict(case='mutually-exclusive-guards', accepted=True, defects=[0]))

    # Reusing the same target in different retry epochs is allowed: the object
    # being certified is (epoch,target), not global physical transmission.
    spec = dict(n=4, a=1, b=0,
                epochs=[dict(allow=[[0, 4]], exclude=[]),
                        dict(allow=[[0, 4]], exclude=[])], history=[])
    plan = dict(context=dict(n=4, a=1, b=0), future=[
        mkrow(0, 0, 4, 1, 0, [[0, 4]]),
        mkrow(1, 0, 4, 1, 0, [[0, 4]]),
    ])
    check, _ = checked_defects(spec, plan)
    assert check.accepted and defects(spec, plan) == [0, 0]
    controls.append(dict(case='cross-epoch-target-reuse', accepted=True, defects=[0, 0]))

    # History is supplied only by the declaration; the continuation cannot
    # replace it. A safe continuation completes the remaining prefix, whereas
    # duplicating the declared history is detected.
    spec = dict(n=8, a=3, b=1, epochs=[dict(allow=[[0, 8]], exclude=[])],
                history=[mkrow(0, 0, 4, 1, 0, [[0, 8]])])
    plan = dict(context=dict(n=8, a=3, b=1),
                future=[mkrow(0, 4, 8, 1, 0, [[0, 8]])])
    safe, safe_text = checked_defects(spec, plan)
    assert safe.accepted
    duplicated = copy.deepcopy(plan)
    duplicated['future'].append(mkrow(0, 0, 4, 1, 0, [[0, 8]]))
    unsafe, _ = checked_defects(spec, duplicated)
    assert not unsafe.accepted and defects(spec, duplicated) == [4]
    changed_declaration = copy.deepcopy(spec)
    changed_declaration['history'] = []
    reject(lambda: verify(changed_declaration, plan, io.StringIO(safe_text)),
           'changed declaration must not reuse certificate')
    controls.append(dict(case='declared-history-protection', safe_defects=[0],
                         duplicated_history_defects=[4]))

    return controls


def witness_checks():
    spec = load(ROOT / 'examples' / 'fault-declaration.json')
    plan = load(ROOT / 'examples' / 'fault-plan.json')
    bundle = ROOT / 'examples' / 'witness'
    witness = load(bundle / 'witness.json')
    assert witness == {
        'epoch': 0, 'counter': 2, 'target': 17, 'kind': 'omission', 'rows': []
    }
    assert locate(spec, plan) == witness
    assert defects(spec, plan, 50) == [12]
    assert check_witness(
        spec, plan, witness,
        certificate_lines(bundle / 'full.jsonl'),
        certificate_lines(bundle / 'before.jsonl'),
        certificate_lines(bundle / 'through.jsonl'),
    )

    swapped = reject(
        lambda: check_witness(
            spec, plan, witness,
            certificate_lines(bundle / 'full.jsonl'),
            certificate_lines(bundle / 'through.jsonl'),
            certificate_lines(bundle / 'before.jsonl'),
        ),
        'swapped adjacent prefixes',
    )
    changed = copy.deepcopy(witness)
    changed['rows'] = [0]
    changed_rows = reject(
        lambda: check_witness(
            spec, plan, changed,
            certificate_lines(bundle / 'full.jsonl'),
            certificate_lines(bundle / 'before.jsonl'),
            certificate_lines(bundle / 'through.jsonl'),
        ),
        'changed canonical row positions',
    )
    return dict(witness=witness, defect_at_prefix_50=12,
                swapped_prefix_rejection=swapped,
                changed_row_rejection=changed_rows)


def transcript_checks():
    spec = load(ROOT / 'examples' / 'declaration.json')
    plan = load(ROOT / 'examples' / 'plan.json')
    text = (ROOT / 'examples' / 'certificate.jsonl').read_text()
    lines = text.splitlines(keepends=True)
    assert verify(spec, plan, io.StringIO(text)).accepted

    # The first floor record exists for this example.
    value_mutation = copy.deepcopy(lines)
    rec = json.loads(value_mutation[1])
    rec[0] += 1
    value_mutation[1] = json.dumps(rec) + '\n'
    bad_value = reject(lambda: verify(spec, plan, value_mutation), 'bad floor value')

    quotient_mutation = copy.deepcopy(lines)
    rec = json.loads(quotient_mutation[1])
    rec[1][0][0] += 1
    quotient_mutation[1] = json.dumps(rec) + '\n'
    bad_quotient = reject(lambda: verify(spec, plan, quotient_mutation), 'bad quotient')

    truncated = reject(lambda: verify(spec, plan, lines[:-1]), 'truncated transcript')
    trailing = reject(lambda: verify(spec, plan, lines + ['{}\n']), 'trailing record')

    # Prefix binding is explicit and whole-plan verification cannot consume a
    # prefix-zero certificate.
    prefix_zero = certificate(spec, plan, 0)
    prefix_binding = reject(lambda: verify(spec, plan, io.StringIO(prefix_zero)),
                            'prefix certificate used as full certificate')

    # Input binding is semantic reconstruction, not a cryptographic commitment.
    changed_plan = copy.deepcopy(plan)
    changed_plan['future'][0]['guard'] = [[1, 2]]
    semantic_binding = reject(
        lambda: verify(spec, changed_plan, io.StringIO(text)),
        'certificate reused for changed guard',
    )

    too_many_steps = json.dumps([0, [[0, 0, 0]] * 69])
    transcript_steps = reject(
        lambda: TranscriptReader([too_many_steps]).floor(0, 1, 0, 0),
        '69-step floor transcript',
    )
    exact_total = TranscriptReader(['{}\n'])
    exact_total.bytes = MAX_CERTIFICATE_BYTES - len('{}\n'.encode('utf-8'))
    assert exact_total.take() == {}
    reader = TranscriptReader(['{}\n'])
    reader.bytes = MAX_CERTIFICATE_BYTES - len('{}\n'.encode('utf-8')) + 1
    total_bytes = reject(reader.take, 'certificate total byte bound')

    return dict(
        bad_value=bad_value,
        bad_quotient=bad_quotient,
        truncated=truncated,
        trailing=trailing,
        prefix_binding=prefix_binding,
        semantic_input_binding=semantic_binding,
        floor_step_bound=transcript_steps,
        certificate_total_exact_accepted=MAX_CERTIFICATE_BYTES,
        certificate_total_boundary_plus_one=total_bytes,
    )


def schema_and_limit_checks():
    # Fragment-count boundary and boundary+1.
    full = [[0, 2]]
    row = mkrow(0, 0, 0, 1, 0, full)
    spec = dict(n=2, a=1, b=0, epochs=[dict(allow=full, exclude=[])], history=[])
    plan = dict(context=dict(n=2, a=1, b=0),
                future=[copy.deepcopy(row) for _ in range(MAX_ROWS)])
    validate(spec, plan)
    too_many_rows = copy.deepcopy(plan)
    too_many_rows['future'].append(copy.deepcopy(row))
    row_bound = reject(lambda: validate(spec, too_many_rows), 'row boundary+1')

    # Interval-count boundary and boundary+1 with canonical nonadjacent spans.
    n = 2 * (MAX_INTERVALS + 1)
    max_mask = [[2 * i, 2 * i + 1] for i in range(MAX_INTERVALS)]
    spec_intervals = dict(n=n, a=1, b=0,
                          epochs=[dict(allow=max_mask, exclude=[])], history=[])
    plan_intervals = dict(context=dict(n=n, a=1, b=0), future=[])
    validate(spec_intervals, plan_intervals)
    too_many_mask = max_mask + [[2 * MAX_INTERVALS, 2 * MAX_INTERVALS + 1]]
    bad_spec = copy.deepcopy(spec_intervals)
    bad_spec['epochs'][0]['allow'] = too_many_mask
    interval_bound = reject(lambda: validate(bad_spec, plan_intervals),
                            'interval boundary+1')

    # Epoch boundary and boundary+1.
    spec_epochs = dict(n=1, a=0, b=0,
                       epochs=[dict(allow=[[0, 1]], exclude=[])
                               for _ in range(MAX_EPOCHS)], history=[])
    plan_epochs = dict(context=dict(n=1, a=0, b=0), future=[])
    validate(spec_epochs, plan_epochs)
    bad_epochs = copy.deepcopy(spec_epochs)
    bad_epochs['epochs'].append(dict(allow=[[0, 1]], exclude=[]))
    epoch_bound = reject(lambda: validate(bad_epochs, plan_epochs),
                         'epoch boundary+1')

    # Explicit-oracle static boundary and boundary+1.
    assert require_explicit_domain(EXPLICIT_ORACLE_LIMIT) == EXPLICIT_ORACLE_LIMIT
    oracle_bound = reject(lambda: require_explicit_domain(EXPLICIT_ORACLE_LIMIT + 1),
                          'explicit oracle boundary+1')

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        exact_input = tmp / 'exact-input.json'
        exact_input.write_bytes(b'{}' + b' ' * (MAX_INPUT_BYTES - 2))
        assert load(exact_input) == {}
        oversized_input = tmp / 'oversized.json'
        oversized_input.write_bytes(b'{}' + b' ' * (MAX_INPUT_BYTES - 1))
        input_bound = reject(lambda: load(oversized_input), '8 MiB input boundary+1')

        exact_line = tmp / 'exact-line.jsonl'
        exact_line.write_bytes(b' ' * (MAX_CERTIFICATE_LINE_BYTES - 3) + b'{}\n')
        exact_lines = list(certificate_lines(exact_line))
        assert len(exact_lines) == 1 and len(exact_lines[0].encode('utf-8')) == MAX_CERTIFICATE_LINE_BYTES
        long_line = tmp / 'long.jsonl'
        long_line.write_bytes(b' ' * (MAX_CERTIFICATE_LINE_BYTES - 2) + b'{}\n')
        line_bound = reject(lambda: list(certificate_lines(long_line)),
                            'certificate line boundary+1')

        # Exercise the public streaming reader at the exact 64-MiB total and at
        # total+1. Every component line is independently within the line cap.
        total_path = tmp / 'total-boundary.jsonl'
        line = b' ' * (MAX_CERTIFICATE_LINE_BYTES - 1) + b'\n'
        with total_path.open('wb') as stream:
            for _ in range(MAX_CERTIFICATE_BYTES // MAX_CERTIFICATE_LINE_BYTES):
                stream.write(line)
        assert sum(len(part.encode('utf-8')) for part in certificate_lines(total_path)) == MAX_CERTIFICATE_BYTES
        with total_path.open('ab') as stream:
            stream.write(b'\n')
        total_bound = reject(lambda: sum(1 for _ in certificate_lines(total_path)),
                             'certificate total boundary+1 through public reader')

    # Symbolic schema domain and modulus boundaries are separate from the
    # smaller explicit-oracle limit.
    max_spec = dict(n=MAX_N, a=1, b=0,
                    epochs=[dict(allow=[], exclude=[])], history=[])
    max_plan = dict(context=dict(n=MAX_N, a=1, b=0), future=[
        mkrow(0, 0, 0, MAX_STEP, MAX_STEP - 1, [])
    ])
    validate(max_spec, max_plan)
    bad_n_spec = copy.deepcopy(max_spec)
    bad_n_spec['n'] = MAX_N + 1
    bad_n_plan = copy.deepcopy(max_plan)
    bad_n_plan['context']['n'] = MAX_N + 1
    domain_bound = reject(lambda: validate(bad_n_spec, bad_n_plan), 'domain boundary+1')
    bad_step = copy.deepcopy(max_plan)
    bad_step['future'][0]['step'] = MAX_STEP + 1
    bad_step['future'][0]['residue'] = MAX_STEP
    step_bound = reject(lambda: validate(max_spec, bad_step), 'modulus boundary+1')

    # Transcript integer values are accepted through 2^128-1 and rejected at
    # 2^128 before arithmetic can use them.
    exact_integer = json.dumps([MAX_TRANSCRIPT_INTEGER, [[0, MAX_TRANSCRIPT_INTEGER, 0]]])
    assert TranscriptReader([exact_integer]).floor(1, 1, 0, MAX_TRANSCRIPT_INTEGER) == MAX_TRANSCRIPT_INTEGER
    oversized_integer = json.dumps([MAX_TRANSCRIPT_INTEGER + 1, [[0, MAX_TRANSCRIPT_INTEGER, 0]]])
    transcript_integer_bound = reject(
        lambda: TranscriptReader([oversized_integer]).floor(1, 1, 0, MAX_TRANSCRIPT_INTEGER),
        'transcript integer boundary+1',
    )

    return dict(
        max_rows_accepted=MAX_ROWS,
        row_boundary_plus_one=row_bound,
        max_intervals_accepted=MAX_INTERVALS,
        interval_boundary_plus_one=interval_bound,
        max_epochs_accepted=MAX_EPOCHS,
        epoch_boundary_plus_one=epoch_bound,
        explicit_oracle_limit=EXPLICIT_ORACLE_LIMIT,
        explicit_oracle_boundary_plus_one=oracle_bound,
        input_exact_bytes_accepted=MAX_INPUT_BYTES,
        input_boundary_plus_one=input_bound,
        certificate_line_exact_bytes_accepted=MAX_CERTIFICATE_LINE_BYTES,
        certificate_line_boundary_plus_one=line_bound,
        certificate_total_exact_bytes_accepted_through_public_reader=MAX_CERTIFICATE_BYTES,
        certificate_total_boundary_plus_one_through_public_reader=total_bound,
        symbolic_domain_exact_accepted=MAX_N,
        symbolic_domain_boundary_plus_one=domain_bound,
        modulus_exact_accepted=MAX_STEP,
        modulus_boundary_plus_one=step_bound,
        transcript_integer_exact_accepted=MAX_TRANSCRIPT_INTEGER,
        transcript_integer_boundary_plus_one=transcript_integer_bound,
    )


def independence_check():
    paths = {
        'checker': ROOT / 'src' / 'pcs' / 'checker.py',
        'producer': ROOT / 'src' / 'pcs' / 'producer.py',
    }
    module_imports = {}
    forbidden = {}
    for role, path in paths.items():
        tree = ast.parse(path.read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = ('.' * node.level) + (node.module or '')
                imports.append(module)
        module_imports[role] = imports
        other = 'producer' if role == 'checker' else 'checker'
        forbidden[role] = [name for name in imports if other in name or 'oracle' in name]
        assert not forbidden[role]

    checker_source = paths['checker'].read_text()
    producer_source = paths['producer'].read_text()
    assert 'Endpoint sweep' in checker_source
    assert 'def extended' in checker_source
    assert 'invalid quotient witness' in checker_source
    assert 'def overlap' in producer_source and 'def intersect_rows' in producer_source
    assert 'pow(s//g,-1,q)' in producer_source
    assert 'def floor_transcript' in producer_source
    assert 'def extended' not in producer_source
    assert 'pow(' not in checker_source
    return dict(
        module_imports=module_imports,
        forbidden_cross_oracle_imports=forbidden,
        checker_arithmetic=['endpoint sweep', 'extended Euclidean lattice',
                            'verified quotient/remainder triples'],
        producer_arithmetic=['two-pointer interval overlap', 'modular inverse CRT',
                             'producer floor recurrence'],
        shared_components=['pcs.model schema/parser/limits',
                           'Python interpreter and arbitrary-precision integers'],
        oracle_dependency='none in producer/checker; explicit oracles are validation only',
    )


def cli_contract():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        spec = load(ROOT / 'examples' / 'declaration.json')
        safe_plan = load(ROOT / 'examples' / 'plan.json')
        unsafe_plan = load(ROOT / 'examples' / 'fault-plan.json')
        spec_path = tmp / 'declaration.json'
        safe_path = tmp / 'safe-plan.json'
        unsafe_path = tmp / 'unsafe-plan.json'
        safe_cert = tmp / 'safe.jsonl'
        unsafe_cert = tmp / 'unsafe.jsonl'
        broken_cert = tmp / 'broken.jsonl'
        spec_path.write_text(json.dumps(spec))
        safe_path.write_text(json.dumps(safe_plan))
        unsafe_path.write_text(json.dumps(unsafe_plan))
        safe_cert.write_text(certificate(spec, safe_plan))
        unsafe_cert.write_text(certificate(spec, unsafe_plan))
        broken_cert.write_text(''.join(unsafe_cert.read_text().splitlines(keepends=True)[:-1]))

        def run(plan_path, cert_path):
            process = subprocess.run(
                [sys.executable, str(ROOT / 'pcs.py'), 'check',
                 str(spec_path), str(plan_path), str(cert_path)],
                cwd=ROOT, text=True, capture_output=True, timeout=20,
            )
            return dict(returncode=process.returncode,
                        stdout=process.stdout.strip(), stderr=process.stderr.strip())

        safe = run(safe_path, safe_cert)
        unsafe = run(unsafe_path, unsafe_cert)
        damaged = run(unsafe_path, broken_cert)
        assert safe['returncode'] == 0
        assert unsafe['returncode'] == 1
        assert damaged['returncode'] == 2
        return dict(safe=safe, unsafe=unsafe, malformed_or_corrupt=damaged,
                    contract={'safe': 0, 'unsafe': 1, 'malformed_or_unsupported': 2})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    bounded()
    report = dict(
        project_key='mask-aware-certificates-for-permutation-complete-stateless-scan-plans',
        observation_kind='repair_recheck_not_original_observation',
        semantic_controls=semantic_controls(),
        witness=witness_checks(),
        transcript_contract=transcript_checks(),
        schema_and_limits=schema_and_limit_checks(),
        independence=independence_check(),
        cli=cli_contract(),
        all_checks_passed=True,
    )
    text = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x', encoding='utf-8') as stream:
            stream.write(text)
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
