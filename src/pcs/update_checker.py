"""Safe-anchor verifier. Shares the existing transcript-checking arithmetic implementation
with the full *checker*, not the producer. No oracle or producer imports.

The anchor is a trusted in-process capability, not a serialized certificate,
signature or defence against arbitrary code in this Python process.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from .model import Invalid, MAX_INPUT_BYTES, integer, keys, loads, validate
from .checker import (Checked, TranscriptReader, lattice, masked, meet,
                      permitted, verify)

_ANCHOR_CAPABILITY = object()


@dataclass(frozen=True, slots=True, init=False)
class SafeAnchor:
    _declaration: str
    _plan: str
    _capability: object

    def __init__(self, key, declaration: str, plan: str):
        if key is not _ANCHOR_CAPABILITY:
            raise Invalid('safe anchors are created only by full verification')
        object.__setattr__(self, '_declaration', declaration)
        object.__setattr__(self, '_plan', plan)
        object.__setattr__(self, '_capability', key)

    def inputs(self):
        if self._capability is not _ANCHOR_CAPABILITY:
            raise Invalid('untrusted anchor')
        return loads(self._declaration), loads(self._plan)


def establish_anchor(spec: dict, plan: dict, full_lines) -> SafeAnchor:
    # Snapshot BEFORE checking: later caller mutation cannot change the premise.
    declaration = json.dumps(spec, separators=(',', ':'))
    future = json.dumps(plan, separators=(',', ':'))
    if max(len(declaration.encode()), len(future.encode())) > MAX_INPUT_BYTES:
        raise Invalid('anchor input byte bound')
    snapshot_spec, snapshot_plan = loads(declaration), loads(future)
    result = verify(snapshot_spec, snapshot_plan, full_lines)  # full prefix only
    if not result.accepted:
        raise Invalid('unsafe base cannot establish a safe anchor')
    return SafeAnchor(_ANCHOR_CAPABILITY, declaration, future)


def _difference(old_plan, plan):
    """Independent sorted merge, not producer's hash-queue matching."""
    def order(row):
        scalars = tuple(row[field] for field in ('epoch', 'lo', 'hi', 'step', 'residue'))
        return scalars + (tuple((span[0], span[1]) for span in row['guard']),)
    left = sorted((order(row), j) for j, row in enumerate(old_plan['future']))
    right = sorted((order(row), j) for j, row in enumerate(plan['future']))
    i = j = 0
    removed, added = [], []
    while i < len(left) and j < len(right):
        if left[i][0] == right[j][0]:
            i += 1
            j += 1
        elif left[i][0] < right[j][0]:
            removed.append(left[i][1])
            i += 1
        else:
            added.append(right[j][1])
            j += 1
    removed.extend(position for _, position in left[i:])
    added.extend(position for _, position in right[j:])
    return sorted(removed), sorted(added)


def _minus(left, right, n):
    # Use checker endpoint intersections, not the producer's subtraction.
    complement = []
    previous = 0
    for lo, hi in right:
        if previous < lo:
            complement.append([previous, lo])
        previous = hi
    if previous < n:
        complement.append([previous, n])
    return meet(left, complement)


