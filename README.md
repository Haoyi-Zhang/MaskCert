# Mask-Aware Certificates for Affine Schedule Fragments

Project key: `mask-aware-certificates-for-permutation-complete-stateless-scan-plans`

This repository accompanies the research manuscript and its Artifact Protocol.
It contains full certificates, safe-anchor updates, exact
Boolean encodings, finite validation, preserved original observations, and new
matched-input experiments.
The broad originating sharding brief was scientifically narrowed to this same
guarded affine model; the incompatible pcs-v2 replacement is not included.

Default science is self-contained and standard-library-only. It does not require
the paper directory, a network connection, GPU, account, private cache, LLM API,
scanner, target host, or external compute. The optional native SMT route uses
an explicitly selected platform-compatible upstream Z3 library and is a trusted decision baseline,
not a certified model counter. The historical bundled Linux library is not used
on Windows; the current Windows run used `z3-solver` 5.1.0.0 `libz3.dll`.
No CPOG/d4/VeriPB/CakePB pipeline was run.

## Current measurement set

`results/windows-2026-10-06/` is the single current directory for the completed
64-command Windows campaign: one 48-query finite native SMT suite, 20 update
benchmarks, three transfer cases and 40 full/reduced SMT configurations. All
64 actual command exits are 0, with logs retained. This is separate from plan
safety and solver completion: split/remove/revoke defects are
0/44,738,560/1,024, and timed full SMT has five timeout UNKNOWN samples.
See that directory's README and `platform.json` for the exact platform, solver
version, CPU-resolution limits, input/formula locations and scientific results.
All original `results/update-bench/`, `results/transfer/` and `results/smt/`
observations remain historical Linux measurements, not Windows results.
Current paper extension tables and fragment/edit plot data use the Windows set.

## What the checker establishes

For an independently supplied declaration, fixed affine permutation, interval
policy, declared history, and guarded modular fragments, the checker verifies
exact-once coverage of **(retry epoch, target)** and zero undesired occurrences.
For authorized targets the local penalty is `(m-1)^2`; for unauthorized targets
it is the linear multiplicity `m`, not `m^2`. History is trusted declaration
input, not observed execution. A target may be reused in a different epoch.

The diagnostic checker verifies the least fault in lexicographic
`(epoch,counter)` order using a full certificate and certificates immediately
before and through the candidate counter. The retained N=64 example therefore
has `(counter=2,target=17)`, not the minimum-target pair `(50,1)`; its defect at
prefix 50 is 12.

The producer and checker do not share interval-intersection, CRT, floor-sum, or
transcript arithmetic. The producer uses two-pointer intersections, modular
inversion, and its own recurrence. The checker uses an endpoint sweep, extended
Euclidean congruence composition, and verifies every quotient/remainder triple.
They deliberately share the strict parser/schema/limit module, the Python
interpreter, and arbitrary-precision integer semantics. The explicit oracles
are validation-only dependencies and are imported by neither producer nor
checker. This is implementation separation, not independent-team development
or machine-checked noninterference.

## What the update adds

A FULL verified safe old plan has multiplicity equal to its old policy indicator.
The update theorem substitutes that invariant into the new, linear-forbidden
defect and eliminates every unchanged-row counting query. With r removed and
s added future occurrences, it needs O(1+r+s+s^2+sr) masked count terms, rather
than all old/new row pairs. Input parsing, matching and anchor storage still
scale with the full input. The old and new policies may differ; affine context,
epoch count/order and trusted history may not change.

An immutable in-process SafeAnchor is obtained by checking the old full
certificate. It is not a serialized authentication token. Unsafe or prefix-only
bases cannot establish it. Cold CLI invocations recheck the old base every time;
a warm API call explicitly reuses a checked base. A large edit can be slower
and larger than a full certificate. Neither cache reuse nor polynomial delta
algebra is claimed as a new general principle.

## Non-overwriting scientific reproduction

Python 3.10+ on Linux is required for the measured resource controls. Assertions
are part of validation: do not use `python -O`. From this repository root:

```sh
python scripts/reproduce.py
```

For a scoped Windows finite recheck, run from the complete project root:

```sh
python repair-2026-10-06/run_local_checks.py
```

This route stages all fresh outputs and CLI temporary files below that repair
directory, records the actual host, and applies a 120-second outer wall bound
per child. It does not apply POSIX CPU, memory, alarm or affinity limits and
does not measure peak RSS. It does not load the received Linux Z3 library,
install dependencies, contact a network, compile the paper, or rerun timing
sweeps/native SMT. The Linux driver and archived observations remain separate.
The repaired inherited validator adds 909 actual prefix-transcript checks;
the archived 909 prefix comparisons used producer/counter-oracle defects.
Additional checks in `scripts/finite_repair_checks.py` cover 40 prefix CNFs
on domains 3, 5 and 9 (7,168 assignments), 80 finite progression cases at
integer widths up to a 32-bit domain, nonfinite JSON overflow rejection, and
200 selected maximum-row boundary assignments. These are not new operational
workloads or proof-assistant verification. Original result files are unchanged.

