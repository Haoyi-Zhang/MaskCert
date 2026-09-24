"""Exact certificate machinery for permutation-complete stateless scan plans.

The implementation deliberately uses only Python's standard library.  All
arithmetic is integer arithmetic; no floating-point value affects a verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import gcd
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
import json


class PCSValidationError(ValueError):
    """Raised when an input violates the strict schema or a certificate differs."""


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise PCSValidationError(f"duplicate JSON key: {key!r}")
        out[key] = value
    return out


def loads_strict(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except PCSValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise PCSValidationError(f"invalid JSON: {exc}") from exc


def load_json_strict(path: str | Path) -> Any:
    return loads_strict(Path(path).read_text(encoding="utf-8"))


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _need_int(value: Any, where: str, *, low: int | None = None,
              high: int | None = None) -> int:
    if not _is_int(value):
        raise PCSValidationError(f"{where} must be an integer (booleans are rejected)")
    if low is not None and value < low:
        raise PCSValidationError(f"{where} must be >= {low}")
    if high is not None and value > high:
        raise PCSValidationError(f"{where} must be <= {high}")
    return value


def _need_exact_keys(value: Any, keys: set[str], where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PCSValidationError(f"{where} must be an object")
    actual = set(value)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        raise PCSValidationError(
            f"{where} has wrong keys; missing={missing}, extra={extra}"
        )
    return value


def _need_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise PCSValidationError(f"{where} must be a non-empty string")
    return value


@dataclass(frozen=True, order=True)
class Interval:
    lo: int
    hi: int

    @property
    def size(self) -> int:
        return self.hi - self.lo


@dataclass(frozen=True)
class AffinePermutation:
    multiplier: int
    offset: int


@dataclass(frozen=True)
class Declaration:
    universe: int
    permutation: AffinePermutation
    authorized: tuple[Interval, ...]
    raw: dict[str, Any]

    @property
    def authorized_size(self) -> int:
        return sum(iv.size for iv in self.authorized)

    @property
    def digest(self) -> str:
        return canonical_sha256(self.raw)


@dataclass(frozen=True)
class Fragment:
    id: str
    phase: str
    lo: int
    hi: int
    stride: int
    residue: int


@dataclass(frozen=True)
class Plan:
    fragments: tuple[Fragment, ...]
    raw: dict[str, Any]

    @property
    def digest(self) -> str:
        return canonical_sha256(self.raw)


@dataclass(frozen=True)
class Progression:
    lo: int
    hi: int
    modulus: int
    residue: int


@dataclass(frozen=True)
class Analysis:
    B: int
    T: int
    C: int
    Q: int
    D: int
    safe: bool
    fragment_rows: tuple[tuple[str, int, int], ...]
    pair_rows: tuple[tuple[str, str, int], ...]


def validate_intervals(raw: Any, universe: int, where: str = "authorized") -> tuple[Interval, ...]:
    if not isinstance(raw, list):
        raise PCSValidationError(f"{where} must be an array")
    result: list[Interval] = []
    last_hi = -1
    for idx, pair in enumerate(raw):
        if not isinstance(pair, list) or len(pair) != 2:
            raise PCSValidationError(f"{where}[{idx}] must be [lo, hi]")
        lo = _need_int(pair[0], f"{where}[{idx}][0]", low=0, high=universe)
        hi = _need_int(pair[1], f"{where}[{idx}][1]", low=0, high=universe)
        if lo >= hi:
            raise PCSValidationError(f"{where}[{idx}] must satisfy lo < hi")
        if result and lo <= last_hi:
            relation = "overlaps" if lo < last_hi else "is adjacent to"
            raise PCSValidationError(
                f"{where}[{idx}] {relation} its predecessor; intervals must be canonical"
            )
        result.append(Interval(lo, hi))
        last_hi = hi
    return tuple(result)


def validate_declaration(raw: Any) -> Declaration:
    obj = _need_exact_keys(raw, {"schema", "universe", "permutation", "authorized"}, "declaration")
    if obj["schema"] != "pcs-declaration-v2":
        raise PCSValidationError("declaration.schema must be 'pcs-declaration-v2'")
    n = _need_int(obj["universe"], "declaration.universe", low=1, high=(1 << 63) - 1)
    pobj = _need_exact_keys(obj["permutation"], {"kind", "multiplier", "offset"}, "declaration.permutation")
    if pobj["kind"] != "affine":
        raise PCSValidationError("only the affine permutation family is supported")
    a = _need_int(pobj["multiplier"], "permutation.multiplier", low=0, high=n - 1)
    b = _need_int(pobj["offset"], "permutation.offset", low=0, high=n - 1)
    if gcd(a, n) != 1:
        raise PCSValidationError("permutation.multiplier must be coprime to universe")
    intervals = validate_intervals(obj["authorized"], n)
    return Declaration(n, AffinePermutation(a, b), intervals, obj)


def validate_plan(raw: Any, declaration: Declaration) -> Plan:
    obj = _need_exact_keys(raw, {"schema", "fragments"}, "plan")
    if obj["schema"] != "pcs-plan-v2":
        raise PCSValidationError("plan.schema must be 'pcs-plan-v2'")
    if not isinstance(obj["fragments"], list):
        raise PCSValidationError("plan.fragments must be an array")
    fragments: list[Fragment] = []
    seen: set[str] = set()
    previous_id: str | None = None
    n = declaration.universe
    keys = {"id", "phase", "lo", "hi", "stride", "residue"}
    for idx, item in enumerate(obj["fragments"]):
        fobj = _need_exact_keys(item, keys, f"plan.fragments[{idx}]")
        fid = _need_string(fobj["id"], f"plan.fragments[{idx}].id")
        if fid in seen:
            raise PCSValidationError(f"duplicate fragment id: {fid}")
        if previous_id is not None and fid <= previous_id:
            raise PCSValidationError("fragments must be ordered by strictly increasing id")
        seen.add(fid)
        previous_id = fid
        phase = _need_string(fobj["phase"], f"fragment {fid}.phase")
        if phase not in {"committed", "planned"}:
            raise PCSValidationError(f"fragment {fid}.phase must be committed or planned")
        lo = _need_int(fobj["lo"], f"fragment {fid}.lo", low=0, high=n)
        hi = _need_int(fobj["hi"], f"fragment {fid}.hi", low=0, high=n)
        if lo >= hi:
            raise PCSValidationError(f"fragment {fid} must satisfy lo < hi")
        stride = _need_int(fobj["stride"], f"fragment {fid}.stride", low=1, high=(1 << 63) - 1)
        residue = _need_int(fobj["residue"], f"fragment {fid}.residue", low=0, high=stride - 1)
        f = Fragment(fid, phase, lo, hi, stride, residue)
        if progression_first_count(f.lo, f.hi, f.stride, f.residue)[1] == 0:
            raise PCSValidationError(f"fragment {fid} selects no counters")
        fragments.append(f)
    return Plan(tuple(fragments), obj)


def load_inputs(declaration_path: str | Path, plan_path: str | Path) -> tuple[Declaration, Plan]:
    declaration = validate_declaration(load_json_strict(declaration_path))
    plan = validate_plan(load_json_strict(plan_path), declaration)
    return declaration, plan


def progression_first_count(lo: int, hi: int, modulus: int, residue: int) -> tuple[int, int]:
    first = lo + ((residue - lo) % modulus)
    if first >= hi:
        return first, 0
    return first, (hi - 1 - first) // modulus + 1


def floor_sum_unsigned(n: int, m: int, a: int, b: int) -> int:
    """Return sum_{0<=i<n} floor((a*i+b)/m), for nonnegative arguments."""
    if n < 0 or m <= 0 or a < 0 or b < 0:
        raise ValueError("floor_sum_unsigned requires n>=0, m>0, a>=0, b>=0")
    ans = 0
    while True:
        if a >= m:
            ans += (n - 1) * n * (a // m) // 2
            a %= m
        if b >= m:
            ans += n * (b // m)
            b %= m
        y_max = a * n + b
        if y_max < m:
            return ans
        n = y_max // m
        b = y_max % m
        m, a = a, m


def floor_sum(n: int, m: int, a: int, b: int) -> int:
    """Signed extension of floor_sum_unsigned using Euclidean division."""
    if n < 0 or m <= 0:
        raise ValueError("floor_sum requires n>=0 and m>0")
    qa, ra = divmod(a, m)
    qb, rb = divmod(b, m)
    return qa * n * (n - 1) // 2 + qb * n + floor_sum_unsigned(n, m, ra, rb)


def residue_lt_count(n: int, modulus: int, a: int, b: int, threshold: int) -> int:
    """Count k in [0,n) with (a*k+b) mod modulus < threshold."""
    if n < 0 or modulus <= 0 or not 0 <= threshold <= modulus:
        raise ValueError("invalid residue_lt_count arguments")
    if threshold == 0:
        return 0
    if threshold == modulus:
        return n
    ge = floor_sum(n, modulus, a, b + modulus - threshold) - floor_sum(n, modulus, a, b)
    result = n - ge
    if not 0 <= result <= n:
        raise AssertionError("internal residue count invariant failed")
    return result


def count_progression_target_interval(
    progression: Progression | Fragment,
    declaration: Declaration,
    target_lo: int,
    target_hi: int,
) -> int:
    if not 0 <= target_lo <= target_hi <= declaration.universe:
        raise ValueError("target interval outside universe")
    first, count = progression_first_count(
        progression.lo, progression.hi, progression.stride if isinstance(progression, Fragment) else progression.modulus,
        progression.residue,
    )
    if count == 0 or target_lo == target_hi:
        return 0
    step = progression.stride if isinstance(progression, Fragment) else progression.modulus
    a = declaration.permutation.multiplier * step
    b = declaration.permutation.multiplier * first + declaration.permutation.offset
    n = declaration.universe
    return residue_lt_count(count, n, a, b, target_hi) - residue_lt_count(count, n, a, b, target_lo)


def count_progression_mask(
    progression: Progression | Fragment,
    declaration: Declaration,
    intervals: Sequence[Interval] | None = None,
    prefix: int | None = None,
) -> int:
    use = declaration.authorized if intervals is None else intervals
    total = 0
    for iv in use:
        lo = iv.lo
        hi = iv.hi if prefix is None else min(iv.hi, prefix)
        if hi > lo and (prefix is None or lo < prefix):
            total += count_progression_target_interval(progression, declaration, lo, hi)
        if prefix is not None and iv.hi >= prefix:
            break
    return total


def progression_size(progression: Progression | Fragment) -> int:
    modulus = progression.stride if isinstance(progression, Fragment) else progression.modulus
    return progression_first_count(progression.lo, progression.hi, modulus, progression.residue)[1]


def intersect_progressions(left: Fragment, right: Fragment) -> Progression | None:
    lo = max(left.lo, right.lo)
    hi = min(left.hi, right.hi)
    if lo >= hi:
        return None
    m1, m2 = left.stride, right.stride
    r1, r2 = left.residue, right.residue
    g = gcd(m1, m2)
    delta = r2 - r1
    if delta % g:
        return None
    lcm = (m1 // g) * m2
    reduced = m2 // g
    if reduced == 1:
        t = 0
    else:
        inv = pow(m1 // g, -1, reduced)
        t = ((delta // g) * inv) % reduced
    residue = (r1 + m1 * t) % lcm
    result = Progression(lo, hi, lcm, residue)
    if progression_size(result) == 0:
        return None
    return result


def analyze(declaration: Declaration, plan: Plan, prefix: int | None = None) -> Analysis:
    if prefix is not None and not 0 <= prefix <= declaration.universe:
        raise ValueError("prefix outside universe")
    fragment_rows: list[tuple[str, int, int]] = []
    B = 0
    C = 0
    for fragment in plan.fragments:
        size = progression_size(fragment) if prefix is None else count_progression_target_interval(fragment, declaration, 0, prefix)
        authorized = count_progression_mask(fragment, declaration, prefix=prefix)
        B += size
        C += authorized
        fragment_rows.append((fragment.id, size, authorized))
    pair_rows: list[tuple[str, str, int]] = []
    Q = 0
    for i, left in enumerate(plan.fragments):
        for right in plan.fragments[i + 1:]:
            common = intersect_progressions(left, right)
            if common is None:
                count = 0
            elif prefix is None:
                count = progression_size(common)
            else:
                count = count_progression_target_interval(common, declaration, 0, prefix)
            Q += count
            pair_rows.append((left.id, right.id, count))
    if prefix is None:
        T = declaration.authorized_size
    else:
        T = sum(max(0, min(iv.hi, prefix) - iv.lo) for iv in declaration.authorized if iv.lo < prefix)
    D = B + T - 2 * C + 2 * Q
    if D < 0:
        raise AssertionError("nonnegative defect identity violated")
    return Analysis(B, T, C, Q, D, D == 0, tuple(fragment_rows), tuple(pair_rows))


def _chain_rows(core_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous = "0" * 64
    for seq, core in enumerate(core_rows):
        row = {"seq": seq, "prev_sha256": previous, **core}
        digest = sha256(canonical_json_bytes(row)).hexdigest()
        row["row_sha256"] = digest
        rows.append(row)
        previous = digest
    return rows


def certificate_rows(declaration: Declaration, plan: Plan) -> list[dict[str, Any]]:
    result = analyze(declaration, plan)
    cores: list[dict[str, Any]] = [{
        "type": "header",
        "schema": "pcs-certificate-v2",
        "declaration_sha256": declaration.digest,
        "plan_sha256": plan.digest,
        "fragment_count": len(plan.fragments),
        "pair_count": len(result.pair_rows),
    }]
    for fid, size, authorized in result.fragment_rows:
        cores.append({
            "type": "fragment", "id": fid, "size": size,
            "authorized_hits": authorized,
        })
    for left, right, count in result.pair_rows:
        cores.append({
            "type": "pair", "left": left, "right": right,
            "intersection": count,
        })
    cores.append({
        "type": "summary", "B": result.B, "T": result.T, "C": result.C,
        "Q": result.Q, "D": result.D, "safe": result.safe,
    })
    return _chain_rows(cores)


def write_certificate(path: str | Path, declaration: Declaration, plan: Plan) -> None:
    rows = certificate_rows(declaration, plan)
    text = "".join(canonical_json_bytes(row).decode("utf-8") + "\n" for row in rows)
    Path(path).write_text(text, encoding="utf-8")


def load_jsonl_strict(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise PCSValidationError(f"blank JSONL line at {line_no}")
        value = loads_strict(line)
        if not isinstance(value, dict):
            raise PCSValidationError(f"JSONL line {line_no} must be an object")
        rows.append(value)
    if not rows:
        raise PCSValidationError("certificate is empty")
    return rows


def check_certificate(path: str | Path, declaration: Declaration, plan: Plan) -> Analysis:
    actual = load_jsonl_strict(path)
    expected = certificate_rows(declaration, plan)
    if len(actual) != len(expected):
        raise PCSValidationError(
            f"certificate row count mismatch: got {len(actual)}, expected {len(expected)}"
        )
    for idx, (got, want) in enumerate(zip(actual, expected)):
        if canonical_json_bytes(got) != canonical_json_bytes(want):
            keys = sorted(set(got) | set(want))
            diffs = [key for key in keys if got.get(key, object()) != want.get(key, object())]
            raise PCSValidationError(f"certificate row {idx} mismatch in fields {diffs}")
    return analyze(declaration, plan)


def target_is_authorized(declaration: Declaration, target: int) -> bool:
    lo, hi = 0, len(declaration.authorized)
    while lo < hi:
        mid = (lo + hi) // 2
        iv = declaration.authorized[mid]
        if target < iv.lo:
            hi = mid
        elif target >= iv.hi:
            lo = mid + 1
        else:
            return True
    return False


def source_for_target(declaration: Declaration, target: int) -> int:
    n = declaration.universe
    inv = pow(declaration.permutation.multiplier, -1, n)
    return ((target - declaration.permutation.offset) * inv) % n


def fragment_contains_source(fragment: Fragment, source: int) -> bool:
    return fragment.lo <= source < fragment.hi and source % fragment.stride == fragment.residue


def canonical_witness(declaration: Declaration, plan: Plan) -> dict[str, Any]:
    full = analyze(declaration, plan)
    if full.safe:
        raise PCSValidationError("a safe plan has no defect witness")
    low, high = 1, declaration.universe
    while low < high:
        mid = (low + high) // 2
        if analyze(declaration, plan, prefix=mid).D > 0:
            high = mid
        else:
            low = mid + 1
    prefix = low
    target = prefix - 1
    before = analyze(declaration, plan, prefix=target).D
    at = analyze(declaration, plan, prefix=prefix).D
    source = source_for_target(declaration, target)
    covering = [f.id for f in plan.fragments if fragment_contains_source(f, source)]
    authorized = target_is_authorized(declaration, target)
    multiplicity = len(covering)
    if authorized and multiplicity == 0:
        category = "missing"
    elif authorized and multiplicity > 1:
        category = "duplicate"
    elif (not authorized) and multiplicity > 0:
        category = "forbidden"
    else:
        raise AssertionError("prefix witness does not have a local defect")
    core = {
        "schema": "pcs-witness-v2",
        "declaration_sha256": declaration.digest,
        "plan_sha256": plan.digest,
        "category": category,
        "target": target,
        "source_counter": source,
        "authorized": authorized,
        "expected_multiplicity": 1 if authorized else 0,
        "actual_multiplicity": multiplicity,
        "covering_fragments": covering,
        "prefix_defect_before": before,
        "prefix_defect_at": at,
        "total_defect": full.D,
    }
    return {**core, "witness_sha256": sha256(canonical_json_bytes(core)).hexdigest()}


def write_witness(path: str | Path, declaration: Declaration, plan: Plan) -> None:
    witness = canonical_witness(declaration, plan)
    Path(path).write_bytes(canonical_json_bytes(witness) + b"\n")


def check_witness(path: str | Path, declaration: Declaration, plan: Plan) -> dict[str, Any]:
    got = load_json_strict(path)
    want = canonical_witness(declaration, plan)
    if canonical_json_bytes(got) != canonical_json_bytes(want):
        if not isinstance(got, dict):
            raise PCSValidationError("witness must be an object")
        keys = sorted(set(got) | set(want))
        diffs = [key for key in keys if got.get(key, object()) != want.get(key, object())]
        raise PCSValidationError(f"witness mismatch in fields {diffs}")
    return want


def intervals_from_points(points: Iterable[int], universe: int) -> list[list[int]]:
    ordered = sorted(set(points))
    if any(p < 0 or p >= universe for p in ordered):
        raise ValueError("point outside universe")
    result: list[list[int]] = []
    for point in ordered:
        if result and result[-1][1] == point:
            result[-1][1] = point + 1
        else:
            result.append([point, point + 1])
    return result


def enumerate_fragment(fragment: Fragment) -> Iterator[int]:
    first, count = progression_first_count(fragment.lo, fragment.hi, fragment.stride, fragment.residue)
    for idx in range(count):
        yield first + idx * fragment.stride


def explicit_multiplicities(declaration: Declaration, plan: Plan) -> list[int]:
    if declaration.universe > 1_000_000:
        raise ValueError("explicit oracle limited to small universes")
    out = [0] * declaration.universe
    a, b, n = declaration.permutation.multiplier, declaration.permutation.offset, declaration.universe
    for fragment in plan.fragments:
        for source in enumerate_fragment(fragment):
            out[(a * source + b) % n] += 1
    return out


def explicit_defect(declaration: Declaration, plan: Plan) -> int:
    multiplicities = explicit_multiplicities(declaration, plan)
    return sum(
        (m - 1) ** 2 if target_is_authorized(declaration, x) else m ** 2
        for x, m in enumerate(multiplicities)
    )
