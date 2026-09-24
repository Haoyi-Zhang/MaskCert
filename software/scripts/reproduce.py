#!/usr/bin/env python3
"""Offline, fail-closed reproduction driver for the complete artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "qa" / "reproduction-latest"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(name: str, cmd: list[str], *, env: dict[str, str]) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / f"{name}.log"
    start = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    elapsed = time.perf_counter() - start
    log.write_text(proc.stdout or "", encoding="utf-8")
    record = {
        "name": name,
        "command": cmd,
        "returncode": proc.returncode,
        "elapsed_seconds": round(elapsed, 6),
        "log": str(log.relative_to(ROOT)),
    }
    if proc.returncode != 0:
        raise RuntimeError(f"{name} failed with exit code {proc.returncode}; see {log}")
    return record


def required_tools(require_pdf: bool) -> dict[str, str | None]:
    tools = {
        "python": shutil.which(Path(sys.executable).name) or sys.executable,
        "pdflatex": shutil.which("pdflatex"),
        "bibtex": shutil.which("bibtex"),
        "pdfinfo": shutil.which("pdfinfo"),
        "pdftotext": shutil.which("pdftotext"),
        "pdftoppm": shutil.which("pdftoppm"),
        "pdffonts": shutil.which("pdffonts"),
    }
    missing = [k for k, v in tools.items() if k != "python" and v is None]
    if require_pdf and missing:
        raise RuntimeError("missing required PDF tools: " + ", ".join(missing))
    return tools


def key_hashes(paths: Iterable[Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in paths:
        if p.exists() and p.is_file():
            out[str(p.relative_to(ROOT))] = sha256(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-pdf-tools", action="store_true")
    ap.add_argument("--skip-benchmark", action="store_true", help="Use only retained benchmark evidence; still rerun semantic checks.")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.glob("*.log"):
        p.unlink()

    tools = required_tools(args.require_pdf_tools)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "software") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONHASHSEED"] = "0"
    commands: list[dict] = []
    started = datetime.now(timezone.utc).isoformat()
    try:
        commands.append(run("compileall", [sys.executable, "-m", "compileall", "-q", "software"], env=env))
        commands.append(run("unit-tests", [sys.executable, "-m", "unittest", "discover", "-s", "software/tests", "-p", "test_*.py", "-v"], env=env))
        commands.append(run("generate-examples", [sys.executable, "software/scripts/generate_examples.py"], env=env))
        commands.append(run("protocol-figure", [sys.executable, "software/scripts/make_protocol_figure.py"], env=env))
        if not args.skip_benchmark:
            commands.append(run("benchmark", [sys.executable, "software/scripts/benchmark.py"], env=env))
        commands.append(run("semantic-recheck-prebuild", [sys.executable, "software/scripts/semantic_recheck.py"], env=env))

        have_pdf = all(tools.get(x) for x in ("pdflatex", "bibtex", "pdfinfo", "pdftotext", "pdftoppm", "pdffonts"))
        if have_pdf:
            commands.append(run("paper-fit", [sys.executable, "paper/fit_to_12.py"], env=env))
            commands.append(run("supplement-build", ["bash", "supplement/build.sh"], env=env))
            commands.append(run("reference-audit", [sys.executable, "software/scripts/audit_references.py"], env=env))
            commands.append(run("pdf-audit", [sys.executable, "software/scripts/qa_release.py"], env=env))
        elif args.require_pdf_tools:
            raise RuntimeError("PDF tools required but unavailable")
        else:
            commands.append(run("reference-audit-offline", [sys.executable, "software/scripts/audit_references.py", "--allow-missing-bbl"], env=env))

        commands.append(run("semantic-recheck-final", [sys.executable, "software/scripts/semantic_recheck.py"], env=env))
        status = "passed"
        error = None
    except Exception as exc:
        status = "failed"
        error = str(exc)

    report = {
        "schema": "pcs-reproduction-report-v1",
        "status": status,
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "tools": tools,
        "commands": commands,
        "error": error,
        "key_output_sha256": key_hashes([
            ROOT / "paper" / "main.pdf",
            ROOT / "supplement" / "supplement.pdf",
            ROOT / "results" / "results.json",
            ROOT / "qa" / "reference-audit.json",
            ROOT / "qa" / "semantic-recheck.json",
            ROOT / "qa" / "pdf-audit.json",
        ]),
    }
    (OUT / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = [
        "# Reproduction Report",
        "",
        f"- Status: **{status}**",
        f"- Started (UTC): `{started}`",
        f"- Finished (UTC): `{report['finished_utc']}`",
        f"- Platform: `{report['platform']}`",
        "",
        "## Commands",
        "",
    ]
    for item in commands:
        md.append(f"- `{item['name']}`: exit {item['returncode']}, {item['elapsed_seconds']:.3f} s; log `{item['log']}`")
    if error:
        md.extend(["", "## Failure", "", f"`{error}`"])
    md.extend(["", "## Key output SHA-256", ""])
    for path, digest in report["key_output_sha256"].items():
        md.append(f"- `{path}`: `{digest}`")
    (OUT / "REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    if status != "passed":
        print(error, file=sys.stderr)
        return 1
    print("Reproduction passed. See qa/reproduction-latest/REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
