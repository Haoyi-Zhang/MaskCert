#!/usr/bin/env python3
"""Cold, bounded-input CLI. Every invocation verifies the full base certificate.
For explicitly warm sessions use pcs.update_checker.SafeAnchor through the API.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from pcs.model import Invalid, load, certificate_lines
from pcs.update_checker import establish_anchor, verify_update, check_update_witness
from pcs.update_producer import write_update, locate_update


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('certify', 'check', 'diagnose', 'check-witness'):
        sub = commands.add_parser(name)
        for arg in ('old_declaration', 'old_plan', 'old_certificate', 'declaration', 'plan'):
            sub.add_argument(arg, type=Path)
        if name == 'certify':
            sub.add_argument('--out', required=True, type=Path)
            sub.add_argument('--prefix', type=int)
        elif name == 'check':
            sub.add_argument('certificate', type=Path)
            sub.add_argument('--prefix', type=int)
        else:
            sub.add_argument('bundle', type=Path)
    args = parser.parse_args(argv)
    made = []
    bundle_created = False
    try:
        old_spec, old_plan = load(args.old_declaration), load(args.old_plan)
        spec, plan = load(args.declaration), load(args.plan)
        anchor = establish_anchor(old_spec, old_plan, certificate_lines(args.old_certificate))
        def produce(path, prefix=None):
            with path.open('x', encoding='utf-8', newline='\n') as stream:
                made.append(path)
                return write_update(old_spec, old_plan, spec, plan, stream, prefix)
        if args.command == 'certify':
            ds = produce(args.out, args.prefix)
            output, code = {'created': True, 'producer_defects': ds}, 0
        elif args.command == 'check':
            checked = verify_update(anchor, spec, plan, certificate_lines(args.certificate), args.prefix)
            output = {'verified': True, 'base_reverified_in_this_call': True, **asdict(checked)}
            code = 0 if checked.accepted else 1
        elif args.command == 'diagnose':
            witness = locate_update(old_spec, old_plan, spec, plan)
            if witness is None:
                output = {'producer_witness': None, 'bundle_created': False}
            else:
                args.bundle.mkdir(exist_ok=False)
                bundle_created = True
                produce(args.bundle / 'full.jsonl')
                produce(args.bundle / 'before.jsonl', witness['counter'])
                produce(args.bundle / 'through.jsonl', witness['counter'] + 1)
                path = args.bundle / 'witness.json'
                with path.open('x', encoding='utf-8') as stream:
                    made.append(path)
                    json.dump(witness, stream, indent=2)
                    stream.write('\n')
                output = {'producer_witness': witness, 'bundle_created': True}
            code = 0
        else:
            witness = load(args.bundle / 'witness.json')
            check_update_witness(anchor, spec, plan, witness,
                                 certificate_lines(args.bundle / 'full.jsonl'),
                                 certificate_lines(args.bundle / 'before.jsonl'),
                                 certificate_lines(args.bundle / 'through.jsonl'))
            output, code = {'verified': True, 'least_canonical_witness': witness}, 0
        print(json.dumps(output, sort_keys=True))
        return code
    except (Invalid, OSError, UnicodeError) as error:
        for path in made:
            path.unlink(missing_ok=True)
        if bundle_created:
            args.bundle.rmdir()
        print(json.dumps({'verified': False, 'error': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
