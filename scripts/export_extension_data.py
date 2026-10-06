"""Deterministic paper tables/plots from retained new measurements, no remeasurement."""
from __future__ import annotations
import argparse,csv,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def read(path): return json.loads(path.read_text())
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
 p.add_argument('--results',type=Path,default=ROOT/'results',
                help='Explicit observation directory; default retains the historical Linux export')
 args=p.parse_args();results=args.results
 out=args.output;out.mkdir(parents=True,exist_ok=True)
 records=[read(results/f'update-bench/bench-{i:02d}.json') for i in range(20)]
 for record in records:
  assert record['safe'] and record['timed_repeats']==5
  for measurement in record['measurements'].values():
   s=[x['cpu_ns']/1e9/x['iterations'] for x in measurement['raw']]
   assert len(s)==5 and statistics.median(s)==measurement['cpu_median_s']
 def csvout(name,rows):
  with (out/name).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 for group,indices,xkey in [('fragment-scale',range(5),'base_fragments'),('edit-scale',range(15,20),'removed')]:
  rows=[]
  for i in indices:
   d=records[i];v={'x':d[xkey]}
   for role,key in [('full','full_checker'),('warm','warm_update_checker'),('cold','cold_update_checker')]:
    m=d['measurements'][key];v[role]=m['cpu_median_s']*1000
    v[role+'lo']=(m['cpu_median_s']-m['cpu_q1_s'])*1000
    v[role+'hi']=(m['cpu_q3_s']-m['cpu_median_s'])*1000
   rows.append(v)
  csvout(group+'.csv',rows)
 lines=[]
 for i in [0,2,4,5,9,15,16,17,18,19]:
  d=records[i];ms=d['measurements']; full=ms['full_checker'];warm=ms['warm_update_checker'];cold=ms['cold_update_checker']
  lines.append(f"{i:02d} & {d['base_fragments']} & {d['guard_intervals_per_fragment']} & {d['removed']}/{d['added']} & {d['full_floor_queries']:,}/{d['update_floor_queries']:,} & {full['cpu_median_s']*1000:.2f} & {warm['cpu_median_s']*1000:.2f} & {cold['cpu_median_s']*1000:.2f} "+r'\\')
 (out/'update-table.tex').write_text(r'\newcommand{\UpdateRows}{'+ '\n'.join(lines)+'}\n')
 lines=[]
 for name in ['split','remove','revoke']:
  d=read(results/f'transfer/{name}.json');m=d['measurements'];f=m['full_checker'];w=m['warm_update_checker'];c=m['cold_update_checker']
  label={'split':'Split one future row','remove':'Remove one future row','revoke':'Revoke 1,024 targets'}[name]
  lines.append(f"{label} & {d['defects'][0]:,} & {f['floor_queries']:,}/{w['floor_queries']:,} & {f['certificate_bytes']/2**20:.3f}/{w['certificate_bytes']/2**20:.3f} & {f['cpu_median_s']:.3f} & {w['cpu_median_s']:.3f} & {c['cpu_median_s']:.3f} "+r'\\')
 (out/'transfer-table.tex').write_text(r'\newcommand{\TransferRows}{'+ '\n'.join(lines)+'}\n')
 lines=[]
 for i in [0,2,4,8,9,19]:
  b=records[i]; f=read(results/f'smt/bench-{i:02d}-full.json');u=read(results/f'smt/bench-{i:02d}-reduced.json')
  fv=f"{f['cpu_median_s']:.3f}" if f['status_counts']['unsat']==5 else r'5 timeouts'
  lines.append(f"{i:02d} & {b['base_fragments']} & {b['guard_intervals_per_fragment']} & {fv} & {u['cpu_median_s']:.3f} & {b['boolean_encodings']['full']['clauses']:,}/{b['boolean_encodings']['safe_anchor']['clauses']:,} "+r'\\')
 (out/'smt-table.tex').write_text(r'\newcommand{\SMTRows}{'+ '\n'.join(lines)+'}\n')
 rows=[]
 for d in records:
  for role,m in d['measurements'].items():
   rows.append({'case':d['id'],'operation':role,'cpu_median_s':m['cpu_median_s'],'cpu_q1_s':m['cpu_q1_s'],'cpu_q3_s':m['cpu_q3_s'],'certificate_full_bytes':d['full_certificate_bytes'],'certificate_update_bytes':d['update_certificate_bytes']})
 csvout('all-measurements.csv',rows)
 print(json.dumps({'records':20,'tables':3,'plot_data_files':2,'statistics_rechecked':120}))
if __name__=='__main__':main()
