#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import platform
import re
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

SOFTWARE = Path(__file__).resolve().parents[1]
PROJECT = SOFTWARE.parent
sys.path.insert(0, str(SOFTWARE))

from pcs.core import (
    analyze, canonical_json_bytes, canonical_witness, check_certificate,
    explicit_defect, intervals_from_points, validate_declaration, validate_plan,
    write_certificate,
)


def make_sparse_safe(universe: int, fragment_count: int, point_count: int):
    if point_count < fragment_count:
        raise ValueError("point_count must be >= fragment_count")
    # Odd multipliers are invertible modulo powers of two.
    multiplier = 0x9E3779B1 % universe
    if multiplier == 0:
        multiplier = 1
    while __import__("math").gcd(multiplier, universe) != 1:
        multiplier = (multiplier + 2) % universe
        if multiplier == 0:
            multiplier = 1
    offset = 0x7F4A7C15 % universe
    gap = universe // fragment_count
    fragments = []
    sources = []
    base, extra = divmod(point_count, fragment_count)
    for idx in range(fragment_count):
        count = base + (1 if idx < extra else 0)
        lo = idx * gap
        hi = lo + count
        if hi > (idx + 1) * gap or hi > universe:
            raise ValueError("case does not fit disjoint blocks")
        fragments.append({
            "id": f"f{idx:04d}",
            "phase": "committed" if idx < fragment_count // 3 else "planned",
            "lo": lo, "hi": hi, "stride": 1, "residue": 0,
        })
        sources.extend(range(lo, hi))
    targets = [(multiplier * x + offset) % universe for x in sources]
    declaration_raw = {
        "schema": "pcs-declaration-v2",
        "universe": universe,
        "permutation": {"kind": "affine", "multiplier": multiplier, "offset": offset},
        "authorized": intervals_from_points(targets, universe),
    }
    plan_raw = {"schema": "pcs-plan-v2", "fragments": fragments}
    declaration = validate_declaration(declaration_raw)
    plan = validate_plan(plan_raw, declaration)
    return declaration, plan


def sample(callable_, repeats=5):
    values = []
    result = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        result = callable_()
        values.append((time.perf_counter_ns() - start) / 1e9)
    return result, values


