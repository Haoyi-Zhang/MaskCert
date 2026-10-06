"""Restore the packaged scientific data without changing existing evidence."""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'data' / 'scientific-data.zip'


def members(archive, destination):
    """Check all member paths before creating files inside the destination."""
    root = destination.resolve()
    targets = []
    seen = set()
    for member in archive.infolist():
        name = member.orig_filename
        parts = name.split('/')
        if (member.is_dir() or '\x00' in name or '\\' in name or ':' in name
                or PurePosixPath(name).is_absolute()
                or PureWindowsPath(name).drive
                or any(part in ('', '.', '..') for part in parts)
                or any(part.endswith((' ', '.')) or PureWindowsPath(part).is_reserved()
                       for part in parts)
                or parts[0] not in ('cases', 'results')
                or stat.S_ISLNK(member.external_attr >> 16)):
            raise ValueError('unsupported archive member: ' + name)
        target = root.joinpath(*parts)
        if not target.resolve().is_relative_to(root):
            raise ValueError('archive member leaves destination: ' + name)
        key = name.casefold()
        if key in seen:
            raise ValueError('duplicate archive member: ' + name)
        seen.add(key)
        targets.append((member, target))
    return targets


def prepare(destination):
    restored = existing = 0
    with zipfile.ZipFile(ARCHIVE) as archive:
        targets = members(archive, destination)
        # Refuse changed files before extracting anything; reruns are harmless
        # when the existing bytes already match the archived observation.
        for member, target in targets:
            if not target.exists():
                continue
            if not target.is_file() or target.stat().st_size != member.file_size:
                raise ValueError('existing data differs: ' + member.filename)
            with target.open('rb') as current, archive.open(member) as saved:
                while True:
                    block = saved.read(1024 * 1024)
                    if current.read(len(block)) != block:
                        raise ValueError('existing data differs: ' + member.filename)
                    if not block:
                        break
            existing += 1
        for member, target in targets:
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as saved, target.open('xb') as output:
                shutil.copyfileobj(saved, output)
            restored += 1
    print(f'Scientific data: {restored} restored, {existing} already identical.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dest', type=Path, default=ROOT,
                        help='artifact root (default: this upload view)')
    args = parser.parse_args()
    try:
        prepare(args.dest)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
