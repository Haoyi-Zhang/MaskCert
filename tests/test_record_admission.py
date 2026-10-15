"""Owned local files only. PCS_RECORD_FIXTURE_PARENT selects private fixtures."""
from collections import Counter
from copy import deepcopy
from dataclasses import FrozenInstanceError
from io import StringIO
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from pcs.model import Invalid
from pcs.producer import write_certificate
from pcs.update_producer import write_update
from pcs import record_admission as records
from pcs.record_admission import RecordGate, RecordRead

METHODS = ('direct', 'full', 'incremental')


def row(lo, hi, guard, *, epoch=0, step=1, residue=0):
    return dict(epoch=epoch, lo=lo, hi=hi, step=step, residue=residue,
                guard=deepcopy(guard))


def job(n=16, *, a=5, b=1, history_end=0):
    spec = dict(n=n, a=a % n, b=b % n,
                epochs=[dict(allow=[[0, n]], exclude=[])], history=[])
    if history_end:
        spec['history'] = [row(0, history_end, [[0, n]])]
    plan = dict(context={k: spec[k] for k in ('n', 'a', 'b')},
                future=[row(history_end, n, [[0, n]])])
    return spec, plan


def evidence(method, spec, plan, old=None, *, prefix=None):
    if method == 'direct':
        return None
    out = StringIO()
    if method == 'incremental' and old is not None:
        write_update(*old, spec, plan, out, prefix)
    else:
        write_certificate(spec, plan, out, prefix)
    return out.getvalue()


def occurrences(spec):
    """Independent literal history, retaining (epoch,counter,target) multiplicity."""
    values = Counter()
    for rr in spec['history']:
        for counter in range(spec['n']):
            target = (spec['a'] * counter + spec['b']) % spec['n']
            if (rr['lo'] <= counter < rr['hi'] and counter % rr['step'] == rr['residue']
                    and any(lo <= target < hi for lo, hi in rr['guard'])):
                values[rr['epoch'], counter, target] += 1
    return values


def desired(spec):
    return Counter({(epoch, target): 1
                    for epoch, policy in enumerate(spec['epochs'])
                    for target in range(spec['n'])
                    if any(lo <= target < hi for lo, hi in policy['allow'])
                    and not any(lo <= target < hi for lo, hi in policy['exclude'])})


