# Reproducibility

## Supported environment

The executable checker requires Python 3.10 or newer and the standard library only. The retained release was tested on the environment recorded in `results/results.json`. Timing values are observational; integer verdicts and canonical artifacts are exact.

## One-command rerun

```bash
python software/scripts/reproduce.py
```

The script performs these gates in order:

1. strict unit and differential tests;
2. deterministic regeneration and verification of all example certificates and witnesses;
3. semantic reconstruction of every retained scaling case;
4. offline validation of frozen Crossref metadata and bibliography uniqueness;
5. main-paper and supplement compilation when TeX tools are present;
6. page-count, unresolved-reference, log, text, raster, and margin checks;
7. a machine-readable report under `qa/reproduction-latest/`.

Use `--require-pdf-tools` in a release environment so missing TeX/PDF utilities are a failure rather than a documented skip.

## Full timing rerun

```bash
PYTHONPATH=software python software/scripts/benchmark.py
```

This overwrites retained timing files and generated paper result macros. Timings will vary. After a timing rerun, rebuild the paper and rerun QA. Release reviewers who only need to verify semantics should use `reproduce.py`, which does not require timing equality.

## Online reference refresh

The release includes frozen raw Crossref responses, so ordinary reproduction is offline. To refresh bibliographic metadata:

```bash
python software/scripts/fetch_references.py
```

The refresh is a release-maintainer action: it requires network access, rejects candidates that do not return an exact DOI match with author/title/year, and may change formatting if Crossref metadata changes. The report never treats an unavailable network as a successful online verification.

## Exact versus observational outputs

Exact and compared for equality:

- schema acceptance/rejection;
- `B`, `T`, `C`, `Q`, `D`, and safe/unsafe verdicts;
- certificate row count, ordering, values, and hash chain;
- input SHA-256 digests;
- canonical earliest witness fields;
- bibliography key and DOI uniqueness;
- main-paper page count and citation resolution.

Recorded but not expected to be identical across machines:

- wall-clock times;
- process scheduling effects;
- `tracemalloc` peaks across Python versions;
- compressed ZIP byte sequence when the compressor or timestamps differ.

## Independent oracle

`software/pcs/core.py::explicit_defect` enumerates source counters, materializes target multiplicities, and directly evaluates target-wise squares. It does not call floor-sum, CRT intersection, aggregate analysis, certificate, or witness routines. Randomized tests compare this oracle with optimized analysis for 1,000 seeded complete plans.

## Clean-room release check

The release builder extracts the public artifact ZIP into a fresh temporary directory, rejects unsafe archive paths, runs `reproduce.py --require-pdf-tools`, and records stdout, stderr, exit status, and generated report hashes. See `qa/CLEAN-ROOM.md` and `qa/final-audit.json`.
