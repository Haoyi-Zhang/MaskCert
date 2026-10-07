"""Portable finite mask/defect references. No files, providers or network."""
from copy import deepcopy
from io import StringIO
from math import gcd
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pcs import checker
from pcs.model import Invalid
from pcs.producer import write_certificate
from pcs.update_producer import write_update, locate_update
from pcs.update_checker import (establish_anchor, verify_update, advance_anchor,
                                check_update_witness)


def runs(bits):
    spans = []
    for point, yes in enumerate(bits):
        if yes:
            if spans and spans[-1][1] == point:
                spans[-1][1] += 1
            else:
                spans.append([point, point + 1])
    return spans


def mask_reference(left, right, n):
    # The generic sweep tests exactly one active span in each input, too.
    return runs([sum(lo <= x < hi for lo, hi in left) == 1 and
                 sum(lo <= x < hi for lo, hi in right) == 1 for x in range(n)])


def definition(spec, plan, prefix=None):
    totals, witness = [], None
    for epoch, policy in enumerate(spec["epochs"]):
        total = 0
        for counter in range(spec["n"] if prefix is None else prefix):
            target = (spec["a"] * counter + spec["b"]) % spec["n"]
            wanted = (any(lo <= target < hi for lo, hi in policy["allow"]) and
                      not any(lo <= target < hi for lo, hi in policy["exclude"]))
            hits = [j for j, row in enumerate(spec["history"] + plan["future"])
                    if row["epoch"] == epoch and row["lo"] <= counter < row["hi"]
                    and counter % row["step"] == row["residue"]
                    and any(lo <= target < hi for lo, hi in row["guard"])]
            local = (len(hits) - 1) ** 2 if wanted else len(hits)
            total += local
            if local and witness is None:
                kind = "forbidden" if not wanted else ("omission" if not hits else "collision")
                witness = dict(epoch=epoch, counter=counter, target=target, kind=kind,
                               rows=hits[:2] if kind == "collision" else hits[:1])
        totals.append(total)
    return totals, witness


def owned_cases():
    for seed in range(32):
        rng = random.Random(100801000 + seed)
        n = (1, 2, 5, 9, 17)[seed % 5]
        spec = dict(n=n, a=rng.choice([a for a in range(n) if gcd(a, n) == 1]),
                    b=rng.randrange(n), epochs=[], history=[])
        future = []
        for epoch in range(1 + seed % 3):
            allow = [rng.randrange(4) != 0 for _ in range(n)]
            exclude = [rng.randrange(5) == 0 for _ in range(n)]
            guard = runs([a and not x for a, x in zip(allow, exclude)])
            spec["epochs"].append(dict(allow=runs(allow), exclude=runs(exclude)))
            cut = n // 2
            spec["history"].append(dict(epoch=epoch, lo=0, hi=cut, step=1,
                                        residue=0, guard=deepcopy(guard)))
            future += [dict(epoch=epoch, lo=cut, hi=n, step=2, residue=r,
                            guard=deepcopy(guard)) for r in (0, 1)]
        future += [dict(epoch=0, lo=0, hi=0, step=1, residue=0, guard=[])] * 2
        plan = dict(context={k: spec[k] for k in ("n", "a", "b")}, future=deepcopy(future))
        new_spec, new_plan = deepcopy(spec), deepcopy(plan)
        mode = seed % 6
        if mode == 0:
            rng.shuffle(new_plan["future"])
        elif mode == 1:
            new_plan["future"].pop(0)
        elif mode == 2:
            new_plan["future"].append(deepcopy(new_plan["future"][0]))
        elif mode == 3:
            new_spec["epochs"][0] = dict(allow=runs([rng.choice((True, False)) for _ in range(n)]),
                                          exclude=runs([rng.choice((True, False)) for _ in range(n)]))
        elif mode == 4:
            new_plan["future"][0]["guard"] = runs([rng.choice((True, False)) for _ in range(n)])
        else:
            new_plan["future"].reverse()
            new_plan["future"] += deepcopy(new_plan["future"][:2])
        yield spec, plan, new_spec, new_plan


def full_text(spec, plan, prefix=None):
    out = StringIO()
    write_certificate(spec, plan, out, prefix)
    return out.getvalue()


def update_text(old_spec, old_plan, spec, plan, prefix=None):
    out = StringIO()
    write_update(old_spec, old_plan, spec, plan, out, prefix)
    return out.getvalue()


