"""Derive the compact table from retained whole-workflow samples, not kernel times."""
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with gzip.open(ROOT/'results/record-workflow.json.gz', 'rt', encoding='utf-8') as stream:
        data = json.load(stream)
    if not data['all_checks_passed'] or data['quick'] or data['cases'] != len(data['results']):
        raise RuntimeError('complete record-workflow observations required')
    rows = []
    checks = holds = traversals = reads = 0
    for result in data['results']:
        if len(result['samples']) != 3 * data['repetitions']:
            raise RuntimeError('missing method/repetition sample')
        for sample in result['samples']:
            if [p['accepted'] for p in sample['decisions']] != result['pointwise_decisions']:
                raise RuntimeError('decision changed in retained sample')
            checks += len(sample['decisions'])
            holds += sum(not p['accepted'] for p in sample['decisions'])
            traversals += 1
            reads += sample['actual_record_reads']
        ss = result['input']
        medians = result['medians']
        rows.append(dict(case=result['case'], n=ss['n'], fragments=ss['fragments'],
            cycles=ss['cycles'], dense=ss['dense'],
            total_wall_ms={m: medians[m]['total_wall_ns']/1e6 for m in medians},
            warm_wall_ms={m: medians[m]['warm_wall_ns']/1e6 for m in medians},
            cold_wall_ms={m: medians[m]['cold_wall_ns']/1e6 for m in medians}))
    summary = dict(all_checks_passed=True, cases=data['cases'], repetitions=data['repetitions'],
                   traversals=traversals, replacement_decisions=checks, held_replacements=holds,
                   actual_record_reads=reads, environment=data['environment'], rows=rows)
    (ROOT/'results/record-workflow-summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    paper = ROOT.parent/'paper'
    if paper.is_dir():
        lines = []
        for r in rows:
            label = str(r['fragments']) + (r'$^*$' if r['dense'] else '')
            v = r['total_wall_ms']
            lines.append(f"{r['n']:,} & {label} & {8*r['cycles']} & "
                         f"{v['direct']:.1f} & {v['full']:.1f} & {v['incremental']:.1f}\\\\")
        table = '\\newcommand{\\RecordRows}{%\n' + '\n'.join(lines) + '\n}\n'
        for label, index in (('Small',0),('Reuse',5),('Large',6)):
            for method in ('direct','full','incremental'):
                suffix={'direct':'Direct','full':'Full','incremental':'Update'}[method]
                value=rows[index]['total_wall_ms'][method]
                table += f'\\newcommand{{\\Record{label}{suffix}}}{{{value:.1f}}}\n'
        for method,suffix in (('direct','Direct'),('full','Full'),('incremental','Update')):
            wins=sum(min(r['total_wall_ms'],key=r['total_wall_ms'].get)==method for r in rows)
            table += f'\\newcommand{{\\Record{suffix}Wins}}{{{wins}}}\n'
        (paper/'generated/record-workflow-table.tex').write_text(table, encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('cases', 'traversals', 'replacement_decisions',
                                             'held_replacements', 'actual_record_reads')}))


if __name__ == '__main__':
    main()
