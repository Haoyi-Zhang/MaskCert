"""Strict finite, integer-only declaration. No addresses or network operations."""
from __future__ import annotations
import json
from math import gcd, isfinite
from pathlib import Path
from typing import Any

MAX_N = 1 << 32
MAX_STEP = 64
MAX_EPOCHS = 16
MAX_ROWS = 128
MAX_INTERVALS = 1024
MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_CERTIFICATE_BYTES = 64 * 1024 * 1024
MAX_CERTIFICATE_LINE_BYTES = 65_536
MAX_FLOOR_STEPS = 68
MAX_TRANSCRIPT_INTEGER = (1 << 128) - 1
EXPLICIT_ORACLE_LIMIT = 1 << 20

class Invalid(ValueError):
    """Malformed or unsupported input, not a semantic coverage failure."""

def integer(x: Any, low: int, high: int) -> int:
    if type(x) is not int or not low <= x <= high:
        raise Invalid(f'integer outside [{low},{high}]')
    return x

def keys(x: Any, expected: set[str]) -> None:
    if type(x) is not dict or set(x) != expected:
        raise Invalid('unexpected or missing fields')

def intervals(xs: Any, n: int) -> list[list[int]]:
    if type(xs) is not list or len(xs) > MAX_INTERVALS:
        raise Invalid('interval list bound')
    prev = -1
    for x in xs:
        if type(x) is not list or len(x) != 2:
            raise Invalid('interval shape')
        l, h = integer(x[0], 0, n), integer(x[1], 0, n)
        if l >= h or l <= prev:
            raise Invalid('intervals must be nonempty, sorted, disjoint, nonadjacent')
        prev = h
    return xs

def row(x: Any, n: int, epochs: int) -> None:
    keys(x, {'epoch','lo','hi','step','residue','guard'})
    integer(x['epoch'], 0, epochs-1)
    l, h = integer(x['lo'], 0, n), integer(x['hi'], 0, n)
    if l > h:
        raise Invalid('reversed counter range')
    s = integer(x['step'], 1, MAX_STEP)
    integer(x['residue'], 0, s-1)
    intervals(x['guard'], n)

def validate(spec: Any, plan: Any) -> None:
    keys(spec, {'n','a','b','epochs','history'})
    n = integer(spec['n'], 1, MAX_N)
    a, b = integer(spec['a'], 0, n-1), integer(spec['b'], 0, n-1)
    if gcd(a,n) != 1:
        raise Invalid('affine map is not bijective')
    es = spec['epochs']
    if type(es) is not list or not 1 <= len(es) <= MAX_EPOCHS:
        raise Invalid('epoch bound')
    for e in es:
        keys(e, {'allow','exclude'})
        intervals(e['allow'], n)
        intervals(e['exclude'], n)
    keys(plan, {'context','future'})
    keys(plan['context'], {'n','a','b'})
    for k in ('n','a','b'):
        integer(plan['context'][k], 0, MAX_N)
        if plan['context'][k] != spec[k]:
            raise Invalid('context disagrees with independent declaration')
    if type(spec['history']) is not list or type(plan['future']) is not list:
        raise Invalid('row lists required')
    rs = spec['history'] + plan['future']
    if len(rs) > MAX_ROWS:
        raise Invalid('row bound')
    for r in rs:
        row(r, n, len(es))

def _pairs(ps: list[tuple[str, Any]]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for k,v in ps:
        if k in d:
            raise Invalid('duplicate JSON key')
        d[k] = v
    return d

def loads(text: str) -> Any:
    def bad_constant(x: str) -> None:
        raise Invalid('non-finite JSON number')
    def finite_float(x: str) -> float:
        value = float(x)
        if not isfinite(value):
            raise Invalid('non-finite JSON number')
        return value
    def limited_int(x: str) -> int:
        if len(x.lstrip('-')) > 40:
            raise Invalid('integer encoding too long')
        return int(x)
    try:
        return json.loads(text, object_pairs_hook=_pairs,
                          parse_constant=bad_constant, parse_int=limited_int,
                          parse_float=finite_float)
    except (ValueError, RecursionError) as ex:
        raise Invalid('invalid JSON: '+str(ex)) from ex

def load(path: str | Path) -> Any:
    p = Path(path)
    with p.open('rb') as f:
        raw = f.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise Invalid('input exceeds 8 MiB byte bound')
    try:
        return loads(raw.decode('utf-8'))
    except UnicodeError as ex:
        raise Invalid('input is not UTF-8') from ex


def certificate_lines(path: str | Path):
    """Bound line allocation before the checker parses an untrusted transcript."""
    with Path(path).open('rb') as f:
        total = 0
        while True:
            raw = f.readline(MAX_CERTIFICATE_LINE_BYTES + 1)
            if not raw:
                return
            total += len(raw)
            if len(raw) > MAX_CERTIFICATE_LINE_BYTES:
                raise Invalid('certificate line byte bound')
            if total > MAX_CERTIFICATE_BYTES:
                raise Invalid('certificate total byte bound')
            try:
                yield raw.decode('utf-8')
            except UnicodeError as ex:
                raise Invalid('certificate is not UTF-8') from ex
