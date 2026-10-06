"""Frozen synthetic selection for the safe-anchor extension, not real traffic."""
from copy import deepcopy
from math import gcd
import random
from casegen import mkrow, spans_from_bits


def selected_cases():
    records = []
    sizes = [1, 2, 7, 8, 15, 17, 31, 32, 63, 65, 97, 127]
    for index in range(96):
        rng = random.Random(947000 + index)
        n = sizes[index % len(sizes)]
        a = rng.choice([j for j in range(n) if gcd(j, n) == 1])
        b = rng.randrange(n)
        epochs = 1 + index % 3
        spec = dict(n=n, a=a, b=b, epochs=[], history=[])
        future = []
        for e in range(epochs):
            allowed = [rng.random() < .8 for _ in range(n)]
            excluded = [rng.random() < .2 for _ in range(n)]
            guard = spans_from_bits([u and not x for u, x in zip(allowed, excluded)])
            spec['epochs'].append({'allow': spans_from_bits(allowed),
                                   'exclude': spans_from_bits(excluded)})
            before, after = 1 + rng.randrange(3), 1 + rng.randrange(5)
            cut = n // 3
            for residue in range(before):
                spec['history'].append(mkrow(e, 0, cut, before, residue, guard))
            for residue in range(after):
                future.append(mkrow(e, cut, n, after, residue, guard))
        # Empty duplicate values are legitimate; matching remains positional.
        future += [mkrow(0, 0, 0, 1, 0, [])] * 2
        plan = dict(context={k: spec[k] for k in ('n', 'a', 'b')}, future=deepcopy(future))
        newspec, newplan = deepcopy(spec), deepcopy(plan)
        mode = index % 8
        label = ['no-op-reorder', 'split-source', 'split-guard', 'remove',
                 'duplicate', 'policy-only', 'mixed', 'policy-and-guard'][mode]
        if mode == 0:
            rng.shuffle(newplan['future'])
        elif mode == 1:
            position = rng.randrange(len(future)-2)
            row = newplan['future'].pop(position)
            middle = (row['lo'] + row['hi']) // 2
            lo, hi = deepcopy(row), deepcopy(row)
            lo['hi'], hi['lo'] = middle, middle
            newplan['future'][position:position] = [lo, hi]
        elif mode == 2:
            position = rng.randrange(len(future)-2)
            row = newplan['future'].pop(position)
            left, right = deepcopy(row), deepcopy(row)
            cut = n // 2
            left['guard'] = [[lo, min(hi, cut)] for lo, hi in row['guard'] if lo < cut]
            right['guard'] = [[max(lo, cut), hi] for lo, hi in row['guard'] if hi > cut]
            newplan['future'][position:position] = [left, right]
        elif mode == 3:
            for _ in range(min(3, len(newplan['future']))):
                newplan['future'].pop(rng.randrange(len(newplan['future'])))
        elif mode == 4:
            for _ in range(1 + index % 3):
                newplan['future'].append(deepcopy(rng.choice(future)))
        elif mode in (5, 7):
            epoch = rng.randrange(epochs)
            newspec['epochs'][epoch] = {
                'allow': spans_from_bits([rng.random() < .7 for _ in range(n)]),
                'exclude': spans_from_bits([rng.random() < .3 for _ in range(n)])}
            if mode == 7:
                row = rng.choice(newplan['future'])
                row['guard'] = spans_from_bits([rng.random() < .5 for _ in range(n)])
        else:
            for _ in range(min(2, len(newplan['future']))):
                newplan['future'].pop(rng.randrange(len(newplan['future'])))
            for _ in range(3):
                lo = rng.randrange(n+1)
                hi = rng.randrange(lo, n+1)
                step = 1 + rng.randrange(8)
                newplan['future'].append(mkrow(rng.randrange(epochs), lo, hi, step,
                    rng.randrange(step), spans_from_bits([rng.random() < .6 for _ in range(n)])))
        records.append({'id': f'update-{index:03d}', 'seed': 947000+index, 'group': label,
                        'old_declaration': spec, 'old_plan': plan,
                        'declaration': newspec, 'plan': newplan})
    return records