The default rechecks the frozen evidence and measurement summaries, original
arithmetic/oracles/large certificate, new 96-case updates, Boolean semantics,
public CLI and anchor contracts. Each scientific child is restricted to one
affinity CPU, 2,500 MiB of virtual address space, a 115-second alarm and
110/115-second CPU limits. The parent applies an additional 120-second wall
limit to the entire child process group. Children run sequentially. The total
campaign, containing many children, is not promised to finish in 120 seconds.

For fresh repetitions of all new measured comparisons:

```sh
python scripts/reproduce.py --full --report ../mask-aware-recheck.json
```

`--benchmarks` selects the 20 six-path timing inputs and three original-input
transfer cases; `--smt` selects the 48 finite native decisions and 40 timed native
solver configurations. `--full` selects both. These optional runs take several
minutes on the archived environment. The report path must be new and outside
this source extraction. A `--quick` option skips original boundary regeneration
and is explicitly not a complete core rerun.

All driver writes take place in a private temporary copy. It compares exact
inputs, transcripts and semantic fields, not wall/CPU/RSS values or a required
speedup. Fresh timeout rates are observations, not required to equal the old
rate. The source extraction is internally checked for non-mutation. Random
temporary-directory text in an OSError is normalized only during result
comparison; errno, filename and the remainder of the error must still agree.

To retain actual child standard output and standard error, including a failed
or timed-out child, add `--raw-output ../mask-aware-raw` with a new directory
outside the repository. The default also executes `finite_repair_checks.py`.
That suite includes 1,152 direct mixed-modulus intersection comparisons on
short owned windows, including the `2^32` endpoint and moduli 61--64; these
do not enumerate the large counter domain.

The prepared `scientific-checks.yml` runs this standard-library-only default
from the flat artifact repository on Ubuntu 24.04 on pushes to `main`. It
retains raw streams with an always-run upload step. A 900-second whole-command
wall bound and CPU limit, 2,500-MiB address-space bound and 20-minute job limit
complement the existing per-child bounds. No timings or native solver sweeps
are requested by that workflow. Its presence is not an executed remote run.

Running individual generator/experiment scripts directly writes fresh result
files in the current working repository. Use the driver to preserve the
archived observations. Core code and all experiment scripts are inspected
source assets; no dependency installation or network retrieval is hidden in
reproduction. Paper building and figure-data export are separate optional steps.

## Public CLI contract

```sh
python pcs.py certify examples/declaration.json examples/plan.json --out certificate.jsonl
python pcs.py check examples/declaration.json examples/plan.json certificate.jsonl
python pcs.py diagnose examples/fault-declaration.json examples/fault-plan.json diagnosis
python pcs.py check-witness examples/fault-declaration.json examples/fault-plan.json diagnosis
python pcs.py audit examples/declaration.json examples/plan.json
```

Output files and diagnosis directories must not already exist. For ordinary
`check` and finite `audit`:

- exit 0: valid evidence and a safe plan;
- exit 1: valid evidence and an unsafe plan;
- exit 2: malformed, unsupported, corrupted, or unreadable input.

`certify` returns 0 when it writes a transcript, including one for an unsafe
plan; generation is not verification. `check-witness` returns 0 only for a
verified least canonical fault. Prefix certificates must be checked with the
same explicit `--prefix`; a prefix-zero certificate cannot establish full-plan
safety. `results/repair-checks.json` records subprocess tests of all three
ordinary checker outcomes.

## Update commands and warm API

The following retained cold checks are immediately runnable:

```sh
python pcs-update.py check examples/updates/declaration.json examples/updates/old-plan.json examples/updates/old-certificate.jsonl examples/updates/declaration.json examples/updates/safe-plan.json examples/updates/safe-update.jsonl
python pcs-update.py check examples/updates/declaration.json examples/updates/old-plan.json examples/updates/old-certificate.jsonl examples/updates/declaration.json examples/updates/unsafe-plan.json examples/updates/unsafe-update.jsonl
python pcs-update.py check-witness examples/updates/declaration.json examples/updates/old-plan.json examples/updates/old-certificate.jsonl examples/updates/declaration.json examples/updates/unsafe-plan.json examples/updates/witness
```

