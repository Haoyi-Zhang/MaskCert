"""Optional source/bibliography audit. Requires --paper; not used by core science.

Checks consistency against the curated primary-source ledger, not live source
truth or the correctness of every cited claim. pdfinfo is optional.
"""
from pathlib import Path
import argparse,json,re,subprocess,shutil
ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--paper',type=Path,required=True)
    ap.add_argument('--out',type=Path);args=ap.parse_args();paper=args.paper.resolve()
    tex=(paper/'main.tex').read_text();bib=(paper/'references.bib').read_text();bbl=(paper/'main.bbl').read_text()
    records=json.loads((ROOT/'docs/references.json').read_text())
    keyed={x['key']:x for x in records};assert len(keyed)==len(records)
    keys=re.findall(r'@\w+\{([^,]+),',bib);assert len(keys)==len(set(keys))==len(records)
    citations=[];contexts=[]
    for match in re.finditer(r'\\cite(?:\[[^\]]*\])*\{([^}]+)\}',tex):
        used=[x.strip() for x in match.group(1).split(',')];citations.extend(used)
        contexts.append({'keys':used,'source_line':tex.count('\n',0,match.start())+1,
                         'context':tex[max(0,match.start()-250):match.end()+180]})
    rendered=re.findall(r'\\bibitem\{([^}]+)\}',bbl)
    assert set(citations)==set(keys)==set(rendered)==set(keyed)
    assert len(rendered)==len(set(rendered)) and r'\nocite' not in tex
    dois=[x['doi'].lower() for x in records if x.get('doi')]
    assert len(dois)==len(set(dois))
    for entry in records:
        for field,value in entry['checked_fields'].items():
            assert value and (field+' = {'+value+'}') in bib, (entry['key'],field)
    assert '10.4230/LIPIcs.CP.2026.43' in bib
    assert r'\title{Mask-Aware Certificates for Affine Schedule Fragments}' in tex
    for path in (paper/'main.tex',paper/'supplement.tex'):
        text=path.read_text();assert not re.search(r'\b(?:TODO|TBD|FIXME)\b|\?\?',text)
    assert len(re.findall(r'\\section\{',tex))==9
    pages={}
    if shutil.which('pdfinfo'):
        for name,expected in [('main',12),('supplement',5)]:
            out=subprocess.check_output(['pdfinfo',str(paper/(name+'.pdf'))],text=True)
            page=int(re.search(r'Pages:\s+(\d+)',out).group(1));assert page==expected,(name,page)
            pages[name]=page
    for name in ('main','supplement'):
        log=(paper/(name+'.log')).read_text(errors='replace')
        assert not re.search(r'Overfull \\[hv]box|There were undefined references|Citation .* undefined',log)
    report={'all_structural_checks_passed':True,'references_rendered':len(rendered),
            'unique_nonempty_dois':len(dois),'citation_groups':len(contexts),'primary_ledger_entries':len(records),
            'main_sections':9,'pdf_pages':pages,'citation_contexts':contexts,
            'audit_scope':'source/BibTeX/compiled-reference consistency against curated primary metadata; not a live Crossref or independent scientific audit',
            'all_twenty_full_papers_read':False,'twelve_TDSC_full_paper_calibration_completed':False}
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='citation_contexts'},sort_keys=True))

if __name__=='__main__':main()
