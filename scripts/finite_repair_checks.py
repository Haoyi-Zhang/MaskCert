"""Additional finite arithmetic/Boolean obligations; no native solver or network.

The original Boolean suite is retained separately. This suite checks every
source prefix on specified non-power-of-two domains and selected maximum-row
boundary assignments, without claiming exhaustive validation of the format.
"""
from common import ROOT, bounded, finish
bounded()
from copy import deepcopy
from io import StringIO
from itertools import product
import json
import random
from casegen import mkrow, spans_from_bits
from pcs.model import Invalid, loads, MAX_ROWS
from pcs.producer import write_certificate, floor_transcript, count
from pcs.checker import TranscriptReader, masked
from pcs.oracle import enumerate_counters, replay_audit
from pcs.boolean_encoding import encode_full, encode_update
from pcs.update_checker import establish_anchor


def anchor_for(spec, plan):
    stream = StringIO()
    write_certificate(spec, plan, stream)
    return establish_anchor(spec, plan, StringIO(stream.getvalue()))


def main():
    parser_checks = []
    for text in ('{"x":1e400}', '{"x":-1e400}', '{"x":1.0e400}',
                 '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}'):
        try:
            loads(text)
        except Invalid as error:
            parser_checks.append({'input': text, 'rejection': str(error)})
        else:
            raise AssertionError('nonfinite token accepted: ' + text)
    assert loads('{"x":1e2}') == {'x': 100.0}
    # Finite floating-point tokens can be parsed, but schema integer fields
    # still reject them; this does not broaden the integer-only language.
    from pcs.model import validate
    float_spec = {'n': 2.0, 'a': 1, 'b': 0,
                  'epochs': [{'allow': [[0, 2]], 'exclude': []}], 'history': []}
    try:
        validate(float_spec, {'context': {'n': 2, 'a': 1, 'b': 0}, 'future': []})
    except Invalid:
        pass
    else:
        raise AssertionError('floating-point domain accepted')

    # Exact floor/mask checks at large integer widths with finite progressions.
    rng = random.Random(10020261006)
    arithmetic = []
    for n in (1, 7, 65, 1 << 20, 1 << 32):
        for trial in range(16):
            a, b = (0, 0) if n == 1 else (n - 1, rng.randrange(n))
            first = rng.randrange(n)
            delta = rng.randrange(1, 4033)
            length = min(32, (n - 1 - first) // delta + 1)
            lo = rng.randrange(n + 1)
            hi = rng.randrange(lo, n + 1)
            mask = [] if lo == hi else [[lo, hi]]
            expected = sum(lo <= (a * (first + delta * j) + b) % n < hi
                           for j in range(length))
            records = []
            def floor(z, m, alpha, beta):
                value, steps = floor_transcript(z, m, alpha, beta)
                assert value == sum((alpha * j + beta) // m for j in range(z))
                records.append(json.dumps([value, steps]))
                return value
            result = count((first, delta, length), mask, n, a, b, floor)
            reader = TranscriptReader(records)
            checked = masked((first, delta, length), mask, n, a, b, reader)
            reader.finish()
            assert result == checked == expected
            arithmetic.append({'n': n, 'trial': trial, 'first': first,
                               'step': delta, 'length': length, 'mask': mask,
                               'count': checked, 'floor_queries': reader.calls})

    encoding_records = []
    assignments = 0
    for n in (3, 5, 9):
        a, b = n - 1, 1
        old_mask = spans_from_bits([i % 2 == 0 for i in range(n)])
        old_spec = {'n': n, 'a': a, 'b': b,
                    'epochs': [{'allow': old_mask, 'exclude': []}],
                    'history': [mkrow(0, 0, 1, 1, 0, old_mask)]}
        old_plan = {'context': {k: old_spec[k] for k in ('n', 'a', 'b')},
                    'future': [mkrow(0, 1, n, 2, residue, old_mask)
                               for residue in range(2)]}
        anchor = anchor_for(old_spec, old_plan)
        spec, plan = deepcopy(old_spec), deepcopy(old_plan)
        spec['epochs'][0] = {'allow': [[0, n]], 'exclude': [[1, 2]]}
        plan['future'].pop(0)
        plan['future'].append(mkrow(0, 0, n, 1, 0, [[0, n]]))
        assert enumerate_counters(spec, plan)[0] == replay_audit(spec, plan)
        for prefix in range(n + 1):
            truth = enumerate_counters(spec, plan, prefix)[0][0]
            for route, circuit in (('full', encode_full(spec, plan, prefix=prefix)),
                                   ('reduced', encode_update(anchor, spec, plan, prefix=prefix))):
                models = 0
                invalid_source_models = 0
                checked_assignments = 0
                ranges = [range(1 << len(circuit.inputs[label])) for label in ('i', 'p', 'q')]
                for values in product(*ranges):
                    accepted = circuit.evaluate(dict(zip(('i', 'p', 'q'), values)))
                    models += accepted
                    invalid_source_models += accepted and values[0] >= n
                    checked_assignments += 1
                assert models == truth and invalid_source_models == 0
                assignments += checked_assignments
                encoding_records.append({'n': n, 'prefix': prefix, 'route': route,
                                         'models': models, 'oracle_defect': truth,
                                         'invalid_source_models': invalid_source_models,
                                         'primary_assignments': checked_assignments,
                                         'variables': circuit.variables,
                                         'clauses': len(circuit.clauses)})

    # Maximum multiplicity is represented without wraparound. Only selected
    # boundary assignments are evaluated here, not all token assignments.
    old_spec = {'n': 1, 'a': 0, 'b': 0,
                'epochs': [{'allow': [[0, 1]], 'exclude': []}], 'history': []}
    row = mkrow(0, 0, 1, 1, 0, [[0, 1]])
    old_plan = {'context': {'n': 1, 'a': 0, 'b': 0}, 'future': [row]}
    anchor = anchor_for(old_spec, old_plan)
    plan = deepcopy(old_plan)
    plan['future'] = [deepcopy(row) for _ in range(MAX_ROWS)]
    boundaries = []
    for wanted in (False, True):
        spec = deepcopy(old_spec)
        spec['epochs'][0]['allow'] = [[0, 1]] if wanted else []
        for route, circuit in (('full', encode_full(spec, plan)),
                               ('reduced', encode_update(anchor, spec, plan))):
            assert len(circuit.inputs['p']) == len(circuit.inputs['q']) == 8
            for i, p, q in product((0, 1), (0, 126, 127, 128, 255), (0, 126, 127, 128, 255)):
                expected = i == 0 and ((p < 127 and q < 127) if wanted else (p < 128 and q == 0))
                assert circuit.evaluate({'i': i, 'p': p, 'q': q}) == expected
                boundaries.append({'wanted': wanted, 'route': route, 'i': i,
                                   'p': p, 'q': q, 'accepted': expected})
    finish('finite-repair-checks.json', {
        'observation_kind': 'additional_bounded_finite_math_checks_2026_10_06',
        'all_checks_passed': True, 'nonfinite_rejections': parser_checks,
        'finite_float_schema_rejected': True,
        'large_integer_progression_cases': arithmetic,
        'prefix_encodings': encoding_records,
        'prefix_encodings_compared': len(encoding_records),
        'primary_assignments_checked': assignments,
        'maximum_row_boundary_assignments': boundaries,
        'maximum_row_boundary_checks': len(boundaries),
        'maximum_row_boundary_is_exhaustive': False,
        'native_solver_executed': False, 'certified_counter_executed': False})


if __name__ == '__main__':
    main()