Their expected exits are respectively 0, 1 and 0. The update example omits only
counter 2, hence has full defect 1. It is a different input from the inherited
example whose prefix-50 defect is 12. Both have least counter 2, target 17.
`docs/update-protocol.md` gives generation, complete wire order, immutable
snapshots, anchor advancement, a runnable warm API, and its explicit trust
boundary. A generation command is not an independently checked safety result.

## Supported-format and oracle limits

The exact constants are centralized in `src/pcs/model.py` and documented in
`docs/format.md`:

- domain `1 <= N <= 2^32`;
- fragment modulus at most 64;
- at most 16 epochs;
- at most 128 total history-plus-future fragments;
- at most 1,024 intervals per supplied list;
- at most 8 MiB per JSON input;
- at most 64 MiB per certificate;
- at most 65,536 bytes per certificate line;
- at most 68 Euclidean triples per floor query;
- transcript integers below `2^128`;
- explicit finite oracles only for `N <= 2^20`.

The retained exact-limit benchmark uses exactly `2^20`; the boundary-plus-one
case is rejected. The symbolic checker supports larger N within the separate
format and certificate limits. Schema validity is not a guarantee that every
admitted plan has a certificate below 64 MiB or finishes within an experiment
timeout. Unsupported input is never reported as a semantic coverage fault.

## Evidence navigation

| Claim or activity | Exact evidence |
|---|---|
| Original 303 plans, 909 prefixes, 146 witnesses, 1,194 corruptions | `results/validation.json`, `results/validation-cases.json`, `docs/evidence-map.md` |
| Original 61/64-residue, 1,024-exclusion observation | `cases/boundary.json`, `results/boundary.json`, `results/boundary-certificate.jsonl` |
| Original failed attempt, measured/unknown distinction | `results/resource-failure.json`, `results/resource-accounting.json` |
| 96 new update cases, 688 prefixes, 56 witnesses, 438 actual corruptions | `cases/updates.json`, `results/updates.json` |
| New least-witness and public CLI contracts | `results/update-contract.json`, `examples/updates/` |
| 28 finite exact Boolean encodings | `cases/cnf/`, `results/boolean-validation.json` |
| Historical Linux: 20 measured cases, six paths, five calibrated batches | `cases/update-bench/`, `results/update-bench/` |
| Historical Linux: split/remove/revoke transfers of the original large input | `cases/transfer/`, `results/transfer/` |
| Historical Linux Z3 4.13.3.0: 48 finite and 40 timed native SMT configurations | `results/smt-validation.json`, `cases/smt/`, `results/smt/` |
| Current Windows Z3 5.1.0.0: all 64 commands and corresponding fresh outputs | `results/windows-2026-10-06/README.md`, `results/windows-2026-10-06/execution.json` |
| Frozen timing-statistic and transcript audit | `scripts/audit_extension.py`, `results/extension-audit.json` |
| All mathematical arguments | `proofs/arguments.md`, `proofs/safe-anchor.md`, `proofs/boolean-encoding.md` |
| Reference identities and claim-specific uses | `docs/references.json`, `docs/reference-audit.md`, `docs/closest-work.md` |
| Material claim mapping and external licensing | `claim_evidence_ledger.csv`, `external_resources.csv`, `third_party/z3/` |

Timing-resolution pilot observations and an interrupted parent-status attempt
are preserved separately under `results/update-bench-pilot/` and
`results/update-bench-attempts/`. They are not included in final medians. The
old SMT field `semantic_result_verified` means only that no incorrect SAT
answer was observed on a known safe case; it does NOT mean every decision
finished. The historical Linux audit explicitly reports 95 UNSAT/5 UNKNOWN full-route samples and
100 UNSAT reduced-route samples. Fresh runs use unambiguous separate fields.

## Scope, authorship and external use

The claim is declared epoch-target coverage, not actual scanner execution,
live authorization, history authenticity, cryptographic identity, arbitrary
permutation support, pseudorandomness, or a translation from ZMap. General
certified frameworks have stronger verification properties than this Python
checker; their end-to-end timing/proof pipelines are not measured here. The
parsimonious CNF mapping and the actual native SMT experiment are explicitly
different deliverables. The broad twelve-same-journal-paper calibration and
live TDSC portal rules have not been substantively verified.

The names, affiliations and email addresses of Haoyi Zhang and Huaijin Ran
have been human-confirmed. No corresponding-author role, institutional agreement
or submission authorization is inferred from that confirmation. Collaboration
and development provenance are documented here rather than in recovery-status
paper footnotes. Arguments, code, experiments and writing used substantive
generative-AI assistance, not language polishing alone. Mathematical proofs and
finite executable checks are not proof-assistant verification, independent
human review or a journal-acceptance guarantee.
