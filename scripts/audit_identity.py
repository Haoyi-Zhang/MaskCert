"""Check the repaired artifact identity and model lineage without network access."""
from __future__ import annotations

import json
from pathlib import Path

from common import ROOT, bounded, finish

NAME = 'Mask-Aware Certificates for Affine Schedule Fragments'
KEY = 'mask-aware-certificates-for-permutation-complete-stateless-scan-plans'


def main() -> int:
    bounded()
    project = json.loads((ROOT / 'project.json').read_text(encoding='utf-8'))
    assert project['PROJECT_NAME'] == NAME
    assert project['SLUG'] == KEY
    assert project['VENUE_STATUS'].startswith('intent only')
    assert (ROOT / 'README.md').read_text(encoding='utf-8').startswith('# ' + NAME)

    model = (ROOT / 'src' / 'pcs' / 'model.py').read_text(encoding='utf-8')
    producer = (ROOT / 'src' / 'pcs' / 'producer.py').read_text(encoding='utf-8')
    checker = (ROOT / 'src' / 'pcs' / 'checker.py').read_text(encoding='utf-8')
    oracle = (ROOT / 'src' / 'pcs' / 'oracle.py').read_text(encoding='utf-8')
    assert "{'epoch','lo','hi','step','residue','guard'}" in model
    assert "{'n','a','b','epochs','history'}" in model
    assert "{'context','future'}" in model
    assert 'base+mass-2*auth+2*pairs' in producer
    assert 'Endpoint sweep' in checker and 'def extended' in checker
    assert 'EXPLICIT_ORACLE_LIMIT' in oracle

    witness = json.loads((ROOT / 'examples' / 'witness' / 'witness.json').read_text())
    assert witness == {
        'epoch': 0, 'counter': 2, 'target': 17, 'kind': 'omission', 'rows': []
    }

    sibling_paper = ROOT.parent / 'paper'
    paper_checked = sibling_paper.is_dir()
    if paper_checked:
        main_tex = (sibling_paper / 'main.tex').read_text(encoding='utf-8')
        protocol_tex = (sibling_paper / 'supplement.tex').read_text(encoding='utf-8')
        bibliography = (sibling_paper / 'references.bib').read_text(encoding='utf-8')
        assert r'\title{' + NAME + '}' in main_tex
        assert r'\title{Artifact Protocol for Affine Schedule Certificates}' in protocol_tex
        assert KEY in main_tex and KEY in protocol_tex
        assert 'LIPIcs.CP.2026.54' not in bibliography
        assert '10.4230/LIPIcs.CP.2026.43' in bibliography
        assert 'volume = {379}' in bibliography and 'pages = {43:1--43:21}' in bibliography

    report = {
        'project_name': NAME,
        'project_key': KEY,
        'lineage_decision': 'formal scope narrowing; incompatible pcs-v2 excluded',
        'guard_epoch_exclusion_history_schema_present': True,
        'linear_unauthorized_penalty_source_present': True,
        'separate_checker_arithmetic_source_present': True,
        'least_witness': witness,
        'sibling_paper_source_check': 'performed when a sibling paper directory is present; standalone artifact does not require it',
        'venue_status': project['VENUE_STATUS'],
        'all_checks_passed': True,
    }
    finish('identity-audit.json', report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
