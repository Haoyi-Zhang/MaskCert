"""Regenerate the retained safe example and the Theorem-7 witness bundle."""
from common import *
from casegen import mkrow
from pcs.producer import write_certificate, locate, defects
from pcs.checker import check_witness, verify
from pcs.model import certificate_lines

bounded()
directory = ROOT / 'examples'
directory.mkdir(exist_ok=True)

# N=64 example used to distinguish least (epoch,counter) from minimum target.
# The affine map sends every even counter to an odd target. Declared history
# covers residue 0 mod 4; the safe continuation covers residue 2 mod 4.
odd_targets = [[x, x + 1] for x in range(1, 64, 2)]
spec = dict(
    n=64,
    a=5,
    b=7,
    epochs=[dict(allow=odd_targets, exclude=[])],
    history=[mkrow(0, 0, 64, 4, 0, odd_targets)],
)
safe_plan = dict(
    context=dict(n=64, a=5, b=7),
    future=[mkrow(0, 0, 64, 4, 2, odd_targets)],
)
fault_plan = dict(context=dict(n=64, a=5, b=7), future=[])

(directory / 'declaration.json').write_text(json.dumps(spec, indent=2) + '\n')
(directory / 'plan.json').write_text(json.dumps(safe_plan, indent=2) + '\n')
with (directory / 'certificate.jsonl').open('w') as stream:
    write_certificate(spec, safe_plan, stream)
assert verify(spec, safe_plan, certificate_lines(directory / 'certificate.jsonl')).accepted

(directory / 'fault-declaration.json').write_text(json.dumps(spec, indent=2) + '\n')
(directory / 'fault-plan.json').write_text(json.dumps(fault_plan, indent=2) + '\n')
witness = locate(spec, fault_plan)
assert witness == {
    'epoch': 0,
    'counter': 2,
    'target': 17,
    'kind': 'omission',
    'rows': [],
}
assert defects(spec, fault_plan, 50) == [12]

bundle = directory / 'witness'
bundle.mkdir(exist_ok=True)
(bundle / 'witness.json').write_text(json.dumps(witness, indent=2) + '\n')
for name, prefix in (
    ('full.jsonl', None),
    ('before.jsonl', witness['counter']),
    ('through.jsonl', witness['counter'] + 1),
):
    with (bundle / name).open('w') as stream:
        write_certificate(spec, fault_plan, stream, prefix)
assert check_witness(
    spec,
    fault_plan,
    witness,
    *(certificate_lines(bundle / name)
      for name in ('full.jsonl', 'before.jsonl', 'through.jsonl')),
)

# Figure data remain the original mass-cancellation control.
multiplicities = [2, 1, 1, 0]
prefix_defect = [0]
for count in multiplicities:
    prefix_defect.append(prefix_defect[-1] + (count - 1) ** 2)
(ROOT / 'results' / 'prefix-defect.csv').write_text(
    'prefix,defect\n' + ''.join(f'{i},{v}\n' for i, v in enumerate(prefix_defect))
)
finish(
    'examples.json',
    dict(
        observation_kind='repair_recheck',
        all_checks_passed=True,
        examples=2,
        least_witness=witness,
        defect_at_prefix_50=12,
        prefix_defect=prefix_defect,
    ),
)
