from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import (
    PCSValidationError, analyze, canonical_json_bytes, check_certificate,
    check_witness, load_inputs, write_certificate, write_witness,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pcs", description="Exact checker for permutation-complete stateless scan plans"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("make-certificate", "check", "make-witness", "check-witness", "analyze"):
        cmd = sub.add_parser(name)
        cmd.add_argument("declaration")
        cmd.add_argument("plan")
        if name in {"make-certificate", "check", "make-witness", "check-witness"}:
            cmd.add_argument("artifact")
        if name == "check":
            cmd.add_argument("--require-safe", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        declaration, plan = load_inputs(args.declaration, args.plan)
        if args.command == "make-certificate":
            write_certificate(args.artifact, declaration, plan)
            result = analyze(declaration, plan)
            print(json.dumps({"written": str(Path(args.artifact)), "safe": result.safe, "D": result.D}, sort_keys=True))
            return 0
        if args.command == "check":
            result = check_certificate(args.artifact, declaration, plan)
            print(json.dumps({"valid": True, "safe": result.safe, "D": result.D}, sort_keys=True))
            return 3 if args.require_safe and not result.safe else 0
        if args.command == "make-witness":
            write_witness(args.artifact, declaration, plan)
            print(json.dumps({"written": str(Path(args.artifact))}, sort_keys=True))
            return 0
        if args.command == "check-witness":
            witness = check_witness(args.artifact, declaration, plan)
            print(json.dumps({"valid": True, "category": witness["category"], "target": witness["target"]}, sort_keys=True))
            return 0
        result = analyze(declaration, plan)
        print(canonical_json_bytes({
            "B": result.B, "T": result.T, "C": result.C, "Q": result.Q,
            "D": result.D, "safe": result.safe,
        }).decode("utf-8"))
        return 0
    except (PCSValidationError, OSError, ValueError) as exc:
        print(f"pcs: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
