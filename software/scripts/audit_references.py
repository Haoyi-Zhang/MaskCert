#!/usr/bin/env python3
from __future__ import annotations
import argparse
import html
import json
import re
import unicodedata
from pathlib import Path


def clean(value: str) -> str:
    value=html.unescape(re.sub(r'<[^>]+>','',value or ''))
    value=unicodedata.normalize('NFKD',value)
    value=''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'\s+',' ',value).strip()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    args=ap.parse_args(); root=args.root.resolve()
    verification=json.loads((root/'docs/reference-verification.json').read_text(encoding='utf-8'))
    records=verification['records']
    errors=[]
    if len(records)<40: errors.append(f'only {len(records)} verified records')
    keys=[r['key'] for r in records]; dois=[r['doi'].lower() for r in records]
    if len(keys)!=len(set(keys)): errors.append('duplicate bibliography key')
    if len(dois)!=len(set(dois)): errors.append('duplicate DOI')
    raw_checked=0
    for r in records:
        path=root/'docs'/r['raw_file']
        if not path.is_file(): errors.append(f'missing raw record {path}'); continue
        try: msg=json.loads(path.read_text(encoding='utf-8'))['message']
        except Exception as exc: errors.append(f'invalid raw record {r["key"]}: {exc}'); continue
        if str(msg.get('DOI','')).lower()!=r['doi'].lower(): errors.append(f'DOI mismatch for {r["key"]}')
        title=msg.get('title',[]); title=title[0] if isinstance(title,list) and title else title
        if clean(str(title))!=clean(r['title']): errors.append(f'title mismatch for {r["key"]}')
        if not msg.get('author'): errors.append(f'no author for {r["key"]}')
        raw_checked+=1
    bib=(root/'paper/references.bib').read_text(encoding='utf-8')
    bib_keys=re.findall(r'@[A-Za-z]+\{([^,]+),',bib)
    if set(bib_keys)!=set(keys):
        errors.append(f'BibTeX key set differs: missing={sorted(set(keys)-set(bib_keys))}, extra={sorted(set(bib_keys)-set(keys))}')
    macros=(root/'paper/reference-macros.tex').read_text(encoding='utf-8')
    cited=set()
    for group in re.findall(r'\\cite\{([^}]+)\}',macros): cited.update(x.strip() for x in group.split(',') if x.strip())
    if cited!=set(keys): errors.append(f'citation macro set differs: missing={sorted(set(keys)-cited)}, extra={sorted(cited-set(keys))}')
    bbl=root/'paper/main.bbl'
    rendered=[]
    if bbl.is_file(): rendered=re.findall(r'\\bibitem\{([^}]+)\}',bbl.read_text(encoding='utf-8',errors='replace'))
    else: errors.append('paper/main.bbl missing; build paper before final audit')
    if len(rendered)<40: errors.append(f'only {len(rendered)} rendered bibliography items')
    if set(rendered)!=set(keys): errors.append(f'rendered key set differs: missing={sorted(set(keys)-set(rendered))}, extra={sorted(set(rendered)-set(keys))}')
    report={'status':'ok' if not errors else 'failed','verified_records':len(records),'raw_records_checked':raw_checked,'bibtex_entries':len(bib_keys),'cited_keys':len(cited),'rendered_items':len(rendered),'errors':errors}
    (root/'qa/reference-audit.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    md=['# Reference release audit','',f"Status: **{report['status']}**",'',f"- Verified Crossref records: {len(records)}",f"- Frozen raw records checked: {raw_checked}",f"- BibTeX entries: {len(bib_keys)}",f"- Keys cited through thematic macros: {len(cited)}",f"- Rendered `main.bbl` items: {len(rendered)}",'']
    if errors: md+=['## Errors','']+[f'- {e}' for e in errors]
    else: md+=['All admitted references have unique keys and DOIs, exact frozen Crossref DOI matches, nonempty author/title/year metadata from the online admission step, a BibTeX entry, a main-text citation group, and a rendered bibliography item. This audits bibliographic identity, not the truth of each cited result.']
    (root/'qa/REFERENCE-RELEASE-AUDIT.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(json.dumps(report,sort_keys=True))
    if errors: raise SystemExit(1)

if __name__=='__main__': main()
