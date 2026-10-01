# Reproduction contract

## Full scientific recheck

From the standalone artifact root:

```sh
python scripts/reproduce.py
```

The command stages a private temporary copy, first audits the copied retained
evidence map, and then runs the pilot, validation, large-boundary, regression,
example, and repair-contract scripts sequentially. Each child session has a
120-second outer process-group timeout; the scripts also apply their declared
one-worker CPU, alarm, CPU-time, and address-space limits. The source extraction
is not an output directory.

The recheck compares timing-independent JSON fields and claim-critical files
with retained evidence. It does not overwrite the source result files and does
not relabel its timings as the original observations. Use `--report` only with
a non-existing output path. `--quick` omits the large boundary case and is not
full reproduction.

## Optional paper-side commands

The standalone artifact does not depend on `paper/`. From the full project root,
figure-data export and TeX compilation are explicit, separate actions:

```sh
python artifact/scripts/export_paper_data.py --out paper/figures
sh paper/build.sh
```

The figure exporter uses only the Python standard library. The TeX build needs
the packages listed in `paper/README.md`. Neither command is part of the clean
scientific recheck.

## Interpreting outcomes

A successful command means the documented finite checks completed under the
local bounds. It is not a proof of physical execution, external deployment,
authenticated history, journal compliance, originality, or acceptance. CPU and
RSS from a fresh recheck are new measurements and may differ from the retained
single-run observations in Table III.

The optional report path must be outside the source extraction and must not already exist.
