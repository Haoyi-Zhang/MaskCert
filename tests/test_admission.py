from collections import Counter
from copy import deepcopy
from io import StringIO
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from casegen import base, mkrow
from update_cases import selected_cases
from pcs.admission import future_emissions, LocalConsumer
from pcs.model import Invalid
from pcs.producer import write_certificate
from pcs.update_checker import establish_anchor, advance_anchor
from pcs.update_producer import write_update


def full_text(spec, plan, prefix=None):
    out = StringIO()
    write_certificate(spec, plan, out, prefix)
    return out.getvalue()


def update_text(case):
    out = StringIO()
    write_update(case['old_declaration'], case['old_plan'],
                 case['declaration'], case['plan'], out)
    return out.getvalue()


def literal_history(spec):
    """Pointwise row semantics, independent of the consumer and mask helpers."""
    result = Counter()
    for row in spec['history']:
        for i in range(spec['n']):
            y = (spec['a'] * i + spec['b']) % spec['n']
            if (row['lo'] <= i < row['hi']
                and i % row['step'] == row['residue']
                and any(lo <= y < hi for lo, hi in row['guard'])):
                result[row['epoch'], y] += 1
    return result


def desired_items(spec):
    return Counter({(e, y): 1 for e, policy in enumerate(spec['epochs'])
                    for y in range(spec['n'])
                    if any(lo <= y < hi for lo, hi in policy['allow'])
                    and not any(lo <= y < hi for lo, hi in policy['exclude'])})


class AdmissionTests(unittest.TestCase):
    def test_future_emission_matches_declared_coverage(self):
        for case in selected_cases():
            spec, plan = case['old_declaration'], case['old_plan']
            anchor = establish_anchor(spec, plan, StringIO(full_text(spec, plan)))
            actual = literal_history(spec)
            for item in future_emissions(anchor):
                actual[item.epoch, item.target] += 1
                self.assertGreaterEqual(item.row, len(spec['history']))
            self.assertEqual(actual, desired_items(spec))

    def test_caller_mutation_does_not_change_admitted_items(self):
        spec, plan = base(32, 3, 1)
        anchor = establish_anchor(spec, plan, StringIO(full_text(spec, plan)))
        expected = list(future_emissions(anchor))
        spec['n'] = 1
        spec['epochs'][0]['allow'] = []
        plan['future'].clear()
        self.assertEqual(list(future_emissions(anchor)), expected)
        ss, pp = anchor.inputs()
        pp['future'].clear()
        ss['epochs'].clear()
        self.assertEqual(list(future_emissions(anchor)), expected)

    def test_unsafe_full_plan_does_not_admit(self):
        spec, plan = base(8, 3, 1)
        plan['future'] = []
        with self.assertRaises(Invalid):
            establish_anchor(spec, plan, StringIO(full_text(spec, plan)))

    def test_prefix_and_corrupt_transcript_do_not_admit(self):
        spec, plan = base(8, 3, 1)
        for text in (full_text(spec, plan, 0), full_text(spec, plan)[:-2]):
            with self.assertRaises(Invalid):
                establish_anchor(spec, plan, StringIO(text))

    def test_updates_either_admit_complete_future_or_leave_base(self):
        accepted = rejected = 0
        for case in selected_cases():
            old_spec, old_plan = case['old_declaration'], case['old_plan']
            spec, plan = case['declaration'], case['plan']
            anchor = establish_anchor(old_spec, old_plan,
                                      StringIO(full_text(old_spec, old_plan)))
            before = list(future_emissions(anchor))
            try:
                advanced = advance_anchor(anchor, spec, plan, StringIO(update_text(case)))
            except Invalid:
                rejected += 1
                self.assertEqual(list(future_emissions(anchor)), before)
            else:
                accepted += 1
                actual = literal_history(spec)
                for item in future_emissions(advanced):
                    actual[item.epoch, item.target] += 1
                self.assertEqual(actual, desired_items(spec))
        self.assertEqual((accepted, rejected), (40, 56))

    def test_raw_objects_are_not_admission_capabilities(self):
        spec, plan = base(8, 3, 1)
        for untrusted in (None, True, spec, plan, {'accepted': True}):
            with self.assertRaises(Invalid):
                list(future_emissions(untrusted))

    def test_each_iteration_is_explicit_replay_not_durable_once(self):
        spec, plan = base(8, 3, 1)
        anchor = establish_anchor(spec, plan, StringIO(full_text(spec, plan)))
        first = list(future_emissions(anchor))
        self.assertEqual(list(future_emissions(anchor)), first)
        expected_future = desired_items(spec) - literal_history(spec)
        self.assertEqual(Counter((item.epoch, item.target) for item in first), expected_future)

    def test_sequence_is_epoch_then_future_row_then_counter(self):
        spec = {'n': 4, 'a': 1, 'b': 0,
                'epochs': [{'allow': [[0, 4]], 'exclude': []} for _ in range(2)],
                'history': []}
        plan = {'context': {'n': 4, 'a': 1, 'b': 0}, 'future': [
            mkrow(1, 0, 2, 1, 0, [[0, 4]]),
            mkrow(0, 0, 4, 1, 0, [[0, 4]]),
            mkrow(1, 2, 4, 1, 0, [[0, 4]])]}
        anchor = establish_anchor(spec, plan, StringIO(full_text(spec, plan)))
        self.assertEqual([(v.epoch, v.row, v.counter) for v in future_emissions(anchor)],
                         [(0, 1, i) for i in range(4)]
                         + [(1, 0, i) for i in range(2)] + [(1, 2, i) for i in range(2, 4)])

    def test_rejected_replacement_holds_old_stream(self):
        case = selected_cases()[3]
        anchor = establish_anchor(case['old_declaration'], case['old_plan'],
                                  StringIO(full_text(case['old_declaration'], case['old_plan'])))
        consumer = LocalConsumer(anchor)
        with self.assertRaises(Invalid):
            consumer.request_update(case['declaration'], case['plan'], StringIO(update_text(case)))
        with self.assertRaises(Invalid):
            next(consumer)

    def test_safe_preconsumption_replacement_and_completion(self):
        case = selected_cases()[1]
        anchor = establish_anchor(case['old_declaration'], case['old_plan'],
                                  StringIO(full_text(case['old_declaration'], case['old_plan'])))
        consumer = LocalConsumer(anchor)
        consumer.request_update(case['declaration'], case['plan'], StringIO(update_text(case)))
        actual = literal_history(case['declaration'])
        for item in consumer:
            actual[item.epoch, item.target] += 1
        self.assertEqual(actual, desired_items(case['declaration']))
        self.assertEqual(list(consumer), [])

    def test_replacement_after_emission_holds_until_progress_is_reconciled(self):
        case = selected_cases()[1]
        anchor = establish_anchor(case['old_declaration'], case['old_plan'],
                                  StringIO(full_text(case['old_declaration'], case['old_plan'])))
        consumer = LocalConsumer(anchor)
        next(consumer)
        with self.assertRaises(Invalid):
            consumer.request_update(case['declaration'], case['plan'], StringIO(update_text(case)))
        with self.assertRaises(Invalid):
            next(consumer)


if __name__ == '__main__':
    unittest.main()
