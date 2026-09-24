#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
from pathlib import Path

SOFTWARE = Path(__file__).resolve().parents[1]
PROJECT = SOFTWARE.parent
sys.path.insert(0, str(SOFTWARE))
from pcs.core import canonical_json_bytes, intervals_from_points, load_inputs, validate_declaration, validate_plan, write_certificate, write_witness


def dump(path: Path, value):
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def main():
    out = PROJECT / "examples"
    out.mkdir(exist_ok=True)
    n, a, b = 64, 5, 7
    safe_fragments = [
        {"id":"f000","phase":"committed","lo":0,"hi":64,"stride":4,"residue":0},
        {"id":"f001","phase":"planned","lo":0,"hi":64,"stride":4,"residue":2},
    ]
    points = []
    for f in safe_fragments:
        points.extend((a*x+b)%n for x in range(f["lo"],f["hi"]) if x%f["stride"]==f["residue"])
    declaration = {"schema":"pcs-declaration-v2","universe":n,"permutation":{"kind":"affine","multiplier":a,"offset":b},"authorized":intervals_from_points(points,n)}
    safe_plan = {"schema":"pcs-plan-v2","fragments":safe_fragments}
    missing_plan = {"schema":"pcs-plan-v2","fragments":safe_fragments[:-1]}
    duplicate_plan = {"schema":"pcs-plan-v2","fragments":[*safe_fragments,{"id":"f999","phase":"planned","lo":0,"hi":64,"stride":4,"residue":0}]}
    forbidden_plan = {"schema":"pcs-plan-v2","fragments":[*safe_fragments,{"id":"f999","phase":"planned","lo":0,"hi":64,"stride":4,"residue":1}]}
    dump(out/"declaration.json",declaration)
    for name, plan in [("safe-plan",safe_plan),("missing-plan",missing_plan),("duplicate-plan",duplicate_plan),("forbidden-plan",forbidden_plan)]:
        path=out/f"{name}.json"; dump(path,plan)
        d,p=load_inputs(out/"declaration.json",path)
        write_certificate(out/f"{name}-certificate.jsonl",d,p)
        if name!="safe-plan": write_witness(out/f"{name}-witness.json",d,p)

if __name__=="__main__": main()
