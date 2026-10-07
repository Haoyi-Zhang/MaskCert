"""Owned integer declarations and a direct pointwise definition; no network."""
from copy import deepcopy
from io import StringIO
from math import gcd
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from pcs import update_producer as producer
from pcs.model import Invalid
from pcs.producer import write_certificate
from pcs.update_checker import establish_anchor, check_update_witness


def spans(bits):
    out = []
    for index, yes in enumerate(bits):
        if yes:
            if out and out[-1][1] == index:
                out[-1][1] += 1
            else:
                out.append([index, index + 1])
    return out


def cases():
    for seed in range(80):
        rng = random.Random(100374000 + seed)
        n = (1, 2, 5, 9, 17)[seed % 5]
        s = dict(n=n, a=rng.choice([a for a in range(n) if gcd(a, n) == 1]),
                 b=rng.randrange(n), epochs=[], history=[])
        rows = []
        for epoch in range(1 + seed % 4):
            guard = spans([rng.choice((False, True)) for _ in range(n)])
            s['epochs'].append(dict(allow=guard, exclude=[]))
            cut = n // 2
            s['history'].append(dict(epoch=epoch, lo=0, hi=cut, step=1, residue=0, guard=deepcopy(guard)))
            rows.append(dict(epoch=epoch, lo=cut, hi=n, step=1, residue=0, guard=deepcopy(guard)))
        p = dict(context={k:s[k] for k in ('n', 'a', 'b')}, future=rows)
        t, q = deepcopy(s), deepcopy(p)
        if seed % 8 == 1:
            q['future'] = []
        elif seed % 8 == 2:
            q['future'] += deepcopy(q['future'])
        elif seed % 8 in (3, 4):
            for epoch in t['epochs']:
                epoch['allow'] = spans([rng.choice((False, True)) for _ in range(n)])
                epoch['exclude'] = spans([rng.choice((False, True)) for _ in range(n)])
        elif seed % 8 == 5:
            for row in q['future']:
                row['guard'] = spans([rng.choice((False, True)) for _ in range(n)])
                row['lo'], row['step'], row['residue'] = 0, 3, rng.randrange(3)
        elif seed % 8 == 6:
            q['future'] = list(reversed(q['future']))
        elif seed % 8 == 7:
            q['future'] += [dict(epoch=0, lo=0, hi=0, step=2, residue=1, guard=[])] * 2
        yield s, p, t, q


def definition(spec, plan, prefix=None):
    totals, first = [], None
    for e, policy in enumerate(spec['epochs']):
        total = 0
        for x in range(spec['n'] if prefix is None else prefix):
            y = (spec['a'] * x + spec['b']) % spec['n']
            wanted = any(l <= y < h for l,h in policy['allow']) and not any(l <= y < h for l,h in policy['exclude'])
            hits = [j for j,r in enumerate(spec['history'] + plan['future']) if
                    r['epoch'] == e and r['lo'] <= x < r['hi'] and x % r['step'] == r['residue'] and
                    any(l <= y < h for l,h in r['guard'])]
            local = (len(hits)-1)**2 if wanted else len(hits)
            total += local
            if local and first is None:
                kind = 'forbidden' if not wanted else ('omission' if not hits else 'collision')
                first = dict(epoch=e, counter=x, target=y, kind=kind,
                             rows=hits[:2] if kind == 'collision' else hits[:1])
        totals.append(total)
    return totals, first


class UpdateLocalizationTests(unittest.TestCase):
    def test_definition_and_unchanged_witness_verifier(self):
        for s,p,t,q in cases():
            original = deepcopy((s,p,t,q))
            witness = producer.locate_update(s,p,t,q)
            self.assertEqual(witness, definition(t,q)[1])
            base = StringIO(); write_certificate(s,p,base)
            anchor = establish_anchor(s,p,StringIO(base.getvalue()))
            if witness is not None:
                texts = []
                for prefix in (None,witness['counter'],witness['counter']+1):
                    stream = StringIO(); producer.write_update(s,p,t,q,stream,prefix)
                    self.assertEqual(producer.update_defects(s,p,t,q,prefix), definition(t,q,prefix)[0])
                    texts.append(StringIO(stream.getvalue()))
                self.assertTrue(check_update_witness(anchor,t,q,witness,*texts))
            self.assertEqual((s,p,t,q), original)

    def test_call_local_preparation_and_single_epoch_prefixes(self):
        s,p,t,q = list(cases())[2]
        with patch.object(producer,'changed_rows',wraps=producer.changed_rows) as changed:
            producer.locate_update(s,p,t,q)
            self.assertEqual(changed.call_count,1)
        if hasattr(producer, '_localization_data'):
            data = producer._localization_data(s,p,t,q)
            with self.assertRaises(TypeError):
                data[0][5][0]['hi'] = 99
            for prefix in range(t['n']+1):
                self.assertEqual([producer._localization_defect(t['n'],t['a'],t['b'],item,prefix) for item in data],
                                 definition(t,q,prefix)[0])
        q['future'].clear()
        self.assertEqual(producer.locate_update(s,p,t,q), definition(t,q)[1])

    def test_invalid_inputs_are_not_faults(self):
        s,p,t,q = next(cases())
        for mutate in (lambda x:x[2].update(n=True), lambda x:x[3]['context'].update(a=True),
                       lambda x:x[2]['history'].clear(), lambda x:x[2]['epochs'].append(dict(allow=[],exclude=[]))):
            args = deepcopy([s,p,t,q]); mutate(args)
            with self.assertRaises(Invalid):
                producer.locate_update(*args)


if __name__ == '__main__':
    unittest.main()