def stats(values):
    ordered = sorted(values)
    return {
        "repeats": len(values),
        "raw_seconds": values,
        "median_seconds": statistics.median(values),
        "min_seconds": min(values),
        "max_seconds": max(values),
        "q1_seconds": statistics.median(ordered[: max(1, len(ordered)//2)]),
        "q3_seconds": statistics.median(ordered[(len(ordered)+1)//2 :]) if len(ordered) > 1 else ordered[0],
    }


def peak_memory(callable_):
    tracemalloc.start()
    result = callable_()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, peak


def main():
    results_dir = PROJECT / "results"
    raw_dir = results_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cert_dir = results_dir / "certificates"
    cert_dir.mkdir(parents=True, exist_ok=True)

    scaling_specs = [
        (20, 16, 128),
        (24, 32, 256),
        (28, 64, 512),
        (32, 125, 1024),
        (36, 192, 1536),
        (40, 256, 2048),
    ]
    scaling = []
    for exp, fragment_count, point_count in scaling_specs:
        universe = 1 << exp
        d, p = make_sparse_safe(universe, fragment_count, point_count)
        result, generation_times = sample(lambda: analyze(d, p), repeats=5)
        assert result.safe and result.D == 0
        case_dir = raw_dir / f"case-n2-{exp}-f-{fragment_count}-m-{point_count}"
        case_dir.mkdir(exist_ok=True)
        (case_dir / "declaration.json").write_bytes(canonical_json_bytes(d.raw) + b"\n")
        (case_dir / "plan.json").write_bytes(canonical_json_bytes(p.raw) + b"\n")
        certificate = cert_dir / f"n2-{exp}-f-{fragment_count}-m-{point_count}.jsonl"
        _, certificate_times = sample(lambda: write_certificate(certificate, d, p), repeats=5)
        checked, verify_times = sample(lambda: check_certificate(certificate, d, p), repeats=5)
        assert checked.safe
        _, peak = peak_memory(lambda: check_certificate(certificate, d, p))
        row = {
            "universe_exponent": exp,
            "universe": universe,
            "fragment_count": fragment_count,
            "authorized_interval_count": len(d.authorized),
            "authorized_target_count": d.authorized_size,
            "pair_count": fragment_count * (fragment_count - 1) // 2,
            "certificate_rows": fragment_count * (fragment_count - 1) // 2 + fragment_count + 2,
            "certificate_bytes": certificate.stat().st_size,
            "peak_verify_bytes_tracemalloc": peak,
            "analysis": stats(generation_times),
            "certificate_generation": stats(certificate_times),
            "certificate_verification": stats(verify_times),
            "B": result.B, "T": result.T, "C": result.C, "Q": result.Q, "D": result.D,
        }
        scaling.append(row)

    # Domain-size experiment holds the structural work constant.
    domain = []
    for exp in (20, 24, 28, 32, 36, 40, 44, 48):
        d, p = make_sparse_safe(1 << exp, 64, 512)
        result, times = sample(lambda: analyze(d, p), repeats=7)
        assert result.safe
        domain.append({"universe_exponent": exp, "universe": 1 << exp, **stats(times)})

    # Independent enumeration baseline.  The exact method and explicit oracle
    # do not share counting code.
    baseline = []
    for exp in (12, 14, 16, 18, 20):
        d, p = make_sparse_safe(1 << exp, 32, 256)
        fast, fast_times = sample(lambda: analyze(d, p), repeats=5)
        slow, slow_times = sample(lambda: explicit_defect(d, p), repeats=3)
        assert fast.D == slow == 0
        baseline.append({
            "universe_exponent": exp, "universe": 1 << exp,
            "exact": stats(fast_times), "enumeration": stats(slow_times),
            "median_speedup": statistics.median(slow_times) / statistics.median(fast_times),
        })

    # Canonical earliest witness on a large unsafe variant.
    d, p = make_sparse_safe(1 << 32, 125, 1024)
    unsafe_raw = json.loads(json.dumps(p.raw))
    first = unsafe_raw["fragments"][0]
    unsafe_raw["fragments"].append({**first, "id": "f9999", "phase": "planned"})
    unsafe = validate_plan(unsafe_raw, d)
    witness, witness_times = sample(lambda: canonical_witness(d, unsafe), repeats=5)
    assert witness["category"] == "duplicate"

    unit_text = (raw_dir / "unit-tests.txt").read_text(encoding="utf-8") if (raw_dir / "unit-tests.txt").exists() else ""
    match = re.search(r"Ran (\d+) tests? in ([0-9.]+)s", unit_text)
    unit_summary = {
        "reported_test_count": int(match.group(1)) if match else None,
        "reported_seconds": float(match.group(2)) if match else None,
        "status_ok": "\nOK\n" in "\n" + unit_text,
    }
    if not unit_summary["status_ok"]:
        raise RuntimeError("unit-test transcript does not end in OK")

    document = {
        "schema": "pcs-experiment-results-v2",
        "measurement_note": "Wall-clock observations are environment-specific; verdict fields use exact integers.",
        "environment": {
            "python": sys.version,
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "unit_tests": unit_summary,
        "scaling": scaling,
        "domain_size": domain,
        "enumeration_baseline": baseline,
        "large_witness": {"witness": witness, "timing": stats(witness_times)},
    }
    (results_dir / "results.json").write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with (results_dir / "scaling.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["log2_N", "fragments", "mask_intervals", "pairs", "certificate_bytes", "analysis_median_s", "verify_median_s", "peak_verify_bytes"])
        for row in scaling:
            writer.writerow([
                row["universe_exponent"], row["fragment_count"], row["authorized_interval_count"],
                row["pair_count"], row["certificate_bytes"], row["analysis"]["median_seconds"],
                row["certificate_verification"]["median_seconds"], row["peak_verify_bytes_tracemalloc"],
            ])
    with (results_dir / "domain.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["log2_N", "median_seconds", "min_seconds", "max_seconds"])
        for row in domain:
            writer.writerow([row["universe_exponent"], row["median_seconds"], row["min_seconds"], row["max_seconds"]])
    with (results_dir / "baseline.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["log2_N", "exact_median_seconds", "enumeration_median_seconds", "median_speedup"])
        for row in baseline:
            writer.writerow([row["universe_exponent"], row["exact"]["median_seconds"], row["enumeration"]["median_seconds"], row["median_speedup"]])

    largest = next(row for row in scaling if row["universe_exponent"] == 32 and row["fragment_count"] == 125)
    macros = {
        "UnitTestCount": unit_summary["reported_test_count"],
        "LargeUniverse": largest["universe"],
        "LargeFragments": largest["fragment_count"],
        "LargeMaskIntervals": largest["authorized_interval_count"],
        "LargePairs": largest["pair_count"],
        "LargeCertificateRows": largest["certificate_rows"],
        "LargeCertificateBytes": largest["certificate_bytes"],
        "LargeCertificateMiB": f"{largest['certificate_bytes']/2**20:.3f}",
        "LargeAnalysisSeconds": f"{largest['analysis']['median_seconds']:.6f}",
        "LargeVerifySeconds": f"{largest['certificate_verification']['median_seconds']:.6f}",
        "LargePeakMiB": f"{largest['peak_verify_bytes_tracemalloc']/2**20:.3f}",
        "LargeWitnessSeconds": f"{statistics.median(witness_times):.6f}",
        "BaselineLargestSpeedup": f"{baseline[-1]['median_speedup']:.1f}",
    }
    with (PROJECT / "paper" / "results-macros.tex").open("w", encoding="utf-8") as handle:
        handle.write("% Generated by software/scripts/benchmark.py; do not edit.\n")
        for key, value in macros.items():
            handle.write(f"\\newcommand{{\\{key}}}{{{value}}}\n")

    # TeX rows generated from the retained JSON, avoiding hand transcription.
    with (PROJECT / "paper" / "scaling-rows.tex").open("w", encoding="utf-8") as handle:
        for row in scaling:
            line = (
                f"$2^{{{row['universe_exponent']}}}$ & {row['fragment_count']} & {row['authorized_interval_count']} & "
                f"{row['pair_count']} & {row['certificate_bytes']/2**20:.2f} & "
                f"{row['analysis']['median_seconds']:.4f} & {row['certificate_verification']['median_seconds']:.4f} "
            )
            handle.write(line + "\\\\" + "\n")
    with (PROJECT / "paper" / "baseline-rows.tex").open("w", encoding="utf-8") as handle:
        for row in baseline:
            line = (
                f"$2^{{{row['universe_exponent']}}}$ & {row['exact']['median_seconds']:.5f} & "
                f"{row['enumeration']['median_seconds']:.5f} & {row['median_speedup']:.1f}$\\times$ "
            )
            handle.write(line + "\\\\" + "\n")

    # Plots use the CSV/JSON just written.  Grayscale and vector PDF keep the
    # submission legible when printed.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figdir = PROJECT / "paper" / "figures"
    figdir.mkdir(exist_ok=True)
    plt.figure(figsize=(3.35, 2.25))
    plt.plot([r["fragment_count"] for r in scaling], [r["analysis"]["median_seconds"] for r in scaling], marker="o", label="analysis")
    plt.plot([r["fragment_count"] for r in scaling], [r["certificate_verification"]["median_seconds"] for r in scaling], marker="s", linestyle="--", label="verification")
    plt.xlabel("Fragments")
    plt.ylabel("Median wall time (s)")
    plt.grid(True, linewidth=0.3)
    plt.legend(frameon=False, fontsize=7)
    plt.tight_layout()
    plt.savefig(figdir / "scaling.pdf")
    plt.close()

    plt.figure(figsize=(3.35, 2.25))
    plt.semilogy([r["universe"] for r in baseline], [r["exact"]["median_seconds"] for r in baseline], marker="o", label="certificate arithmetic")
    plt.semilogy([r["universe"] for r in baseline], [r["enumeration"]["median_seconds"] for r in baseline], marker="s", linestyle="--", label="explicit oracle")
    plt.xlabel("Universe size $N$")
    plt.ylabel("Median wall time (s, log scale)")
    plt.grid(True, linewidth=0.3)
    plt.legend(frameon=False, fontsize=7)
    plt.tight_layout()
    plt.savefig(figdir / "baseline.pdf")
    plt.close()

    print(json.dumps({"status": "ok", "results": str(results_dir / "results.json"), "large_case": largest}, sort_keys=True))

if __name__ == "__main__":
    main()
