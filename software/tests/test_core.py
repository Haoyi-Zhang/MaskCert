from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
SOFTWARE = HERE.parents[1]
PROJECT = HERE.parents[2]
sys.path.insert(0, str(SOFTWARE))

from pcs.core import (  # noqa: E402
    PCSValidationError, analyze, canonical_json_bytes, canonical_sha256,
    canonical_witness, certificate_rows, check_certificate, check_witness,
    count_progression_target_interval, explicit_defect, explicit_multiplicities,
    floor_sum, fragment_contains_source, intersect_progressions,
    intervals_from_points, load_inputs, loads_strict, progression_first_count,
    progression_size, residue_lt_count, source_for_target, target_is_authorized,
    validate_declaration, validate_plan, write_certificate, write_witness,
)


def declaration_obj(n=32, a=5, b=3, authorized=None):
    if authorized is None:
        authorized = [[0, n]]
    return {
        "schema": "pcs-declaration-v2",
        "universe": n,
        "permutation": {"kind": "affine", "multiplier": a, "offset": b},
        "authorized": authorized,
    }


def fragment(fid, lo, hi, stride=1, residue=0, phase="planned"):
    return {"id": fid, "phase": phase, "lo": lo, "hi": hi,
            "stride": stride, "residue": residue}


def plan_obj(fragments):
    return {"schema": "pcs-plan-v2", "fragments": fragments}


def make_validated(dobj, pobj):
    d = validate_declaration(dobj)
    p = validate_plan(pobj, d)
    return d, p


def safe_case(n=64):
    a, b = 5, 7
    fragments = [
        fragment("f000", 0, n, 4, 0, "committed"),
        fragment("f001", 0, n, 4, 2, "planned"),
    ]
    points = []
    for f in fragments:
        for x in range(f["lo"], f["hi"]):
            if x % f["stride"] == f["residue"]:
                points.append((a * x + b) % n)
    return make_validated(declaration_obj(n, a, b, intervals_from_points(points, n)), plan_obj(fragments))


class StrictSchemaTests(unittest.TestCase):
    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(PCSValidationError):
            loads_strict('{"x":1,"x":2}')

    def test_bool_not_integer(self):
        obj = declaration_obj()
        obj["universe"] = True
        with self.assertRaises(PCSValidationError):
            validate_declaration(obj)

    def test_unknown_declaration_key(self):
        obj = declaration_obj()
        obj["extra"] = 1
        with self.assertRaises(PCSValidationError):
            validate_declaration(obj)

    def test_bad_schema(self):
        obj = declaration_obj()
        obj["schema"] = "pcs-declaration-v1"
        with self.assertRaises(PCSValidationError):
            validate_declaration(obj)

    def test_non_coprime_affine_multiplier(self):
        with self.assertRaises(PCSValidationError):
            validate_declaration(declaration_obj(32, 4, 0))

    def test_overlapping_intervals(self):
        with self.assertRaises(PCSValidationError):
            validate_declaration(declaration_obj(32, authorized=[[0, 5], [4, 8]]))

    def test_adjacent_intervals_rejected_as_noncanonical(self):
        with self.assertRaises(PCSValidationError):
            validate_declaration(declaration_obj(32, authorized=[[0, 5], [5, 8]]))

    def test_empty_authorized_mask_allowed(self):
        d = validate_declaration(declaration_obj(32, authorized=[]))
        self.assertEqual(d.authorized_size, 0)

    def test_duplicate_fragment_id(self):
        d = validate_declaration(declaration_obj())
        with self.assertRaises(PCSValidationError):
            validate_plan(plan_obj([fragment("f", 0, 2), fragment("f", 2, 4)]), d)

    def test_unsorted_fragment_id(self):
        d = validate_declaration(declaration_obj())
        with self.assertRaises(PCSValidationError):
            validate_plan(plan_obj([fragment("z", 0, 2), fragment("a", 2, 4)]), d)

    def test_empty_fragment_rejected(self):
        d = validate_declaration(declaration_obj())
        with self.assertRaises(PCSValidationError):
            validate_plan(plan_obj([fragment("f", 0, 1, 2, 1)]), d)

    def test_bad_phase(self):
        d = validate_declaration(declaration_obj())
        with self.assertRaises(PCSValidationError):
            validate_plan(plan_obj([fragment("f", 0, 2, phase="done")]), d)


