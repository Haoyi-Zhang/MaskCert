"""Static dependency audit for the standalone Python artifact."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

from common import ROOT, bounded, finish

LOCAL_TOP_LEVEL = {'pcs'} | {p.stem for p in (ROOT / 'scripts').glob('*.py')}


def main() -> int:
    bounded()
    paths = [ROOT / 'pcs.py', ROOT / 'pcs-update.py']
    for directory in (ROOT / 'src', ROOT / 'scripts', ROOT / 'tests'):
        paths.extend(sorted(directory.rglob('*.py')))
    imported: set[str] = set()
    parsed = 0
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        parsed += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split('.')[0])
    external = sorted(name for name in imported
                      if name not in sys.stdlib_module_names
                      and name not in LOCAL_TOP_LEVEL)
    assert not external, external
    finish('dependency-audit.json', {
        'python_files_parsed': parsed,
        'imported_top_level_modules': sorted(imported),
        'external_runtime_or_test_dependencies': external,
        'matplotlib_imported': 'matplotlib' in imported,
        'standard_library_only': True,
        'scope': 'Python imports and default science; optional native SMT needs libz3',
        'optional_native_dependency': 'Z3 shared library through ctypes; not needed by core or default recheck',
        'all_checks_passed': True,
    })
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
