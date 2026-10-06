"""Untrusted safe-anchor update producer; no imports from the checker.

This module assumes an old safe plan for its algebra. Only update_checker may
turn a full verified-safe transcript into a trusted in-process anchor.
"""
from __future__ import annotations
from collections import defaultdict, deque
import json
from typing import TextIO
from .model import Invalid, integer, validate
from .producer import (count, floor_value, floor_transcript, intersect_rows,
                       overlap, progression, subtract)


def changed_rows(old_spec: dict, old_plan: dict, spec: dict, plan: dict):
    """Exact multiset subtraction, preserving earliest positions of duplicates."""
    validate(old_spec, old_plan)
    validate(spec, plan)
    if any(old_spec[k] != spec[k] for k in ('n', 'a', 'b')):
        raise Invalid('update changes affine context')
    if len(old_spec['epochs']) != len(spec['epochs']):
        raise Invalid('update changes epoch count')
    if old_spec['history'] != spec['history']:
        raise Invalid('update changes trusted history')
    def key(row):
        return (row['epoch'], row['lo'], row['hi'], row['step'],
                row['residue'], tuple(tuple(x) for x in row['guard']))
    available = defaultdict(deque)
    for j, row in enumerate(old_plan['future']):
        available[key(row)].append(j)
    matched = set()
    added = []
    for j, row in enumerate(plan['future']):
        queue = available[key(row)]
        if queue:
            matched.add(queue.popleft())
        else:
            added.append(j)
    removed = [j for j in range(len(old_plan['future'])) if j not in matched]
    return removed, added


def update_defects(old_spec: dict, old_plan: dict, spec: dict, plan: dict,
                   prefix: int | None = None, floor=floor_value):
    """Exact on a safe old plan; the producer cannot establish that premise."""
    removed, added = changed_rows(old_spec, old_plan, spec, plan)
    n, a, b = (spec[k] for k in ('n', 'a', 'b'))
    if prefix is None:
        prefix = n
    integer(prefix, 0, n)
    answer = []
    for epoch, policy in enumerate(spec['epochs']):
        old_policy = old_spec['epochs'][epoch]
        U = subtract(old_policy['allow'], old_policy['exclude'])
        V = subtract(policy['allow'], policy['exclude'])
        born = subtract(V, U)
        def c(grid, mask):
            return count(grid, mask, n, a, b, floor)
        if U == V:
            value = 0
        else:
            value = c((0, 1, prefix), U) + c((0, 1, prefix), V)
            value -= 2 * c((0, 1, prefix), overlap(U, V))
        R = [old_plan['future'][j] for j in removed
             if old_plan['future'][j]['epoch'] == epoch]
        A = [plan['future'][j] for j in added
             if plan['future'][j]['epoch'] == epoch]
        for row in R:
            grid = progression(row, prefix)
            value -= c(grid, row['guard'])
            value += 2 * c(grid, overlap(row['guard'], V))
        for row in A:
            grid = progression(row, prefix)
            value += c(grid, row['guard'])
            value -= 2 * c(grid, overlap(row['guard'], born))
        for j, row in enumerate(A):
            for other in A[j+1:]:
                grid = intersect_rows(row, other, prefix)
                if grid[2]:
                    value += 2 * c(grid, overlap(overlap(row['guard'], other['guard']), V))
        for row in A:
            for other in R:
                grid = intersect_rows(row, other, prefix)
                if grid[2]:
                    value -= 2 * c(grid, overlap(overlap(row['guard'], other['guard']), V))
        answer.append(value)
    return answer


def write_update(old_spec: dict, old_plan: dict, spec: dict, plan: dict,
                 stream: TextIO, prefix: int | None = None):
    removed, added = changed_rows(old_spec, old_plan, spec, plan)
    if prefix is None:
        prefix = spec['n']
    integer(prefix, 0, spec['n'])
    def emit(obj):
        stream.write(json.dumps(obj, separators=(',', ':')) + '\n')
    emit({'kind': 'safe-anchor-update', 'prefix': prefix,
          'removed': removed, 'added': added})
    def witnessed(n, m, a, b):
        value, triples = floor_transcript(n, m, a, b)
        emit([value, triples])
        return value
    ds = update_defects(old_spec, old_plan, spec, plan, prefix, witnessed)
    emit({'defects': ds, 'accepted': not any(ds)})
    return ds


def locate_update(old_spec: dict, old_plan: dict, spec: dict, plan: dict):
    ds = update_defects(old_spec, old_plan, spec, plan)
    if not any(ds):
        return None
    epoch = next(j for j, value in enumerate(ds) if value)
    low, high = 0, spec['n']
    while high - low > 1:
        middle = (low + high) // 2
        if update_defects(old_spec, old_plan, spec, plan, middle)[epoch]:
            high = middle
        else:
            low = middle
    target = (spec['a'] * low + spec['b']) % spec['n']
    desired = subtract(spec['epochs'][epoch]['allow'], spec['epochs'][epoch]['exclude'])
    wanted = any(lo <= target < hi for lo, hi in desired)
    hits = []
    for j, row in enumerate(spec['history'] + plan['future']):
        if (row['epoch'] == epoch and row['lo'] <= low < row['hi']
            and low % row['step'] == row['residue']
            and any(lo <= target < hi for lo, hi in row['guard'])):
            hits.append(j)
    kind = 'forbidden' if not wanted else ('omission' if not hits else 'collision')
    return {'epoch': epoch, 'counter': low, 'target': target, 'kind': kind,
            'rows': hits[:2] if kind == 'collision' else hits[:1]}
