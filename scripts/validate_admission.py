"""Finite local item-consumption checks; no addresses or external operations."""
from common import ROOT, bounded, finish
from collections import Counter
from io import StringIO
from update_cases import selected_cases
from pcs.admission import future_emissions, LocalConsumer
from pcs.model import Invalid
from pcs.producer import write_certificate
from pcs.update_producer import write_update
from pcs.update_checker import establish_anchor


def certificate(spec, plan):
    out = StringIO()
    write_certificate(spec, plan, out)
    return out.getvalue()


def compare_items(spec, items):
    actual = Counter()
    # Declared history is independently evaluated, not consumed again.
    for row in spec['history']:
        for counter in range(spec['n']):
            target = (spec['a'] * counter + spec['b']) % spec['n']
            if (row['lo'] <= counter < row['hi']
                and counter % row['step'] == row['residue']
                and any(lo <= target < hi for lo, hi in row['guard'])):
                actual[row['epoch'], target] += 1
    emissions = 0
    for item in items:
        actual[item.epoch, item.target] += 1
        emissions += 1
    expected = Counter()
    for epoch, policy in enumerate(spec['epochs']):
        for target in range(spec['n']):
            if (any(lo <= target < hi for lo, hi in policy['allow'])
                and not any(lo <= target < hi for lo, hi in policy['exclude'])):
                expected[epoch, target] = 1
    if actual != expected:
        raise RuntimeError('admitted item stream disagrees with pointwise policy')
    return emissions


def main():
    bounded()
    records = []
    accepted = rejected = 0
    for case in selected_cases():
        os, op = case['old_declaration'], case['old_plan']
        spec, plan = case['declaration'], case['plan']
        anchor = establish_anchor(os, op, StringIO(certificate(os, op)))
        base_items = compare_items(os, future_emissions(anchor))
        consumer = LocalConsumer(anchor)
        update = StringIO()
        write_update(os, op, spec, plan, update)
        try:
            consumer.request_update(spec, plan, StringIO(update.getvalue()))
        except Invalid:
            rejected += 1
            # A rejected update creates no new consumer capability.
            if compare_items(os, future_emissions(anchor)) != base_items:
                raise RuntimeError('rejected update changed the admitted base')
            try:
                next(consumer)
            except Invalid:
                pass
            else:
                raise RuntimeError('rejected replacement left old consumption active')
            record = {'id': case['id'], 'admitted': False, 'new_items_consumed': 0}
        else:
            accepted += 1
            record = {'id': case['id'], 'admitted': True,
                      'new_items_consumed': compare_items(spec, consumer)}
        record['base_items_consumed'] = base_items
        records.append(record)
    if (accepted, rejected) != (40, 56):
        raise RuntimeError('finite update admission inventory changed')
    finish('admission.json', {'all_checks_passed': True,
           'observation_kind': 'local_integer_item_consumption',
           'base_schedules_consumed': len(records),
           'safe_updates_consumed': accepted, 'unsafe_updates_blocked': rejected,
           'rejected_replacements_held': rejected,
           'history_observed': False, 'network_operations': 0,
           'durable_execution_claim': False, 'records': records})


if __name__ == '__main__':
    main()
