"""Export observed result fields, without depending on a sibling paper."""
from pathlib import Path
import argparse,json,shutil
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args()
args.out.mkdir(parents=True,exist_ok=True)
b=json.loads((root/'results/boundary.json').read_text())
v=json.loads((root/'results/validation.json').read_text())
s=b['symbolic'];x=b['exact']
values={'BoundaryBytes':str(s['certificate_bytes']),
        'BoundaryMiB':f"{s['certificate_bytes']/1048576:.3f}",
        'BoundaryProduce':f"{s['producer_cpu_seconds']:.3f}",
        'BoundaryCheck':f"{s['checker_cpu_seconds']:.3f}",
        'BoundaryPeak':f"{b['peak_rss_kib']/1024:.3f}",
        'BoundaryRun':f"{b['cpu_seconds']:.3f}",
        'ExactEnumerate':f"{x['enumeration_cpu_seconds']:.3f}",
        'ExactReplay':f"{x['replay_cpu_seconds']:.3f}",
        'SafeCases':str(v['safe']),'UnsafeCases':str(v['unsafe'])}
(args.out/'observations.tex').write_text(''.join('\\newcommand{\\'+k+'}{'+str(val)+'}\n' for k,val in values.items()))
shutil.copyfile(root/'results/prefix-defect.csv',args.out/'prefix-defect.csv')
