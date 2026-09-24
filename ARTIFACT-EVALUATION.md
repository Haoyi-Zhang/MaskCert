# Artifact Evaluation Guide

## One-command reproduction

```bash
python software/scripts/reproduce.py --require-pdf-tools
```

The driver is offline and fail-closed. It compiles Python sources, runs all tests, regenerates examples and figures, reruns the deterministic benchmark, independently rechecks retained semantic values, rebuilds the 12-page paper and supplement, audits every rendered reference against retained metadata, and performs PDF structural and raster checks.

## Faster semantic-only check

```bash
python software/scripts/reproduce.py --skip-benchmark
```

This mode still checks all retained benchmark semantics but does not repeat timing measurements. It is not the release-qualification command.

## Direct certificate checks

```bash
python software/pcs.py check examples/safe-declaration.json examples/safe-plan.json examples/safe-certificate.jsonl
python software/pcs.py check-witness examples/duplicate-declaration.json examples/duplicate-plan.json examples/duplicate-witness.json
```

## Expected outputs

- `qa/reproduction-latest/report.json` and `REPORT.md`
- `qa/reference-audit.json`
- `qa/semantic-recheck.json`
- `qa/pdf-audit.json`
- rebuilt `paper/main.pdf` and `supplement/supplement.pdf`

All measurements should be interpreted as observations on the recorded host, not universal performance guarantees.
