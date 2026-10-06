# Reproduction contract

## Core and extension correctness

From the standalone artifact root, with ordinary Python (not `python -O`):

```sh
python scripts/reproduce.py
```

This is the default correctness recheck, not a fresh rerun of all timing batches.
It stages a private temporary copy and audits both the frozen original evidence
and the extension evidence before any new measurements are written in that copy.
It then reruns the original pilot, 303-plan validation, large boundary, regression,
examples and repair contract, followed by safe-anchor updates, public update
contracts, exact Boolean encodings and update examples. It compares exact inputs,
certificates and timing-independent scientific fields. No source result file is
an output destination, and no new time or RSS is relabeled as an old observation.

The current implementation has these explicit additional modes:

```sh
python scripts/reproduce.py --benchmarks
python scripts/reproduce.py --smt
python scripts/reproduce.py --full
```

`--benchmarks` additionally reruns all twenty six-path batched inputs and the
three original-large-input transfer experiments. `--smt` additionally runs the
48 finite native-solver comparisons and forty full/reduced SMT timing
configurations. `--full` combines both additions. The archived Linux SMT route
uses the included unmodified Linux x86-64 Z3 shared library, with its MIT notices;
it is not a standard-library-only or platform-independent route. The default
correctness path does not load that library. SMT results are trusted solver
decisions, not certified model counts. UNKNOWN is retained as unfinished, not
accepted as a safe decision; fresh timing outcomes need not have the same
UNKNOWN count or performance ordering as the frozen measurements.

Each archived Linux science child starts a new process group, is restricted to one affinity
CPU and 2,500 MiB of address space, and receives a 115-second alarm and
110/115-second soft/hard CPU limits. The driver enforces a 120-second outer
wall timeout and kills the whole process group if it expires. Children run
sequentially. The enclosing full campaign can therefore take several minutes;
120 seconds is a per-child limit, not the whole campaign duration.

The separate completed Windows campaign is retained in
`results/windows-2026-10-06/`, not at these historical Linux result paths.
It consists of 64 real successful experiment commands, with 48 finite native
SMT decisions, twenty update benchmarks, three transfers and forty timed SMT
configurations. Its explicitly selected Windows DLL reports Z3 5.1.0.0;
the Linux baseline reports 4.13.3.0. Windows applies the 120-second parent
wall bound but none of the POSIX controls above and does not measure peak RSS.
The current directory's README records timing-resolution limits and the
distinction between exit 0, a safe plan, and a completed solver decision.
This campaign does not extend the Linux reproduction driver to Windows.

For a durable report, supply a new path outside the source extraction:

```sh
python scripts/reproduce.py --full --report /tmp/mask-aware-clean-report.json
```

An existing report is refused. `--quick` omits the large boundary case and is
explicitly incomplete. Assertion-based scientific tests require non-optimized
Python; the public checker performs explicit input/transcript checks.

## Optional paper-side commands

The artifact does not depend on `paper/`. From the complete project root:

```sh
python artifact/scripts/export_paper_data.py --out paper/figures
python artifact/scripts/export_extension_data.py --results artifact/results/windows-2026-10-06 --output paper/generated
sh paper/build.sh
python artifact/scripts/audit_paper.py --paper paper --out paper/reference-use-audit.json
```

Both exporters use only the Python standard library. TeX packages are listed in
`paper/README.md`. Compilation and figure export are separate from the science
recheck. The coordinator's pre-integration compilation has thirteen main pages
and five protocol pages. The package PDFs remain preserved older twelve/five-page
snapshots; this experiment-integration revision has not been compiled. The old
six/two description refers only to the recovered scientific basis. Current
extension tables and fragment/edit plot data use the explicitly selected Windows
directory; omitting `--results` retains the historical Linux export.

## Interpreting outcomes

A successful recheck establishes that the named finite obligations and file
comparisons completed under the measured limits. It does not establish physical
execution, authenticated history, an external workload distribution, a formally
verified checker, publication approval, acceptance or unique originality.
CPOG/d4 and VeriPB/CakePB upstream certified-counting pipelines were not executed.
The exact Boolean encoding and native SMT route do not close that empirical
comparison. Original single-run timings, new frozen timings and fresh recheck
timings remain distinct evidence groups.