class MaskSweepTests(unittest.TestCase):
    def test_cartesian_masks_against_membership_not_sweep_copy(self):
        masks = [runs([bool(bits & (1 << point)) for point in range(6)]) for bits in range(64)]
        for left in masks:
            for right in masks:
                before = deepcopy((left, right))
                self.assertEqual(checker.meet(left, right), mask_reference(left, right, 6))
                self.assertEqual((left, right), before)

    def test_half_open_ties_generic_fallback_and_fresh_results(self):
        cases = (([[0, 2], [2, 4]], [[1, 3]]),
                 ([[4, 6], [0, 2]], [[1, 5]]),
                 ([[0, 4], [2, 6]], [[0, 6]]),
                 ([[2, 2]], [[0, 6]]),
                 ([], [[0, 6]]), ([[0, 6]], []))
        for left, right in cases:
            expected = mask_reference(left, right, 6)
            self.assertEqual(checker.meet(left, right), expected)
            self.assertEqual(checker.meet(tuple(map(tuple, left)), tuple(map(tuple, right))), expected)
            self.assertEqual(checker.meet(iter(left), iter(right)), expected)
        left, right = [[0, 3]], [[0, 3]]
        result = checker.meet(left, right)
        result[0][1] = 1
        self.assertEqual((left, right), ([[0, 3]], [[0, 3]]))

    def test_1024_masks_at_large_endpoints_without_domain_enumeration(self):
        start = (1 << 32) - 8192
        left = [[start + 8*j, start + 8*j + 4] for j in range(1024)]
        right = [[start + 8*j + 2, start + 8*j + 6] for j in range(1024)]
        expected = [[start + 8*j + 2, start + 8*j + 4] for j in range(1024)]
        self.assertEqual(checker.meet(left, right), expected)
        self.assertEqual(checker.meet(left, []), [])
        self.assertEqual(checker.meet([[0, 1 << 32]], left), left)

    def test_full_and_update_all_owned_prefixes_and_masks(self):
        for old_spec, old_plan, spec, plan in owned_cases():
            inputs = deepcopy((old_spec, old_plan, spec, plan))
            anchor = establish_anchor(old_spec, old_plan, StringIO(full_text(old_spec, old_plan)))
            for prefix in range(spec["n"] + 1):
                expected = definition(spec, plan, prefix)[0]
                full = checker.verify(spec, plan, StringIO(full_text(spec, plan, prefix)), prefix)
                update = verify_update(anchor, spec, plan,
                                       StringIO(update_text(old_spec, old_plan, spec, plan, prefix)), prefix)
                self.assertEqual(full.defects, tuple(expected))
                self.assertEqual(update.defects, full.defects)
                self.assertEqual((full.accepted, update.accepted), (not any(expected), not any(expected)))
            self.assertEqual((old_spec, old_plan, spec, plan), inputs)

    def test_complete_stream_corruption_caps_and_anchor_premises(self):
        old_spec, old_plan, spec, plan = list(owned_cases())[4]
        anchor = establish_anchor(old_spec, old_plan, StringIO(full_text(old_spec, old_plan)))
        for text, verify in (
            (full_text(spec, plan), lambda lines: checker.verify(spec, plan, lines)),
            (update_text(old_spec, old_plan, spec, plan), lambda lines: verify_update(anchor, spec, plan, lines)),
        ):
            records = text.splitlines(keepends=True)
            for broken in ("".join(records[:-1]), text + "{}\n", "{}\n" + "".join(records[1:]),
                           records[0] + "[0,[[0,0,0]]]\n" + "".join(records[1:])):
                with self.assertRaises(Invalid):
                    verify(StringIO(broken))
            with patch.object(checker, "MAX_CERTIFICATE_BYTES", 1):
                with self.assertRaises(Invalid):
                    verify(StringIO(text))
            with patch.object(checker, "MAX_CERTIFICATE_LINE_BYTES", 1):
                with self.assertRaises(Invalid):
                    verify(StringIO(text))
        with self.assertRaises(Invalid):
            establish_anchor(old_spec, old_plan, StringIO(full_text(old_spec, old_plan, 0)))
        bad_spec = deepcopy(spec)
        bad_spec["history"].clear()
        with self.assertRaises(Invalid):
            verify_update(anchor, bad_spec, plan, StringIO(update_text(old_spec, old_plan, spec, plan)))
        bad_spec = deepcopy(spec)
        bad_spec["n"] = True
        with self.assertRaises(Invalid):
            verify_update(anchor, bad_spec, plan, StringIO(update_text(old_spec, old_plan, spec, plan)))

    def test_witness_order_snapshot_and_safe_advancement(self):
        for old_spec, old_plan, spec, plan in owned_cases():
            anchor = establish_anchor(old_spec, old_plan, StringIO(full_text(old_spec, old_plan)))
            expected = definition(spec, plan)[1]
            witness = locate_update(old_spec, old_plan, spec, plan)
            self.assertEqual(witness, expected)
            text = update_text(old_spec, old_plan, spec, plan)
            if witness is None:
                advanced = advance_anchor(anchor, spec, plan, StringIO(text))
                self.assertEqual(advanced.inputs(), (spec, plan))
            else:
                certs = [update_text(old_spec, old_plan, spec, plan, prefix)
                         for prefix in (None, witness["counter"], witness["counter"] + 1)]
                self.assertTrue(check_update_witness(anchor, spec, plan, witness,
                                *(StringIO(t) for t in certs)))
                with self.assertRaises(Invalid):
                    advance_anchor(anchor, spec, plan, StringIO(text))
                with self.assertRaises(Invalid):
                    check_update_witness(anchor, spec, plan, witness,
                                         StringIO(certs[0]), StringIO(certs[2]), StringIO(certs[1]))
            saved = deepcopy((old_spec, old_plan))
            old_plan["future"].clear()
            self.assertEqual(anchor.inputs(), saved)


if __name__ == "__main__":
    unittest.main(verbosity=2)