class RecordAdmissionTests(unittest.TestCase):
    def setUp(self):
        parent = os.environ.get('PCS_RECORD_FIXTURE_PARENT')
        self.temporary = tempfile.TemporaryDirectory(prefix='owned-record-gate-', dir=parent)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.serial = 0

    def make_gate(self, method, *, n=16, record_size=8):
        self.serial += 1
        path = self.directory / f'records-{self.serial}.bin'
        with path.open('xb') as stream:
            for target in range(n):
                stream.write(self.payload(target, record_size))
        gate = RecordGate(path, n=n, record_size=record_size, method=method)
        self.addCleanup(gate.close)
        return gate, path

    @staticmethod
    def payload(target, size=8):
        return bytes((target + 17 * j) % 256 for j in range(size))

    def assert_held(self, gate, reads=None):
        before = gate.total_reads if reads is None else reads
        self.assertEqual(gate.state, 'hold')
        with patch.object(records.os, 'read', side_effect=AssertionError('held gate read')):
            with self.assertRaises(Invalid):
                gate.consume(1)
        self.assertEqual(gate.total_reads, before)

    def assert_payloads(self, items, size=8):
        for item in items:
            self.assertIsInstance(item, RecordRead)
            self.assertIs(type(item.payload), bytes)
            self.assertEqual(item.payload, self.payload(item.target, size))

    def test_complete_workflow_same_decisions_and_actual_records_all_routes(self):
        outcomes = []
        for method in METHODS:
            with self.subTest(method=method):
                gate, _ = self.make_gate(method)
                spec, plan = job(history_end=2)
                decisions = [gate.admit(spec, plan, evidence(method, spec, plan))]
                first = gate.consume(2)
                self.assertEqual([v.counter for v in first], [2, 3])
                with self.assertRaises(Invalid):
                    gate.replace(spec, plan, None)
                self.assert_held(gate, 2)
                ss, pp = deepcopy(spec), deepcopy(plan)
                # Literal history can be repacked; row identity is not progress.
                ss['history'] = [row(0, 4, [[0, 16]])]
                pp['future'] = [row(4, 16, [[0, 16]])]
                decisions.append(gate.reconcile(ss, pp, evidence(method, ss, pp)))
                self.assertEqual(gate.pending_observed, ())
                split = deepcopy(pp)
                split['future'] = [row(4, 16, [[0, 16]], step=2, residue=r) for r in (0, 1)]
                decisions.append(gate.replace(ss, split, evidence(method, ss, split, (ss, pp))))
                revoked = deepcopy(ss)
                target = (ss['a'] * 5 + ss['b']) % ss['n']
                revoked['epochs'][0]['exclude'] = [[target, target + 1]]
                decisions.append(gate.replace(revoked, split,
                    evidence(method, revoked, split, (ss, split))))
                self.assert_held(gate, 2)
                repaired = deepcopy(split)
                guard = ([[0, target]] if target else []) + ([[target + 1, 16]] if target < 15 else [])
                for rr in repaired['future']:
                    rr['guard'] = deepcopy(guard)
                decisions.append(gate.replace(revoked, repaired,
                    evidence(method, revoked, repaired, (ss, split))))
                final = first + gate.consume()
                self.assert_payloads(final)
                seen = Counter((e, y) for (e, _, y), count in occurrences(spec).items()
                               for _ in range(count))
                seen.update((item.epoch, item.target) for item in final)
                self.assertEqual(seen, desired(revoked))
                self.assertEqual(gate.total_reads, len(final))
                self.assertEqual(gate.state, 'complete')
                self.assertEqual(gate.consume(), [])
                outcomes.append((decisions, final))
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(outcomes[1], outcomes[2])
        self.assertEqual(outcomes[0][0], [True, True, True, False, True])

    def test_initial_unsafe_returns_false_and_safe_retry_is_possible(self):
        for method in METHODS:
            gate, _ = self.make_gate(method)
            spec, plan = job()
            unsafe = deepcopy(plan)
            unsafe['future'].clear()
            self.assertFalse(gate.admit(spec, unsafe, evidence(method, spec, unsafe)))
            self.assert_held(gate, 0)
            self.assertTrue(gate.admit(spec, plan, evidence(method, spec, plan)))
            self.assertEqual(len(gate.consume()), 16)

    def test_rejected_update_retains_safe_anchor_but_not_continuation(self):
        for method in METHODS:
            gate, _ = self.make_gate(method)
            spec, plan = job()
            self.assertTrue(gate.admit(spec, plan, evidence(method, spec, plan)))
            duplicate = deepcopy(plan)
            duplicate['future'].append(deepcopy(duplicate['future'][0]))
            self.assertFalse(gate.replace(spec, duplicate, evidence(method, spec, duplicate, (spec, plan))))
            self.assert_held(gate, 0)
            repaired = deepcopy(plan)
            repaired['future'] = [row(0, 8, [[0, 16]]), row(8, 16, [[0, 16]])]
            # Evidence is based on the last SAFE plan, not the rejected duplicate.
            self.assertTrue(gate.replace(spec, repaired, evidence(method, spec, repaired, (spec, plan))))
            self.assertEqual(len(gate.consume()), 16)

    def test_failed_reconciliations_keep_checkpoint_and_all_observations(self):
        for method in METHODS:
            gate, _ = self.make_gate(method)
            spec, plan = job(history_end=1)
            gate.admit(spec, plan, evidence(method, spec, plan))
            first = gate.consume(3)
            observed = tuple((v.epoch, v.counter, v.target) for v in first)
            ss, pp = deepcopy(spec), deepcopy(plan)
            ss['history'] = [row(0, 4, [[0, 16]])]
            pp['future'] = [row(4, 16, [[0, 16]])]
            missing = deepcopy(ss)
            missing['history'][0]['hi'] = 3
            duplicate = deepcopy(ss)
            duplicate['history'].append(row(1, 2, [[0, 16]]))
            wrong = deepcopy(ss)
            wrong['history'] = [row(0, 3, [[0, 16]]), row(5, 6, [[0, 16]])]
            for bad in (missing, duplicate, wrong):
                with self.assertRaises(Invalid):
                    gate.reconcile(bad, pp, evidence(method, bad, pp))
                self.assert_held(gate, 3)
                self.assertEqual(gate.pending_observed, observed)
            unsafe = deepcopy(pp)
            unsafe['future'][0]['hi'] = 15
            self.assertFalse(gate.reconcile(ss, unsafe, evidence(method, ss, unsafe)))
            self.assert_held(gate, 3)
            self.assertEqual(gate.pending_observed, observed)
            if method != 'direct':
                with self.assertRaises(Invalid):
                    gate.reconcile(ss, pp, evidence(method, ss, pp)[:-2])
                self.assert_held(gate, 3)
                self.assertEqual(gate.pending_observed, observed)
            with self.assertRaises(Invalid):
                gate.replace(spec, plan, None)
            self.assertTrue(gate.reconcile(ss, pp, evidence(method, ss, pp)))
            self.assertEqual(gate.pending_observed, ())
            last = gate.consume()
            self.assertEqual([x.counter for x in first + last], list(range(1, 16)))
            self.assertEqual(gate.total_reads, 15)

    def test_reconcile_policy_change_checks_old_history_under_new_policy(self):
        for method in METHODS:
            gate, _ = self.make_gate(method)
            spec, plan = job()
            gate.admit(spec, plan, evidence(method, spec, plan))
            first = gate.consume(2)
            ss, pp = deepcopy(spec), deepcopy(plan)
            ss['history'] = [row(0, 2, [[0, 16]])]
            pp['future'] = [row(2, 16, [[0, 16]])]
            forbidden = deepcopy(ss)
            target = first[0].target
            forbidden['epochs'][0]['exclude'] = [[target, target + 1]]
            self.assertFalse(gate.reconcile(forbidden, pp, evidence(method, forbidden, pp)))
            self.assert_held(gate, 2)
            self.assertEqual(len(gate.pending_observed), 2)
            changed = deepcopy(ss)
            future_target = (spec['a'] * 3 + spec['b']) % 16
            changed['epochs'][0]['exclude'] = [[future_target, future_target + 1]]
            guard = ([[0, future_target]] if future_target else []) + (
                [[future_target + 1, 16]] if future_target < 15 else [])
            repaired = deepcopy(pp)
            repaired['future'][0]['guard'] = guard
            self.assertTrue(gate.reconcile(changed, repaired, evidence(method, changed, repaired)))
            self.assertEqual(Counter((x.epoch, x.target) for x in first + gate.consume()), desired(changed))

    def test_successive_reconcile_and_completed_stream_never_forget_history(self):
        for method in METHODS:
            gate, _ = self.make_gate(method)
            spec, plan = job()
            gate.admit(spec, plan, evidence(method, spec, plan))
            all_items = []
            for end in (2, 5, 16):
                all_items += gate.consume(end - len(all_items))
                new_spec, new_plan = deepcopy(spec), deepcopy(plan)
                new_spec['history'] = [row(0, end, [[0, 16]])]
                new_plan['future'] = [row(end, 16, [[0, 16]])]
                with self.assertRaises(Invalid):
                    gate.replace(new_spec, new_plan, None)
                self.assertTrue(gate.reconcile(new_spec, new_plan, evidence(method, new_spec, new_plan)))
                spec, plan = new_spec, new_plan
            self.assertEqual(gate.total_reads, 16)
            self.assertEqual(len(all_items), 16)
            self.assertEqual(gate.state, 'complete')
            self.assertEqual(gate.pending_observed, ())
            reset, restart = job()
            with self.assertRaises(Invalid):
                gate.reconcile(reset, restart, evidence(method, reset, restart))
            self.assert_held(gate, 16)

    def test_dictionary_mutation_cannot_change_accepted_inputs_or_observed_log(self):
        expected = None
        for method in METHODS:
            gate, _ = self.make_gate(method)
            spec, plan = job()
            gate.admit(spec, plan, evidence(method, spec, plan))
            spec['epochs'][0]['allow'].clear()
            spec['history'].append(row(0, 16, [[0, 16]]))
            spec['n'] = True
            plan['context']['n'] = True
            plan['future'][0]['guard'].clear()
            plan['future'].clear()
            first = gate.consume(1)
            snapshot = gate.pending_observed
            with self.assertRaises(TypeError):
                snapshot[0] = (0, 0, 0)
            with self.assertRaises(FrozenInstanceError):
                first[0].target = 99
            actual = first + gate.consume()
            self.assert_payloads(actual)
            if expected is None:
                expected = actual
            self.assertEqual(actual, expected)
            self.assertEqual(len(actual), 16)

    def test_mutation_while_certificate_is_read_cannot_change_private_snapshot(self):
        for method in ('full', 'incremental'):
            gate, _ = self.make_gate(method)
            spec, plan = job()
            text = evidence(method, spec, plan)

            def mutate_while_reading():
                spec['epochs'].clear()
                plan['future'].clear()
                yield from text.splitlines(keepends=True)

            self.assertTrue(gate.admit(spec, plan, mutate_while_reading()))
            actual = gate.consume()
            self.assertEqual([v.counter for v in actual], list(range(16)))
            self.assert_payloads(actual)

    def test_epoch_then_row_then_counter_with_history_offset_and_reuse(self):
        sequences = []
        for method in METHODS:
            gate, _ = self.make_gate(method, n=4)
            spec = dict(n=4, a=1, b=0,
                        epochs=[dict(allow=[[0, 4]], exclude=[]) for _ in range(2)],
                        history=[row(0, 1, [[0, 4]])])
            plan = dict(context=dict(n=4, a=1, b=0), future=[
                row(0, 4, [[0, 4]], epoch=1, step=2, residue=1),
                row(1, 4, [[0, 4]], step=2, residue=1),
                row(1, 4, [[0, 4]], step=2, residue=0),
                row(0, 4, [[0, 4]], epoch=1, step=2, residue=0)])
            self.assertTrue(gate.admit(spec, plan, evidence(method, spec, plan)))
            actual = gate.consume()
            sequences.append([(x.epoch, x.row, x.counter) for x in actual])
            self.assert_payloads(actual)
            self.assertEqual(gate.total_reads, 7)
        self.assertEqual(sequences, [[(0, 2, 1), (0, 2, 3), (0, 3, 2),
                                     (1, 1, 1), (1, 1, 3), (1, 4, 0), (1, 4, 2)]] * 3)

    def test_initial_schema_n_binding_and_strict_boolean_rejection(self):
        for method in METHODS:
            for kind in ('n', 'bool-n', 'bool-context', 'tuple-guard', 'extra-field'):
                gate, _ = self.make_gate(method)
                spec, plan = job()
                if kind == 'n':
                    spec, plan = job(8)
                elif kind == 'bool-n':
                    spec['n'] = True
                elif kind == 'bool-context':
                    plan['context']['n'] = True
                elif kind == 'tuple-guard':
                    plan['future'][0]['guard'] = ((0, 16),)
                else:
                    spec['extra'] = 1
                with self.subTest(method=method, kind=kind), self.assertRaises(Invalid):
                    gate.admit(spec, plan)
                self.assert_held(gate, 0)

    def test_replacement_and_reconcile_bind_fixed_context_and_epoch_count(self):
        for method in METHODS:
            gate, _ = self.make_gate(method)
            spec, plan = job(history_end=1)
            gate.admit(spec, plan, evidence(method, spec, plan))
            for operation in (gate.replace, gate.reconcile):
                for kind in ('n', 'a', 'b', 'epochs'):
                    ss, pp = deepcopy(spec), deepcopy(plan)
                    if kind == 'n':
                        ss, pp = job(8, history_end=1)
                    elif kind in ('a', 'b'):
                        ss[kind] = 3
                        pp['context'][kind] = 3
                    else:
                        ss['epochs'].append(deepcopy(ss['epochs'][0]))
                    with self.assertRaises(Invalid):
                        operation(ss, pp)
                    self.assert_held(gate, 0)
            altered = deepcopy(spec)
            altered['history'] = [row(0, 1, [[1, 2]])]  # same occurrence, different row.
            with self.assertRaises(Invalid):
                gate.replace(altered, plan)
            self.assertTrue(gate.reconcile(altered, plan, evidence(method, altered, plan)))

    def test_certificate_corruption_prefix_trailing_and_types_are_invalid(self):
        spec, plan = job()
        spec['epochs'][0]['allow'] = [[0, 3], [5, 16]]
        plan['future'][0]['guard'] = [[0, 3], [5, 16]]
        text = evidence('full', spec, plan)
        lines = text.splitlines(keepends=True)
        floor = json.loads(lines[1])
        floor[0] += 1
        corrupt_floor = ''.join([lines[0], json.dumps(floor) + '\n', *lines[2:]])
        for method in ('full', 'incremental'):
            invalids = (None, True, b'certificate', ['not json\n'], [True], text[:-2],
                        text + '{}\n', corrupt_floor,
                        evidence(method, spec, plan, prefix=0),
                        text.replace('"accepted":true', '"accepted":false'))
            for proof in invalids:
                gate, _ = self.make_gate(method)
                with self.assertRaises(Invalid):
                    gate.admit(spec, plan, proof)
                self.assert_held(gate, 0)
            gate, _ = self.make_gate(method)
            self.assertTrue(gate.admit(spec, plan, StringIO(text)))
            broken = evidence(method, spec, plan, (spec, plan))[:-2]
            with self.assertRaises(Invalid):
                gate.replace(spec, plan, broken)
            self.assert_held(gate, 0)
            self.assertTrue(gate.replace(spec, plan, evidence(method, spec, plan, (spec, plan))))

    def test_certificate_iterator_cannot_spoof_semantic_unsafe_exit(self):
        for method in ('full', 'incremental'):
            gate, _ = self.make_gate(method)
            spec, plan = job()

            def broken():
                yield '{"prefix":16}\n'
                raise Invalid('unsafe base cannot establish a safe anchor')

            with self.assertRaises(Invalid):
                gate.admit(spec, plan, broken())
            self.assert_held(gate, 0)

    def test_direct_ignores_evidence_and_cert_routes_do_not_use_direct_defects(self):
        for method in METHODS:
            gate, _ = self.make_gate(method)
            spec, plan = job()
            initial = object() if method == 'direct' else evidence(method, spec, plan)
            pp = deepcopy(plan)
            pp['future'] = [row(0, 8, [[0, 16]]), row(8, 16, [[0, 16]])]
            update = evidence(method, spec, pp, (spec, plan))
            rebase = evidence(method, spec, pp)
            with patch.object(records, 'defects', wraps=records.defects) as direct, \
                 patch.object(records, 'establish_anchor', wraps=records.establish_anchor) as full, \
                 patch.object(records, 'advance_anchor', wraps=records.advance_anchor) as advance:
                self.assertTrue(gate.admit(spec, plan, initial))
                self.assertTrue(gate.replace(spec, pp, update))
                self.assertTrue(gate.reconcile(spec, pp, rebase))
                expected = {'direct': (3, 0, 0), 'full': (0, 3, 0), 'incremental': (0, 2, 1)}[method]
                self.assertEqual((direct.call_count, full.call_count, advance.call_count), expected)
            self.assertEqual(gate.total_reads, 0)

    def test_read_failure_preserves_prior_successes_and_holds(self):
        for method in METHODS:
            gate, _ = self.make_gate(method)
            spec, plan = job()
            gate.admit(spec, plan, evidence(method, spec, plan))
            raw_read = records.os.read
            calls = 0

            def fail_second(fd, size):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError('owned test read fault')
                return raw_read(fd, size)

            with patch.object(records.os, 'read', side_effect=fail_second):
                with self.assertRaises(Invalid):
                    gate.consume(3)
            self.assert_held(gate, 2)
            self.assertEqual(gate.pending_observed, ((0, 0, 1),))
            with self.assertRaises(Invalid):
                gate.replace(spec, plan)
            ss, pp = deepcopy(spec), deepcopy(plan)
            ss['history'] = [row(0, 1, [[0, 16]])]
            pp['future'] = [row(1, 16, [[0, 16]])]
            self.assertTrue(gate.reconcile(ss, pp, evidence(method, ss, pp)))
            self.assertEqual(len(gate.consume()), 15)
            self.assertEqual(gate.total_reads, 17)  # 16 complete records, one failed call.

    def test_short_read_holds_and_no_complete_observation_is_invented(self):
        for method in METHODS:
            gate, _ = self.make_gate(method)
            spec, plan = job()
            gate.admit(spec, plan, evidence(method, spec, plan))
            with patch.object(records.os, 'read', return_value=b'x'):
                with self.assertRaisesRegex(Invalid, 'short'):
                    gate.consume(1)
            self.assert_held(gate, 1)
            self.assertEqual(gate.pending_observed, ())
            with self.assertRaises(Invalid):
                gate.replace(spec, plan)
            self.assertTrue(gate.reconcile(spec, plan, evidence(method, spec, plan)))
            self.assertEqual(len(gate.consume()), 16)

    def test_file_shape_locality_and_constructor_bounds(self):
        path = self.directory / 'input.bin'
        path.write_bytes(b'x' * 16)
        for n in (True, False, 0, -1, (1 << 20) + 1, 16.0):
            with self.assertRaises(Invalid):
                RecordGate(path, n=n, record_size=1, method='direct')
        for size in (True, 0, -1, 1.0):
            with self.assertRaises(Invalid):
                RecordGate(path, n=16, record_size=size, method='direct')
        for method in (None, True, 'Direct', 'full ', 'update', [], 1):
            with self.assertRaises(Invalid):
                RecordGate(path, n=16, record_size=1, method=method)
        for size in (15, 17):
            path.write_bytes(b'x' * size)
            with self.assertRaisesRegex(Invalid, 'length'):
                RecordGate(path, n=16, record_size=1, method='direct')
        for bad_path in (self.directory, self.directory / 'absent', '//host/share',
                         '\\\\host\\share', 'https://example.invalid/input', None, b'input.bin'):
            with self.assertRaises(Invalid):
                RecordGate(bad_path, n=16, record_size=1, method='direct')

    def test_file_change_and_wrong_owner_fence_before_payload_read(self):
        for method in METHODS:
            for change in ('length', 'same-size-content'):
                gate, path = self.make_gate(method)
                spec, plan = job()
                gate.admit(spec, plan, evidence(method, spec, plan))
                if change == 'length':
                    with path.open('ab') as stream:
                        stream.write(b'x')
                else:
                    old = path.stat()
                    with path.open('r+b') as stream:
                        stream.write(b'changed!')
                    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns + 1_000_000))
                with patch.object(records.os, 'read', side_effect=AssertionError('changed file read')):
                    with self.assertRaises(Invalid):
                        gate.consume(1)
                self.assert_held(gate, 0)
        gate, path = self.make_gate('direct')
        if os.name == 'nt':
            with patch.object(records, '_windows_owner', side_effect=Invalid('wrong owner')):
                with self.assertRaises(Invalid):
                    RecordGate(path, n=16, record_size=8, method='direct')
        elif hasattr(os, 'geteuid'):
            with patch.object(records.os, 'geteuid', return_value=path.stat().st_uid + 1):
                with self.assertRaises(Invalid):
                    RecordGate(path, n=16, record_size=8, method='direct')

    def test_opening_binds_identity_not_cross_api_ctime_meaning(self):
        gate, path = self.make_gate('direct')
        info = path.stat(follow_symlinks=False)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode')
        path_info = SimpleNamespace(**{field: getattr(info, field) for field in fields})
        path_info.st_ctime_ns += 100
        with patch.object(records.os, 'stat', return_value=path_info):
            with RecordGate(path, n=16, record_size=8, method='direct') as reopened:
                spec, plan = job()
                self.assertTrue(reopened.admit(spec, plan))
                self.assertEqual(len(reopened.consume()), 16)

    def test_symlink_input_is_not_a_regular_owned_input(self):
        gate, path = self.make_gate('direct')
        link = self.directory / 'link.bin'
        try:
            link.symlink_to(path)
        except OSError as error:
            self.skipTest(f'owned symlink fixture unavailable: {error}')
        with self.assertRaises(Invalid):
            RecordGate(link, n=16, record_size=8, method='direct')

    def test_zero_limit_is_not_progress_and_invalid_limits_hold(self):
        for method in METHODS:
            gate, _ = self.make_gate(method)
            spec, plan = job()
            gate.admit(spec, plan, evidence(method, spec, plan))
            self.assertEqual(gate.consume(0), [])
            self.assertEqual(gate.state, 'ready')
            self.assertTrue(gate.replace(spec, plan, evidence(method, spec, plan, (spec, plan))))
            for limit in (True, False, -1, 1.0, '1'):
                with self.assertRaises(Invalid):
                    gate.consume(limit)
                self.assert_held(gate, 0)
                self.assertTrue(gate.replace(spec, plan, evidence(method, spec, plan, (spec, plan))))

    def test_initial_hold_readmit_bypass_and_safe_context_close(self):
        for method in METHODS:
            gate, _ = self.make_gate(method)
            self.assert_held(gate, 0)
            spec, plan = job()
            for operation in (gate.replace, gate.reconcile):
                with self.assertRaises(Invalid):
                    operation(spec, plan)
            self.assertTrue(gate.admit(spec, plan, evidence(method, spec, plan)))
            gate.consume(1)
            with self.assertRaises(Invalid):
                gate.admit(spec, plan, evidence(method, spec, plan))
            self.assert_held(gate, 1)
            fd = gate._fd
            with self.assertRaisesRegex(RuntimeError, 'body fault'):
                with gate:
                    raise RuntimeError('body fault')
            self.assertTrue(gate.closed)
            with self.assertRaises(OSError):
                os.fstat(fd)
            gate.close()
            self.assert_held(gate, 1)
            with self.assertRaises(Invalid):
                gate.__enter__()
            with self.assertRaises(Invalid):
                gate.reconcile(spec, plan, evidence(method, spec, plan))

    def test_empty_future_and_singleton(self):
        for method in METHODS:
            gate, _ = self.make_gate(method, n=1)
            spec, plan = job(1)
            self.assertTrue(gate.admit(spec, plan, evidence(method, spec, plan)))
            self.assertEqual([v.target for v in gate.consume()], [0])
            self.assertEqual(gate.state, 'complete')
            empty, empty_plan = deepcopy(spec), deepcopy(plan)
            empty['history'] = [row(0, 1, [[0, 1]])]
            empty_plan['future'] = []
            self.assertTrue(gate.reconcile(empty, empty_plan, evidence(method, empty, empty_plan)))
            self.assertEqual(gate.state, 'complete')
            self.assertEqual(gate.consume(), [])
            self.assertEqual(gate.total_reads, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
