"""Finite, single-process admission of reads from a caller-owned record file.

Certificates are supplied by the caller, never produced here. All three routes
use the same immutable row snapshots and emission iterator. History is a declared
checkpoint plus this instance's observed complete record reads; it is not a
crash-durable exactly-once log. Keep the input file unchanged while it is open.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
import os
import stat
import sys

from .admission import Emission
from .model import (Invalid, MAX_INPUT_BYTES, MAX_CERTIFICATE_BYTES,
                    MAX_CERTIFICATE_LINE_BYTES, integer, loads, validate)
from .producer import defects
from .update_checker import advance_anchor, establish_anchor

MAX_RECORDS = 1 << 20


@dataclass(frozen=True, slots=True)
class RecordRead:
    epoch: int
    counter: int
    target: int
    row: int
    payload: bytes


@dataclass(frozen=True, slots=True)
class _Row:
    epoch: int
    lo: int
    hi: int
    step: int
    residue: int
    guard: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class _Schedule:
    declaration: str
    plan: str
    n: int
    a: int
    b: int
    epochs: int
    history: tuple[_Row, ...]
    future: tuple[_Row, ...]

    def inputs(self):
        return loads(self.declaration), loads(self.plan)


def _snapshot(spec, plan, n):
    # Validate BEFORE JSON conversion, which would otherwise normalize tuples
    # and non-string dictionary keys. Revalidate the detached checked inputs.
    validate(spec, plan)
    integer(spec['n'], 1, MAX_RECORDS)
    if spec['n'] != n:
        raise Invalid('declaration does not match record file n')
    try:
        declaration = json.dumps(spec, separators=(',', ':'))
        future = json.dumps(plan, separators=(',', ':'))
        if max(len(declaration.encode('utf-8')), len(future.encode('utf-8'))) > MAX_INPUT_BYTES:
            raise Invalid('record gate input byte bound')
        ss, pp = loads(declaration), loads(future)
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise Invalid('cannot snapshot record gate inputs') from error
    validate(ss, pp)
    if ss['n'] != n:
        raise Invalid('snapshot does not match record file n')

    def rows(values):
        return tuple(_Row(r['epoch'], r['lo'], r['hi'], r['step'], r['residue'],
                          tuple((lo, hi) for lo, hi in r['guard'])) for r in values)

    return _Schedule(declaration, future, ss['n'], ss['a'], ss['b'],
                     len(ss['epochs']), rows(ss['history']), rows(pp['future']))


def _emissions(schedule, rows, offset=0):
    """Shared epoch, row, counter traversal; no route-specific item checks."""
    for epoch in range(schedule.epochs):
        for position, row in enumerate(rows):
            if row.epoch != epoch:
                continue
            start = row.lo + (row.residue - row.lo) % row.step
            for counter in range(start, row.hi, row.step):
                target = (schedule.a * counter + schedule.b) % schedule.n
                if any(lo <= target < hi for lo, hi in row.guard):
                    yield Emission(epoch, counter, target, offset + position)


def _history(schedule):
    return Counter((item.epoch, item.counter, item.target)
                   for item in _emissions(schedule, schedule.history))


def _certificate_lines(certificate):
    """Detach bounded text evidence before invoking either anchor checker."""
    if isinstance(certificate, str):
        try:
            if len(certificate.encode('utf-8')) > MAX_CERTIFICATE_BYTES:
                raise Invalid('certificate total byte bound')
        except UnicodeError as error:
            raise Invalid('certificate is not UTF-8') from error
        certificate = certificate.splitlines(keepends=True)
    try:
        source = iter(certificate)
    except TypeError as error:
        raise Invalid('certificate text or iterable of text lines required') from error
    lines = []
    total = 0
    for line in source:
        if type(line) is not str:
            raise Invalid('certificate lines must be text')
        try:
            size = len(line.encode('utf-8'))
        except UnicodeError as error:
            raise Invalid('certificate is not UTF-8') from error
        total += size
        if size == 0 or size > MAX_CERTIFICATE_LINE_BYTES:
            raise Invalid('certificate line byte bound')
        if total > MAX_CERTIFICATE_BYTES:
            raise Invalid('certificate total byte bound')
        lines.append(line)
    return tuple(lines)


def _windows_owner(fd):
    """Compare the handle owner with the process user/default owner SIDs."""
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    security = ctypes.WinDLL('advapi32', use_last_error=True)
    pointer = ctypes.c_void_p
    security.GetSecurityInfo.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                        ctypes.POINTER(pointer), pointer, pointer, pointer,
                                        ctypes.POINTER(pointer)]
    security.GetSecurityInfo.restype = wintypes.DWORD
    security.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                         ctypes.POINTER(wintypes.HANDLE)]
    security.OpenProcessToken.restype = wintypes.BOOL
    security.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, pointer,
                                            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    security.GetTokenInformation.restype = wintypes.BOOL
    security.EqualSid.argtypes = [pointer, pointer]
    security.EqualSid.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [pointer]
    kernel.LocalFree.restype = pointer
    owner, descriptor = pointer(), pointer()
    token = wintypes.HANDLE()
    try:
        status = security.GetSecurityInfo(msvcrt.get_osfhandle(fd), 1, 1,
                                          ctypes.byref(owner), None, None, None,
                                          ctypes.byref(descriptor))
        if status or not owner.value:
            raise Invalid('cannot determine record file owner')
        if not security.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
            raise Invalid('cannot determine process owner')
        for kind in (1, 4):  # TokenUser, TokenOwner (e.g. an elevated local owner).
            needed = wintypes.DWORD()
            security.GetTokenInformation(token, kind, None, 0, ctypes.byref(needed))
            if not needed.value:
                raise Invalid('cannot determine process owner SID')
            buffer = ctypes.create_string_buffer(needed.value)
            if not security.GetTokenInformation(token, kind, buffer, needed.value,
                                                ctypes.byref(needed)):
                raise Invalid('cannot read process owner SID')
            sid = ctypes.cast(buffer, ctypes.POINTER(pointer)).contents.value
            if security.EqualSid(owner, sid):
                return
        raise Invalid('record file must be owned by the current process user/owner')
    finally:
        if token.value:
            kernel.CloseHandle(token)
        if descriptor.value:
            kernel.LocalFree(descriptor)


def _local_path(path):
    try:
        path = os.fspath(path)
    except TypeError as error:
        raise Invalid('a local record file path is required') from error
    if type(path) is not str or not path or '\x00' in path:
        raise Invalid('a local record file path is required')
    if path.startswith(('\\\\', '//')) or '://' in path:
        raise Invalid('record file must be local')
    if os.name == 'nt':
        import ctypes
        drive = os.path.splitdrive(os.path.abspath(path))[0]
        if ctypes.windll.kernel32.GetDriveTypeW(drive + '\\') == 4:
            raise Invalid('record file must not be on a network drive')
    return path


def _file_signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class RecordGate:
    """One local record traversal, with a fail-closed replacement fence.

    ``admit(spec, plan, certificate=None)`` admits the first safe checkpoint.
    ``replace(...)`` requires unchanged declared history and no read started
    since admit/reconcile. ``reconcile(...)`` requires exact literal history
    plus pending observed occurrences, and always checks from scratch.

    The certificate argument is positional or keyword: full text/line evidence
    for full/incremental admit and reconcile, full evidence for full replace,
    update evidence for incremental replace, and ignored for direct decisions.
    Well-formed unsafe proposals return False; malformed ones raise Invalid.
    Either failure leaves HOLD, retaining the last accepted checkpoint/log.
    ``total_reads`` counts unbuffered record read calls, including failed/short
    calls; ``pending_observed`` logs only complete records actually read.
    The object is single-threaded and does not prevent writes by other handles.
    """

    def __init__(self, path, *, n, record_size, method):
        self._n = integer(n, 1, MAX_RECORDS)
        self._record_size = integer(record_size, 1, sys.maxsize // n)
        if type(method) is not str or method not in ('direct', 'full', 'incremental'):
            raise Invalid('method must be direct, full, or incremental')
        self._method = method
        self._fd = None
        self._state = 'hold'
        self._checkpoint = None
        self._anchor = None
        self._items = self._next = None
        self._started = False
        self._observed = []
        self._total_reads = 0
        path = _local_path(path)
        try:
            before = os.stat(path, follow_symlinks=False)
            if not stat.S_ISREG(before.st_mode):
                raise Invalid('record input must be a regular nonsymlink file')
            flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
            flags |= getattr(os, 'O_NONBLOCK', 0)
            self._fd = os.open(path, flags)
            opened = os.fstat(self._fd)
            # Windows path-stat and handle-stat can report different ctime
            # meanings. Bind opening identity/size/mtime, then use handle-stat
            # alone for the immutable file metadata checkpoint thereafter.
            if (not stat.S_ISREG(opened.st_mode)
                    or _file_signature(before)[:4] != _file_signature(opened)[:4]):
                raise Invalid('record file changed while opening')
            if opened.st_size != n * record_size:
                raise Invalid('record file length must equal n * record_size')
            if os.name == 'nt':
                _windows_owner(self._fd)
            elif hasattr(os, 'geteuid') and opened.st_uid != os.geteuid():
                raise Invalid('record file must be owned by the current user')
            self._signature = _file_signature(opened)
        except (OSError, ValueError) as error:
            self.close()
            if isinstance(error, Invalid):
                raise
            raise Invalid('cannot open fixed-size record input') from error

    @property
    def n(self):
        return self._n

    @property
    def record_size(self):
        return self._record_size

    @property
    def method(self):
        return self._method

    @property
    def state(self):
        return self._state

    @property
    def closed(self):
        return self._fd is None

    @property
    def total_reads(self):
        return self._total_reads

    @property
    def pending_observed(self):
        return tuple(self._observed)

    def _hold(self):
        self._state = 'hold'
        self._items = self._next = None

    def _check_file(self):
        if self.closed:
            raise Invalid('record gate is closed')
        try:
            info = os.fstat(self._fd)
        except OSError as error:
            raise Invalid('cannot stat record input') from error
        if not stat.S_ISREG(info.st_mode) or _file_signature(info) != self._signature:
            raise Invalid('record input changed since opening')

    def _proposal(self, spec, plan):
        self._check_file()
        candidate = _snapshot(spec, plan, self.n)
        if self._checkpoint is not None:
            old = self._checkpoint
            if (candidate.n, candidate.a, candidate.b, candidate.epochs) != (old.n, old.a, old.b, old.epochs):
                raise Invalid('proposal changes fixed affine context or epoch count')
        return candidate

    def _checked(self, candidate, certificate, *, update=False):
        spec, plan = candidate.inputs()
        if self.method == 'direct':
            return all(value == 0 for value in defects(spec, plan)), None
        # Snapshotting evidence here also keeps user iterator exceptions outside
        # the two narrowly classified semantic-unsafe anchor exits below.
        lines = _certificate_lines(certificate)
        try:
            if update:
                anchor = advance_anchor(self._anchor, spec, plan, lines)
            else:
                anchor = establish_anchor(spec, plan, lines)
        except Invalid as error:
            # These exits occur only AFTER the respective checker has validated
            # an entire nonzero-defect transcript. Do not hide malformed input.
            unsafe = ('unsafe update cannot advance safe anchor' if update
                      else 'unsafe base cannot establish a safe anchor')
            if str(error) == unsafe:
                return False, None
            raise
        return True, anchor

    def _activate(self, candidate, anchor):
        self._check_file()
        items = _emissions(candidate, candidate.future, len(candidate.history))
        first = next(items, None)
        self._checkpoint, self._anchor = candidate, anchor
        self._items, self._next = items, first
        self._observed = []
        self._started = False
        self._state = 'complete' if first is None else 'ready'

    def admit(self, spec, plan, certificate=None):
        self._hold()
        if self._checkpoint is not None:
            raise Invalid('already admitted; use replace or reconcile')
        candidate = self._proposal(spec, plan)
        accepted, anchor = self._checked(candidate, certificate)
        if accepted:
            self._activate(candidate, anchor)
        return accepted

    def replace(self, spec, plan, certificate=None):
        self._hold()
        if self._checkpoint is None:
            raise Invalid('admit a safe initial checkpoint first')
        if self._started:
            raise Invalid('record reads require history reconciliation before replacement')
        candidate = self._proposal(spec, plan)
        if candidate.history != self._checkpoint.history:
            raise Invalid('replacement changes declared history; use reconcile')
        accepted, anchor = self._checked(candidate, certificate,
                                        update=self.method == 'incremental')
        if accepted:
            self._activate(candidate, anchor)
        return accepted

    def reconcile(self, spec, plan, certificate=None):
        self._hold()
        if self._checkpoint is None:
            raise Invalid('admit a safe initial checkpoint first')
        candidate = self._proposal(spec, plan)
        expected = _history(self._checkpoint)
        expected.update(self._observed)
        if _history(candidate) != expected:
            raise Invalid('new history must equal declared history plus observed occurrences')
        # History changed: even the incremental route requires a FULL rebase.
        accepted, anchor = self._checked(candidate, certificate)
        if accepted:
            self._activate(candidate, anchor)
        return accepted

    def consume(self, limit=None):
        if self.closed or self.state == 'hold':
            raise Invalid('record consumption is on hold or closed')
        if limit is not None and (type(limit) is not int or limit < 0):
            self._hold()
            raise Invalid('consume limit must be a nonnegative integer or None')
        result = []
        try:
            while self._next is not None and (limit is None or len(result) < limit):
                item = self._next
                self._check_file()
                self._started = True
                os.lseek(self._fd, item.target * self.record_size, os.SEEK_SET)
                self._total_reads += 1
                payload = os.read(self._fd, self.record_size)
                if len(payload) != self.record_size:
                    raise Invalid('short fixed-size record read')
                # Log before advancing or returning: earlier reads survive a
                # later exception in the same consume call and can be reconciled.
                self._observed.append((item.epoch, item.counter, item.target))
                result.append(RecordRead(item.epoch, item.counter, item.target, item.row, payload))
                self._next = next(self._items, None)
            if self._next is None:
                self._state = 'complete'
        except Exception as error:
            self._hold()
            if isinstance(error, OSError):
                raise Invalid('fixed-size record read failed') from error
            raise
        return result

    def close(self):
        self._hold()
        fd, self._fd = self._fd, None
        if fd is not None:
            os.close(fd)

    def __enter__(self):
        if self.closed:
            raise Invalid('record gate is closed')
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
