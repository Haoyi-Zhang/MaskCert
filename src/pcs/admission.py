"""Local integer-item consumption from a verified immutable schedule.

This module has no address mapping, networking, persistence or retry service.
History is a supplied completed prefix. Each iterator enumerates the future
once; creating another iterator deliberately replays it.
"""
from __future__ import annotations
from dataclasses import dataclass
from .model import Invalid
from .update_checker import SafeAnchor, advance_anchor


@dataclass(frozen=True, slots=True)
class Emission:
    epoch: int
    counter: int
    target: int
    row: int


def future_emissions(anchor: SafeAnchor):
    """Yield only the future contained in an established or advanced anchor.

    The private snapshot is obtained before the first yield. Caller mutations
    of the original declaration or plan cannot change this iteration.
    """
    if type(anchor) is not SafeAnchor:
        raise Invalid('an admitted immutable schedule is required')
    spec, plan = anchor.inputs()
    n, a, b = spec['n'], spec['a'], spec['b']
    offset = len(spec['history'])
    for epoch in range(len(spec['epochs'])):
        for position, row in enumerate(plan['future']):
            if row['epoch'] != epoch:
                continue
            step = row['step']
            start = row['lo'] + (row['residue'] - row['lo']) % step
            for counter in range(start, row['hi'], step):
                target = (a * counter + b) % n
                if any(low <= target < high for low, high in row['guard']):
                    yield Emission(epoch, counter, target, offset + position)


class LocalConsumer:
    """One traversal with a HOLD fence for application-requested replacements.

    Replacement before consumption uses the existing safe-base update check.
    Once consumption has started, emitted progress must be reconciled into a
    new independently declared history before constructing another consumer.
    """
    def __init__(self, anchor: SafeAnchor):
        if type(anchor) is not SafeAnchor:
            raise Invalid('a verified safe anchor is required')
        anchor.inputs()  # Validate the in-process capability before activation.
        self._basis = anchor
        self._items = future_emissions(anchor)
        self._started = False
        self._state = 'ready'

    def request_update(self, spec, plan, lines):
        # Fence the old stream BEFORE checking a newly requested policy/plan.
        self._state = 'hold'
        self._items = None
        if self._started:
            raise Invalid('consumed progress requires a newly declared history')
        advanced = advance_anchor(self._basis, spec, plan, lines)
        self._basis = advanced
        self._items = future_emissions(advanced)
        self._state = 'ready'

    def __iter__(self):
        return self

    def __next__(self):
        if self._state == 'hold':
            raise Invalid('item consumption is on hold')
        if self._state == 'complete':
            raise StopIteration
        self._started = True
        try:
            return next(self._items)
        except StopIteration:
            self._state = 'complete'
            raise
        except Exception:
            self._state = 'hold'
            self._items = None
            raise
