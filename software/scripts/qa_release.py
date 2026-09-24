#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(cmd, cwd=None, text=True):
    return subprocess.run(cmd,cwd=cwd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=text)

def pdf_info(path: Path):
    text=run(['pdfinfo',str(path)]).stdout
    def field(name):
        m=re.search(rf'^{re.escape(name)}:\s*(.+)$',text,re.M)
        return m.group(1).strip() if m else None
    return {'raw':text,'pages':int(field('Pages')),'page_size':field('Page size'),'title':field('Title'),'author':field('Author')}

def render_and_measure(pdf: Path, outdir: Path):
    outdir.mkdir(parents=True,exist_ok=True)
    prefix=outdir/pdf.stem
    run(['pdftoppm','-r','120','-png',str(pdf),str(prefix)])
    from PIL import Image, ImageDraw
    paths=sorted(outdir.glob(pdf.stem+'-*.png'))
    metrics=[]; thumbs=[]
    for idx,path in enumerate(paths,1):
        im=Image.open(path).convert('L'); w,h=im.size
        hist=im.histogram(); total=w*h
        ink=sum(hist[:245])/total
        mask=im.point(lambda p: 255 if p<245 else 0)
        bbox=mask.getbbox()
        if bbox:
            left,top,right,bottom=bbox; margins=[left,top,w-right,h-bottom]
        else: margins=[w,h,w,h]
        edge_pixels=[]
        for x in range(w):
            for y in (0,1,h-2,h-1): edge_pixels.append(im.getpixel((x,y)))
        for y in range(2,h-2):
            for x in (0,1,w-2,w-1): edge_pixels.append(im.getpixel((x,y)))
        edge_ink=sum(1 for p in edge_pixels if p<220)/max(1,len(edge_pixels))
        metrics.append({'page':idx,'width_px':w,'height_px':h,'ink_fraction':ink,'bbox_margins_px':margins,'edge_ink_fraction':edge_ink})
        thumb=Image.open(path).convert('RGB'); thumb.thumbnail((320,420)); thumbs.append(thumb.copy())
    cols=3; cellw=340; cellh=455; rows=math.ceil(len(thumbs)/cols)
    sheet=Image.new('RGB',(cols*cellw,rows*cellh),'white'); draw=ImageDraw.Draw(sheet)
    for idx,im in enumerate(thumbs):
        x=(idx%cols)*cellw+(cellw-im.width)//2; y=(idx//cols)*cellh+25
        sheet.paste(im,(x,y)); draw.text(((idx%cols)*cellw+8,(idx//cols)*cellh+5),f'page {idx+1}',fill='black')
    sheet_path=outdir/(pdf.stem+'-contact-sheet.png'); sheet.save(sheet_path)
    return paths,metrics,sheet_path

def page_text_metrics(pdf: Path):
    info=pdf_info(pdf); values=[]
    for page in range(1,info['pages']+1):
        text=run(['pdftotext','-f',str(page),'-l',str(page),str(pdf),'-']).stdout
        values.append({'page':page,'characters':len(text),'nonspace_characters':len(re.sub(r'\s+','',text))})
    return values

def font_audit(pdf: Path):
    text=run(['pdffonts',str(pdf)]).stdout
    lines=text.splitlines(); records=[]
    for line in lines[2:]:
        parts=line.split()
        if len(parts)>=7:
            records.append({'name':parts[0],'type':parts[1],'encoding':parts[2],'embedded':parts[3],'subset':parts[4],'unicode':parts[5]})
    return records,text

def log_audit(path: Path):
    text=path.read_text(encoding='utf-8',errors='replace')
    errors=[]
    patterns=[
        ('LaTeX error',r'! LaTeX Error'),('undefined references',r'There were undefined references'),
        ('undefined citations', r'Citation .* undefined'),
    ]
    for label,pattern in patterns:
        if re.search(pattern,text,re.I): errors.append(label)
    over=[]
    for m in re.finditer(r'Overfull \\hbox \(([0-9.]+)pt too wide\)',text): over.append(float(m.group(1)))
    if over and max(over)>2.0: errors.append(f'overfull hbox max {max(over):.3f}pt')
    return {'errors':errors,'overfull_widths_pt':over,'max_overfull_pt':max(over) if over else 0.0}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]); args=ap.parse_args()
    root=args.root.resolve(); qa=root/'qa'; qa.mkdir(exist_ok=True)
    errors=[]
    pdfs=[('main',root/'paper/main.pdf',12),('supplement',root/'supplement/supplement.pdf',None)]
    pdf_report={}
    render_root=qa/'renders'
    if render_root.exists(): shutil.rmtree(render_root)
    for name,path,required_pages in pdfs:
        if not path.is_file(): errors.append(f'missing {path}'); continue
        info=pdf_info(path)
        if required_pages is not None and info['pages']!=required_pages: errors.append(f'{name} has {info["pages"]} pages, expected {required_pages}')
        if name=='supplement' and info['pages']<5: errors.append('supplement unexpectedly short')
        if not info['page_size'] or '612 x 792 pts' not in info['page_size']: errors.append(f'{name} is not US Letter: {info["page_size"]}')
        text=run(['pdftotext',str(path),'-']).stdout
        for token in ('??','TODO','TBD','PLACEHOLDER'):
            if token in text: errors.append(f'{name} extracted text contains {token}')
        pages=page_text_metrics(path)
        for p in pages:
            if p['nonspace_characters']<80: errors.append(f'{name} page {p["page"]} appears blank/sparse ({p["nonspace_characters"]} chars)')
        images,metrics,sheet=render_and_measure(path,render_root/name)
        if len(images)!=info['pages']: errors.append(f'{name} raster page count mismatch')
        for m in metrics:
            if m['ink_fraction']<0.003: errors.append(f'{name} page {m["page"]} raster appears blank')
            if m['edge_ink_fraction']>0.001: errors.append(f'{name} page {m["page"]} has ink on raster edge')
            if min(m['bbox_margins_px'])<8: errors.append(f'{name} page {m["page"]} content too near edge: {m["bbox_margins_px"]}')
        fonts,font_text=font_audit(path)
        for f in fonts:
            if f['embedded'].lower()!='yes': errors.append(f'{name} font not embedded: {f["name"]}')
        pdf_report[name]={'path':str(path.relative_to(root)),'info':{k:v for k,v in info.items() if k!='raw'},'page_text':pages,'raster_metrics':metrics,'contact_sheet':str(sheet.relative_to(root)),'fonts':fonts}
        (qa/f'{name}-pdfinfo.txt').write_text(info['raw'],encoding='utf-8')
        (qa/f'{name}-pdffonts.txt').write_text(font_text,encoding='utf-8')
    logs={}
    for name,path in [('main',root/'paper/main.log'),('supplement',root/'supplement/supplement.log')]:
        if not path.is_file(): errors.append(f'missing log {path}')
        else:
            audit=log_audit(path); logs[name]=audit; errors.extend(f'{name}: {e}' for e in audit['errors'])
    for source in [root/'paper/main.tex',root/'supplement/supplement.tex']:
        text=source.read_text(encoding='utf-8')
        if re.search(r'\b(TODO|TBD|PLACEHOLDER)\b',text,re.I): errors.append(f'placeholder in {source.relative_to(root)}')
    bbl=root/'paper/main.bbl'; rendered=re.findall(r'\\bibitem\{([^}]+)\}',bbl.read_text(encoding='utf-8',errors='replace')) if bbl.exists() else []
    if len(rendered)<40: errors.append(f'rendered bibliography count {len(rendered)} < 40')
    if len(rendered)!=len(set(rendered)): errors.append('duplicate rendered bibliography keys')
    fit_path=qa/'paper-fit.json'
    fit=json.loads(fit_path.read_text()) if fit_path.exists() else None
    report={'status':'ok' if not errors else 'failed','pdfs':pdf_report,'logs':logs,'rendered_reference_count':len(rendered),'paper_fit':fit,'errors':errors}
    (qa/'pdf-audit.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    md=['# PDF and manuscript audit','',f"Status: **{report['status']}**",'',f"Rendered bibliography entries: **{len(rendered)}**.",'']
    for name,data in pdf_report.items():
        md += [f"## {name.title()}","",f"- Pages: {data['info']['pages']}",f"- Page size: {data['info']['page_size']}",f"- Contact sheet: `{data['contact_sheet']}`",f"- Embedded fonts checked: {len(data['fonts'])}",""]
    if errors: md+=['## Errors','']+[f'- {e}' for e in errors]
    else: md+=['No unresolved citations/placeholders, serious overfull boxes, blank raster pages, edge clipping, missing embedded fonts, or page-count violations were detected. Raster metrics complement, but do not replace, human visual review of the included contact sheets.']
    (qa/'PDF-AUDIT.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'errors':errors},sort_keys=True))
    if errors: raise SystemExit(1)

if __name__=='__main__': main()