def verify_update(anchor: SafeAnchor, spec: dict, plan: dict, lines,
                  prefix: int | None = None) -> Checked:
    if type(anchor) is not SafeAnchor:
        raise Invalid('a verified in-process safe anchor is required')
    old_spec, old_plan = anchor.inputs()
    validate(spec, plan)
    if any(spec[name] != old_spec[name] for name in ('n', 'a', 'b')):
        raise Invalid('update changes fixed affine context')
    if len(spec['epochs']) != len(old_spec['epochs']):
        raise Invalid('update changes epoch count')
    if spec['history'] != old_spec['history']:
        raise Invalid('trusted history cannot be replaced by an update')
    n, a, b = spec['n'], spec['a'], spec['b']
    if prefix is None:
        prefix = n
    integer(prefix, 0, n)
    removed, added = _difference(old_plan, plan)
    reader = TranscriptReader(lines)
    header = reader.take()
    keys(header, {'kind', 'prefix', 'removed', 'added'})
    integer(header['prefix'], 0, n)
    for label in ('removed', 'added'):
        if type(header[label]) is not list or any(type(x) is not int for x in header[label]):
            raise Invalid('update position list type')
    if header != {'kind': 'safe-anchor-update', 'prefix': prefix,
                  'removed': removed, 'added': added}:
        raise Invalid('update prefix or exact row-position difference mismatch')
    defects = []
    for epoch in range(len(spec['epochs'])):
        U = permitted(old_spec['epochs'][epoch], n)
        V = permitted(spec['epochs'][epoch], n)
        born = _minus(V, U, n)
        def c(grid, mask):
            return masked(grid, mask, n, a, b, reader)
        total = 0
        if U != V:
            total += c((0, 1, prefix), U)
            total += c((0, 1, prefix), V)
            total -= 2 * c((0, 1, prefix), meet(U, V))
        removed_rows = [old_plan['future'][j] for j in removed
                        if old_plan['future'][j]['epoch'] == epoch]
        added_rows = [plan['future'][j] for j in added
                      if plan['future'][j]['epoch'] == epoch]
        for row in removed_rows:
            source = lattice([row], prefix)
            total -= c(source, row['guard'])
            total += 2 * c(source, meet(row['guard'], V))
        for row in added_rows:
            source = lattice([row], prefix)
            total += c(source, row['guard'])
            total -= 2 * c(source, meet(row['guard'], born))
        for j, first in enumerate(added_rows):
            for second in added_rows[j+1:]:
                source = lattice([first, second], prefix)
                if source[2]:
                    total += 2 * c(source, meet(meet(first['guard'], second['guard']), V))
        for first in added_rows:
            for second in removed_rows:
                source = lattice([first, second], prefix)
                if source[2]:
                    total -= 2 * c(source, meet(meet(first['guard'], second['guard']), V))
        if total < 0:
            raise Invalid('negative update defect')
        defects.append(total)
    trailer = reader.take()
    keys(trailer, {'defects', 'accepted'})
    if (type(trailer['defects']) is not list
        or any(type(x) is not int for x in trailer['defects'])
        or type(trailer['accepted']) is not bool
        or trailer != {'defects': defects, 'accepted': not any(defects)}):
        raise Invalid('update trailer mismatch')
    reader.finish()
    return Checked(not any(defects), tuple(defects), reader.calls, reader.steps, reader.bytes)


def advance_anchor(anchor: SafeAnchor, spec: dict, plan: dict, lines) -> SafeAnchor:
    """Make a new safe anchor only after FULL accepted update verification."""
    declaration = json.dumps(spec, separators=(',', ':'))
    future = json.dumps(plan, separators=(',', ':'))
    if max(len(declaration.encode()), len(future.encode())) > MAX_INPUT_BYTES:
        raise Invalid('anchor input byte bound')
    ss, pp = loads(declaration), loads(future)
    result = verify_update(anchor, ss, pp, lines)
    if not result.accepted:
        raise Invalid('unsafe update cannot advance safe anchor')
    return SafeAnchor(_ANCHOR_CAPABILITY, declaration, future)


def check_update_witness(anchor: SafeAnchor, spec: dict, plan: dict, witness,
                         full_lines, before_lines, through_lines) -> bool:
    full = verify_update(anchor, spec, plan, full_lines)
    if full.accepted:
        raise Invalid('safe update has no fault witness')
    keys(witness, {'epoch', 'counter', 'target', 'kind', 'rows'})
    e = integer(witness['epoch'], 0, len(spec['epochs']) - 1)
    x = integer(witness['counter'], 0, spec['n'] - 1)
    if any(full.defects[:e]) or not full.defects[e]:
        raise Invalid('not the first defective epoch')
    before = verify_update(anchor, spec, plan, before_lines, x)
    through = verify_update(anchor, spec, plan, through_lines, x + 1)
    if before.defects[e] != 0 or through.defects[e] <= 0:
        raise Invalid('not the least defective source counter')
    target = (spec['a'] * x + spec['b']) % spec['n']
    integer(witness['target'], 0, spec['n'] - 1)
    if witness['target'] != target:
        raise Invalid('wrong target')
    desired = permitted(spec['epochs'][e], spec['n'])
    wanted = any(lo <= target < hi for lo, hi in desired)
    hits = []
    for j, row in enumerate(spec['history'] + plan['future']):
        if (row['epoch'] == e and row['lo'] <= x < row['hi']
            and x % row['step'] == row['residue']
            and any(lo <= target < hi for lo, hi in row['guard'])):
            hits.append(j)
    kind = 'forbidden' if not wanted else ('omission' if not hits else 'collision')
    positions = hits[:2] if kind == 'collision' else hits[:1]
    if (type(witness['rows']) is not list
        or any(type(j) is not int for j in witness['rows'])
        or witness['rows'] != positions or witness['kind'] != kind):
        raise Invalid('wrong canonical row positions or kind')
    return True
