"""Restore only absent frozen material from the lossless distribution ZIP.

The ZIP contains data and the optional, MIT-noticed Linux Z3 library, never
Python/source scripts. Nothing is imported or executed from it. Existing
ordinary files must match every byte; differing files and links are refused.
Use ``python -B scripts/restore_inputs.py`` before standalone child commands.
The default reproduce.py calls this before its non-mutation snapshot.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data/frozen-material.zip"
MAX_ARCHIVE_BYTES = 12_000_000
MAX_TOTAL_BYTES = 400_000_000
MAX_MEMBER_BYTES = 34_000_000
MAX_DICTIONARY_BYTES = 8 * 1024 * 1024
BLOCK_BYTES = 1024 * 1024
# Exact paths/sizes of the 30 large files omitted by the prior remote sync.
# No digest manifest: existing originals are compared directly with ZIP bytes.
MEMBERS = {
    "cases/boundary.json": 3038453,
    "cases/smt/bench-09-full.smt2": 303713,
    "cases/transfer/remove.json": 18410993,
    "cases/transfer/revoke.json": 18484345,
    "cases/transfer/split.json": 18557696,
    "cases/update-bench/bench-04.json": 294205,
    "cases/update-bench/bench-08.json": 291801,
    "cases/update-bench/bench-09.json": 1136709,
    "cases/updates.json": 2105545,
    "results/boundary-certificate.jsonl": 32816640,
    "results/transfer/remove-full.jsonl": 32527928,
    "results/transfer/remove-update.jsonl": 288835,
    "results/transfer/revoke-full.jsonl": 32816644,
    "results/transfer/revoke-update.jsonl": 459308,
    "results/transfer/split-full.jsonl": 33037144,
    "results/transfer/split-update.jsonl": 798054,
    "results/windows-2026-10-06/cases/smt/bench-09-full.smt2": 303724,
    "results/windows-2026-10-06/cases/transfer/remove.json": 19441389,
    "results/windows-2026-10-06/cases/transfer/revoke.json": 19518846,
    "results/windows-2026-10-06/cases/transfer/split.json": 19596302,
    "results/windows-2026-10-06/cases/update-bench/bench-04.json": 311911,
    "results/windows-2026-10-06/cases/update-bench/bench-08.json": 309331,
    "results/windows-2026-10-06/cases/update-bench/bench-09.json": 1204927,
    "results/windows-2026-10-06/transfer/remove-full.jsonl": 33037882,
    "results/windows-2026-10-06/transfer/remove-update.jsonl": 292933,
    "results/windows-2026-10-06/transfer/revoke-full.jsonl": 33330694,
    "results/windows-2026-10-06/transfer/revoke-update.jsonl": 465454,
    "results/windows-2026-10-06/transfer/split-full.jsonl": 33555290,
    "results/windows-2026-10-06/transfer/split-update.jsonl": 810344,
    "third_party/z3/libz3.so.4": 27751664,
}


def ordinary(path, directory=False):
    """lstat rejects symlinks and Windows reparse points, not just escapes."""
    observed = path.lstat()
    reparse = getattr(observed, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if reparse or not expected(observed.st_mode):
        raise ValueError(f"not an ordinary {'directory' if directory else 'file'}: {path}")
    return observed


def target_path(root, name):
    relative = PurePosixPath(name)
    if (relative.is_absolute() or str(relative) != name or ".." in relative.parts
            or "\\" in name or ":" in name or not relative.parts):
        raise ValueError(f"invalid allowlisted path: {name}")
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if os.path.lexists(current):
            ordinary(current, directory=True)
    return root.joinpath(*relative.parts)


def validate_zip(archive):
    infos = archive.infolist()
    if archive.comment or len(infos) != len(MEMBERS) or len({i.filename for i in infos}) != len(infos):
        raise ValueError("ZIP count, duplicate member, or comment mismatch")
    if {i.filename for i in infos} != set(MEMBERS):
        raise ValueError("ZIP member set differs from the fixed allowlist")
    if sum(MEMBERS.values()) > MAX_TOTAL_BYTES:
        raise ValueError("uncompressed bundle limit exceeded")
    for info in infos:
        target_path(ROOT, info.filename)  # syntax only; no writes.
        mode = info.external_attr >> 16
        if (info.is_dir() or not stat.S_ISREG(mode) or info.flag_bits & 1
                or info.compress_type != zipfile.ZIP_LZMA
                or info.file_size != MEMBERS[info.filename]
                or not 0 <= info.file_size <= MAX_MEMBER_BYTES):
            raise ValueError(f"ZIP type/compression/size mismatch: {info.filename}")
        # ZIP-LZMA stores five properties bytes before the compressed stream.
        # Bound its dictionary before opening a decoder, independently of sizes.
        archive.fp.seek(info.header_offset)
        header = archive.fp.read(30)
        if len(header) != 30 or header[:4] != b"PK\x03\x04":
            raise ValueError("invalid local ZIP boundary")
        fields = struct.unpack("<4s5H3I2H", header)
        offset = info.header_offset + 30 + fields[9] + fields[10]
        if offset < 0 or offset + info.compress_size > archive.start_dir or info.compress_size < 9:
            raise ValueError("compressed member leaves ZIP data bounds")
        archive.fp.seek(offset)
        properties = archive.fp.read(9)
        if (len(properties) != 9 or int.from_bytes(properties[2:4], "little") != 5
                or not 0 < int.from_bytes(properties[5:9], "little") <= MAX_DICTIONARY_BYTES):
            raise ValueError("ZIP-LZMA property/dictionary limit exceeded")
    return {info.filename: info for info in infos}


def compare_member(archive, info, existing=None):
    """Read to EOF for ZIP CRC validation; compare originals without hashes."""
    read = 0
    with archive.open(info) as compressed:
        if existing is None:
            while block := compressed.read(BLOCK_BYTES):
                read += len(block)
                if read > info.file_size:
                    raise ValueError("member expands beyond its fixed size")
        else:
            if ordinary(existing).st_size != info.file_size:
                raise ValueError(f"existing file differs: {info.filename}")
            with existing.open("rb") as original:
                while block := compressed.read(BLOCK_BYTES):
                    read += len(block)
                    if read > info.file_size or original.read(len(block)) != block:
                        raise ValueError(f"existing file differs: {info.filename}")
                if original.read(1):
                    raise ValueError(f"existing file differs: {info.filename}")
    if read != info.file_size:
        raise ValueError("member ended before its fixed size")


def restore_inputs(root=ROOT, archive_path=ARCHIVE):
    root, archive_path = Path(root).absolute(), Path(archive_path).absolute()
    ordinary(root, directory=True)
    if ordinary(archive_path).st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("compressed archive exceeds 12 MB")
    missing, existing = [], []
    with zipfile.ZipFile(archive_path) as archive:
        infos = validate_zip(archive)
        # Complete preflight before any directory/file creation: wrong existing
        # bytes or a corrupt member must not materialize earlier missing files.
        for name in MEMBERS:
            target = target_path(root, name)
            present = os.path.lexists(target)
            compare_member(archive, infos[name], target if present else None)
            (existing if present else missing).append(name)
        for name in missing:
            target = target_path(root, name)
            current = root
            for part in PurePosixPath(name).parts[:-1]:
                current = current / part
                if not os.path.lexists(current):
                    current.mkdir()
                ordinary(current, directory=True)
            # Binary exclusive-create cannot overwrite a racing/differing file.
            with archive.open(infos[name]) as source, target.open("xb") as output:
                written = 0
                while block := source.read(BLOCK_BYTES):
                    written += len(block)
                    if written > MEMBERS[name]:
                        raise ValueError("member expands beyond its fixed size")
                    output.write(block)
                if written != MEMBERS[name]:
                    raise ValueError("restored member ended before its fixed size")
            ordinary(target)
    return {"restored_files": len(missing), "existing_files_byte_equal": len(existing),
            "uncompressed_bytes": sum(MEMBERS.values()), "source_programs_executed": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="existing ordinary destination directory (default: artifact root)")
    args = parser.parse_args()
    print(json.dumps(restore_inputs(args.root), sort_keys=True))


if __name__ == "__main__":
    main()
