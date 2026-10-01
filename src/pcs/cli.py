"""CLI with explicit malformed/unsafe distinction and exclusive output creation."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from pathlib import Path
import json
import sys
from .model import Invalid, load, certificate_lines, validate
from .producer import write_certificate, locate
from .checker import verify, check_witness
from .oracle import enumerate_counters, replay_audit


def _write_certificate(path: Path, spec: dict, plan: dict, prefix=None):
    created = False
    try:
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            created = True
            return write_certificate(spec, plan, stream, prefix)
    except BaseException:
        if created:
            path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('certify', 'check', 'diagnose', 'check-witness', 'audit'):
        sub = commands.add_parser(command)
        sub.add_argument('declaration', type=Path)
        sub.add_argument('plan', type=Path)
        if command == 'certify':
            sub.add_argument('--out', required=True, type=Path)
            sub.add_argument('--prefix', type=int)
        elif command == 'check':
            sub.add_argument('certificate', type=Path)
            sub.add_argument('--prefix', type=int)
        elif command in ('diagnose', 'check-witness'):
            sub.add_argument('bundle', type=Path)
    args = parser.parse_args(argv)
    try:
        spec, plan = load(args.declaration), load(args.plan)
        validate(spec, plan)
        if args.command == 'certify':
            defects = _write_certificate(args.out, spec, plan, args.prefix)
            result = {'certificate_created': True, 'producer_defects': defects}
            code = 0  # generation is not an independent verification result
        elif args.command == 'check':
            checked = verify(spec, plan, certificate_lines(args.certificate), args.prefix)
            result = dict(verified=True, **asdict(checked))
            code = 0 if checked.accepted else 1
        elif args.command == 'diagnose':
            witness = locate(spec, plan)
            if witness is None:
                result = {'producer_defects': 'none', 'bundle_created': False}
            else:
                args.bundle.mkdir(parents=False, exist_ok=False)
                created = []
                try:
                    for filename, prefix in (
                        ('full.jsonl', None), ('before.jsonl', witness['counter']),
                        ('through.jsonl', witness['counter'] + 1)):
                        path = args.bundle / filename
                        _write_certificate(path, spec, plan, prefix)
                        created.append(path)
                    path = args.bundle / 'witness.json'
                    with path.open('x', encoding='utf-8') as out:
                        created.append(path)
                        json.dump(witness, out, indent=2)
                        out.write('\n')
                except BaseException:
                    for path in created:
                        path.unlink(missing_ok=True)
                    args.bundle.rmdir()
                    raise
                result = {'bundle_created': True, 'producer_witness': witness}
            code = 0
        elif args.command == 'check-witness':
            witness = load(args.bundle / 'witness.json')
            check_witness(spec, plan, witness,
                          certificate_lines(args.bundle / 'full.jsonl'),
                          certificate_lines(args.bundle / 'before.jsonl'),
                          certificate_lines(args.bundle / 'through.jsonl'))
            result = {'verified': True, 'least_canonical_witness': witness}
            code = 0
        else:
            exact, witness = enumerate_counters(spec, plan)
            replay = replay_audit(spec, plan)
            if exact != replay:
                raise Invalid('finite oracle disagreement')
            result = {'finite_oracles_agree': True, 'defects': exact,
                      'least_canonical_witness': witness}
            code = 0 if not any(exact) else 1
        print(json.dumps(result, sort_keys=True))
        return code
    except (Invalid, OSError, UnicodeError) as error:
        print(json.dumps({'verified': False, 'error': str(error)}), file=sys.stderr)
        return 2