class ArithmeticTests(unittest.TestCase):
    def test_progression_first_count_exhaustive(self):
        for lo in range(8):
            for hi in range(lo + 1, 10):
                for m in range(1, 8):
                    for r in range(m):
                        first, count = progression_first_count(lo, hi, m, r)
                        values = [x for x in range(lo, hi) if x % m == r]
                        self.assertEqual(count, len(values))
                        if values:
                            self.assertEqual(first, values[0])

    def test_floor_sum_signed_exhaustive(self):
        for n in range(12):
            for m in range(1, 10):
                for a in range(-12, 13):
                    for b in range(-12, 13):
                        want = sum((a * i + b) // m for i in range(n))
                        self.assertEqual(floor_sum(n, m, a, b), want)

    def test_residue_threshold_random_5000(self):
        rng = random.Random(0xC0FFEE)
        for _ in range(5000):
            n = rng.randrange(0, 80)
            m = rng.randrange(1, 80)
            a = rng.randrange(-300, 301)
            b = rng.randrange(-300, 301)
            t = rng.randrange(0, m + 1)
            want = sum(1 for i in range(n) if (a * i + b) % m < t)
            self.assertEqual(residue_lt_count(n, m, a, b, t), want)

    def test_modular_interval_random_5000(self):
        rng = random.Random(0xA11F1E)
        for idx in range(5000):
            n = rng.randrange(2, 100)
            candidates = [a for a in range(1, n) if __import__("math").gcd(a, n) == 1]
            a = rng.choice(candidates)
            b = rng.randrange(n)
            lo = rng.randrange(n)
            hi = rng.randrange(lo + 1, n + 1)
            stride = rng.randrange(1, n + 5)
            residue = rng.randrange(stride)
            fobj = fragment("f", lo, hi, stride, residue)
            # Skip empty strict fragments.
            if not [x for x in range(lo, hi) if x % stride == residue]:
                continue
            d, p = make_validated(declaration_obj(n, a, b), plan_obj([fobj]))
            f = p.fragments[0]
            L = rng.randrange(n + 1)
            R = rng.randrange(L, n + 1)
            got = count_progression_target_interval(f, d, L, R)
            want = sum(1 for x in range(lo, hi) if x % stride == residue and L <= (a*x+b) % n < R)
            self.assertEqual(got, want, msg=f"case {idx}")

    def test_crt_intersection_random_3000(self):
        rng = random.Random(0xC127)
        for _ in range(3000):
            n = rng.randrange(2, 120)
            lo1, hi1 = sorted(rng.sample(range(n + 1), 2))
            lo2, hi2 = sorted(rng.sample(range(n + 1), 2))
            if lo1 == hi1 or lo2 == hi2:
                continue
            s1, s2 = rng.randrange(1, 20), rng.randrange(1, 20)
            r1, r2 = rng.randrange(s1), rng.randrange(s2)
            if not any(x % s1 == r1 for x in range(lo1, hi1)):
                continue
            if not any(x % s2 == r2 for x in range(lo2, hi2)):
                continue
            d, p = make_validated(
                declaration_obj(n, 1, 0),
                plan_obj([fragment("a", lo1, hi1, s1, r1), fragment("b", lo2, hi2, s2, r2)]),
            )
            common = intersect_progressions(p.fragments[0], p.fragments[1])
            want = [x for x in range(n) if lo1 <= x < hi1 and lo2 <= x < hi2 and x % s1 == r1 and x % s2 == r2]
            self.assertEqual(0 if common is None else progression_size(common), len(want))
            if common is not None:
                got = [x for x in range(common.lo, common.hi) if x % common.modulus == common.residue]
                self.assertEqual(got, want)


class SemanticTests(unittest.TestCase):
    def test_safe_identity(self):
        d, p = make_validated(declaration_obj(16, 1, 0), plan_obj([fragment("f", 0, 16)]))
        result = analyze(d, p)
        self.assertTrue(result.safe)
        self.assertEqual((result.B, result.T, result.C, result.Q, result.D), (16, 16, 16, 0, 0))

    def test_safe_sparse_case(self):
        d, p = safe_case()
        self.assertTrue(analyze(d, p).safe)
        self.assertEqual(explicit_defect(d, p), 0)

    def test_missing_defect(self):
        d, p = safe_case()
        raw = p.raw.copy()
        raw["fragments"] = raw["fragments"][:-1]
        p2 = validate_plan(raw, d)
        self.assertGreater(analyze(d, p2).D, 0)
        self.assertEqual(analyze(d, p2).D, explicit_defect(d, p2))
        self.assertEqual(canonical_witness(d, p2)["category"], "missing")

    def test_duplicate_defect(self):
        d = validate_declaration(declaration_obj(16, 1, 0, [[0, 8]]))
        p = validate_plan(plan_obj([fragment("a", 0, 8), fragment("b", 0, 8)]), d)
        self.assertEqual(analyze(d, p).D, 8)
        self.assertEqual(canonical_witness(d, p)["category"], "duplicate")

    def test_forbidden_defect(self):
        d = validate_declaration(declaration_obj(16, 1, 0, [[0, 8]]))
        p = validate_plan(plan_obj([fragment("a", 0, 9)]), d)
        self.assertEqual(analyze(d, p).D, 1)
        witness = canonical_witness(d, p)
        self.assertEqual(witness["category"], "forbidden")
        self.assertEqual(witness["target"], 8)

    def test_mixed_defect_equals_explicit(self):
        d = validate_declaration(declaration_obj(21, 4, 2, [[0, 3], [5, 14], [19, 21]]))
        p = validate_plan(plan_obj([
            fragment("a", 0, 21, 2, 0), fragment("b", 3, 20, 3, 1),
            fragment("c", 0, 10, 5, 0),
        ]), d)
        self.assertEqual(analyze(d, p).D, explicit_defect(d, p))

    def test_random_full_plan_oracle_1000(self):
        rng = random.Random(0x5EED123)
        checked = 0
        while checked < 1000:
            n = rng.randrange(2, 48)
            coprime = [a for a in range(1, n) if __import__("math").gcd(a, n) == 1]
            a, b = rng.choice(coprime), rng.randrange(n)
            points = sorted(rng.sample(range(n), rng.randrange(n + 1)))
            intervals = intervals_from_points(points, n)
            frags = []
            for j in range(rng.randrange(1, 8)):
                lo = rng.randrange(n)
                hi = rng.randrange(lo + 1, n + 1)
                stride = rng.randrange(1, min(n + 4, 12))
                residues = [r for r in range(stride) if any(x % stride == r for x in range(lo, hi))]
                if not residues:
                    continue
                frags.append(fragment(f"f{j:02d}", lo, hi, stride, rng.choice(residues), "committed" if j % 2 else "planned"))
            if not frags:
                continue
            d, p = make_validated(declaration_obj(n, a, b, intervals), plan_obj(frags))
            fast = analyze(d, p)
            self.assertEqual(fast.D, explicit_defect(d, p))
            self.assertEqual(fast.safe, fast.D == 0)
            checked += 1

    def test_source_inverse(self):
        d = validate_declaration(declaration_obj(97, 37, 11))
        for source in range(97):
            target = (37 * source + 11) % 97
            self.assertEqual(source_for_target(d, target), source)

    def test_prefix_defect_monotone(self):
        d, p = safe_case()
        # Add a duplicate for a deliberately unsafe plan.
        raw = {"schema": "pcs-plan-v2", "fragments": [*p.raw["fragments"], fragment("f999", 0, 5)]}
        p2 = validate_plan(raw, d)
        values = [analyze(d, p2, prefix=x).D for x in range(d.universe + 1)]
        self.assertEqual(values, sorted(values))

    def test_target_authorization_boundaries(self):
        d = validate_declaration(declaration_obj(20, 1, 0, [[2, 5], [9, 11]]))
        self.assertFalse(target_is_authorized(d, 1))
        self.assertTrue(target_is_authorized(d, 2))
        self.assertTrue(target_is_authorized(d, 4))
        self.assertFalse(target_is_authorized(d, 5))


class CertificateTests(unittest.TestCase):
    def setUp(self):
        self.d, self.p = safe_case()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "cert.jsonl"
        write_certificate(self.path, self.d, self.p)

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip(self):
        self.assertTrue(check_certificate(self.path, self.d, self.p).safe)

    def test_header_binds_declaration(self):
        raw = json.loads(json.dumps(self.d.raw))
        raw["permutation"]["offset"] = (raw["permutation"]["offset"] + 1) % raw["universe"]
        d2 = validate_declaration(raw)
        with self.assertRaises(PCSValidationError):
            check_certificate(self.path, d2, self.p)

    def test_header_binds_plan(self):
        raw = json.loads(json.dumps(self.p.raw))
        raw["fragments"][0]["phase"] = "planned"
        p2 = validate_plan(raw, self.d)
        with self.assertRaises(PCSValidationError):
            check_certificate(self.path, self.d, p2)

    def _mutate(self, fn):
        rows = [json.loads(x) for x in self.path.read_text().splitlines()]
        fn(rows)
        self.path.write_text("\n".join(json.dumps(x, sort_keys=True, separators=(",", ":")) for x in rows) + "\n")
        with self.assertRaises(PCSValidationError):
            check_certificate(self.path, self.d, self.p)

    def test_delete_row(self):
        self._mutate(lambda rows: rows.pop(1))

    def test_duplicate_row(self):
        self._mutate(lambda rows: rows.insert(1, dict(rows[1])))

    def test_reorder_rows(self):
        self._mutate(lambda rows: rows.__setitem__(slice(1, 3), [rows[2], rows[1]]))

    def test_modify_numeric_field(self):
        self._mutate(lambda rows: rows[1].__setitem__("size", rows[1]["size"] + 1))

    def test_modify_hash_field(self):
        self._mutate(lambda rows: rows[0].__setitem__("plan_sha256", "0" * 64))

    def test_add_unknown_field(self):
        self._mutate(lambda rows: rows[1].__setitem__("surprise", 1))

    def test_trailing_blank_line_rejected(self):
        self.path.write_text(self.path.read_text() + "\n")
        with self.assertRaises(PCSValidationError):
            check_certificate(self.path, self.d, self.p)

    def test_duplicate_key_rejected(self):
        lines = self.path.read_text().splitlines()
        lines[0] = lines[0][:-1] + ',"seq":99}'
        self.path.write_text("\n".join(lines) + "\n")
        with self.assertRaises(PCSValidationError):
            check_certificate(self.path, self.d, self.p)

    def test_tamper_matrix_200(self):
        original = [json.loads(x) for x in self.path.read_text().splitlines()]
        rng = random.Random(0xBAD5EED)
        for trial in range(200):
            rows = json.loads(json.dumps(original))
            idx = rng.randrange(len(rows))
            candidate_fields = [k for k, v in rows[idx].items() if isinstance(v, (int, str, bool))]
            key = rng.choice(candidate_fields)
            value = rows[idx][key]
            if isinstance(value, bool):
                rows[idx][key] = not value
            elif isinstance(value, int):
                rows[idx][key] = value + 1
            else:
                rows[idx][key] = value + "x"
            self.path.write_text("\n".join(json.dumps(x, sort_keys=True, separators=(",", ":")) for x in rows) + "\n")
            with self.assertRaises(PCSValidationError, msg=f"tamper trial {trial}"):
                check_certificate(self.path, self.d, self.p)


class WitnessTests(unittest.TestCase):
    def test_missing_witness_round_trip(self):
        d = validate_declaration(declaration_obj(16, 1, 0, [[0, 8]]))
        p = validate_plan(plan_obj([fragment("a", 0, 7)]), d)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "w.json"
            write_witness(path, d, p)
            witness = check_witness(path, d, p)
            self.assertEqual((witness["category"], witness["target"]), ("missing", 7))

    def test_duplicate_witness_round_trip(self):
        d = validate_declaration(declaration_obj(16, 1, 0, [[0, 8]]))
        p = validate_plan(plan_obj([fragment("a", 0, 8), fragment("b", 0, 8)]), d)
        witness = canonical_witness(d, p)
        self.assertEqual(witness["category"], "duplicate")
        self.assertEqual(witness["target"], 0)
        self.assertEqual(witness["covering_fragments"], ["a", "b"])

    def test_forbidden_witness_round_trip(self):
        d = validate_declaration(declaration_obj(16, 1, 0, [[0, 8]]))
        p = validate_plan(plan_obj([fragment("a", 0, 9)]), d)
        witness = canonical_witness(d, p)
        self.assertEqual(witness["category"], "forbidden")

    def test_safe_has_no_witness(self):
        d, p = safe_case()
        with self.assertRaises(PCSValidationError):
            canonical_witness(d, p)

    def test_witness_tamper_rejected(self):
        d = validate_declaration(declaration_obj(16, 1, 0, [[0, 8]]))
        p = validate_plan(plan_obj([fragment("a", 0, 7)]), d)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "w.json"
            write_witness(path, d, p)
            obj = json.loads(path.read_text())
            obj["target"] += 1
            path.write_text(json.dumps(obj))
            with self.assertRaises(PCSValidationError):
                check_witness(path, d, p)


class CLITests(unittest.TestCase):
    def _write(self, directory, d, p):
        dp, pp = Path(directory) / "d.json", Path(directory) / "p.json"
        dp.write_bytes(canonical_json_bytes(d) + b"\n")
        pp.write_bytes(canonical_json_bytes(p) + b"\n")
        return dp, pp

    def test_cli_round_trip(self):
        d, p = safe_case()
        with tempfile.TemporaryDirectory() as td:
            dp, pp = self._write(td, d.raw, p.raw)
            cp = Path(td) / "c.jsonl"
            env = {**os.environ, "PYTHONPATH": str(SOFTWARE)}
            make = subprocess.run([sys.executable, str(SOFTWARE / "pcs.py"), "make-certificate", str(dp), str(pp), str(cp)], env=env, capture_output=True, text=True)
            self.assertEqual(make.returncode, 0, make.stderr)
            check = subprocess.run([sys.executable, str(SOFTWARE / "pcs.py"), "check", str(dp), str(pp), str(cp), "--require-safe"], env=env, capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)

    def test_cli_unsafe_require_safe_exit_3(self):
        d = declaration_obj(8, 1, 0, [[0, 4]])
        p = plan_obj([fragment("f", 0, 5)])
        with tempfile.TemporaryDirectory() as td:
            dp, pp = self._write(td, d, p)
            cp = Path(td) / "c.jsonl"
            env = {**os.environ, "PYTHONPATH": str(SOFTWARE)}
            subprocess.check_call([sys.executable, str(SOFTWARE / "pcs.py"), "make-certificate", str(dp), str(pp), str(cp)], env=env, stdout=subprocess.DEVNULL)
            check = subprocess.run([sys.executable, str(SOFTWARE / "pcs.py"), "check", str(dp), str(pp), str(cp), "--require-safe"], env=env, capture_output=True, text=True)
            self.assertEqual(check.returncode, 3)

    def test_cli_bad_input_exit_2(self):
        with tempfile.TemporaryDirectory() as td:
            dp = Path(td) / "d.json"
            pp = Path(td) / "p.json"
            dp.write_text('{"schema":"bad"}')
            pp.write_text('{}')
            env = {**os.environ, "PYTHONPATH": str(SOFTWARE)}
            run = subprocess.run([sys.executable, str(SOFTWARE / "pcs.py"), "analyze", str(dp), str(pp)], env=env, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn("pcs:", run.stderr)


class HashAndCanonicalizationTests(unittest.TestCase):
    def test_canonical_hash_key_order_independent(self):
        self.assertEqual(canonical_sha256({"b": 1, "a": 2}), canonical_sha256({"a": 2, "b": 1}))

    def test_intervals_from_points(self):
        self.assertEqual(intervals_from_points([1, 2, 4, 7, 6], 10), [[1, 3], [4, 5], [6, 8]])

    def test_fragment_membership(self):
        d, p = make_validated(declaration_obj(20, 1, 0), plan_obj([fragment("f", 3, 17, 4, 1)]))
        f = p.fragments[0]
        got = [x for x in range(20) if fragment_contains_source(f, x)]
        self.assertEqual(got, [5, 9, 13])

    def test_certificate_chain_is_linked(self):
        d, p = safe_case()
        rows = certificate_rows(d, p)
        self.assertEqual(rows[0]["prev_sha256"], "0" * 64)
        for left, right in zip(rows, rows[1:]):
            self.assertEqual(right["prev_sha256"], left["row_sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
