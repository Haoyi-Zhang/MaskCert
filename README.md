# Mask-Aware Certificates for Affine Schedule Fragments

Exact certificates for declared epoch–target coverage in guarded affine
schedules. The artifact includes a producer, a separately implemented arithmetic
checker, explicit finite oracles, safe-anchor updates, least-fault witnesses,
Boolean encodings, and a local fixed-record consumer. It is standalone: the
scientific checks need no sibling paper, network, account or private data.

## Setup

Use Python 3.10 or later. The core and portable tests use only the standard
library; no package installation is needed. The complete reproduction driver
requires Linux/POSIX resource controls. Windows supports the portable tests
and public checker commands below.

The optional native SMT baseline needs a compatible upstream Z3 library.
Retained Linux observations use Z3 4.13.3.0; the separate Windows native campaign
used the upstream 5.1.0.0 DLL. The frozen bundle preserves the Linux library and
its license, but it is not a Windows binary. No certified-counting toolchain is
required or claimed to have run.

## Check a supplied example

From this artifact directory:

```sh
python -B pcs.py check examples/declaration.json examples/plan.json examples/certificate.jsonl
python -B pcs.py audit examples/declaration.json examples/plan.json
```

For `check` and finite `audit`, exits are 0 for valid safe, 1 for valid unsafe,
and 2 for malformed, unsupported, corrupted or unreadable input. Generation
exit 0 means that a transcript was written, including for an unsafe plan.
Witness verification exit 0 establishes the least canonical fault.

`pcs.py` also supplies `certify`, `diagnose` and `check-witness`.
`pcs-update.py` supplies full-base/update and update-witness commands;
`docs/update-protocol.md` contains the runnable cold commands and warm API.
Output files and diagnosis directories must be new. Check a prefix transcript
with the same explicit prefix; a prefix-zero result does not establish full safety.

## Tests and reproduction

Portable discovery runs 66 methods: eight contract, fourteen restore-input,
three localization, six mask-sweep, eleven item-consumption, 23 record-admission,
and one report-serialization regression.

```sh
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

On Windows, select a private temporary parent before the same command:

```powershell
$private = Join-Path ([IO.Path]::GetTempPath()) ('P100-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $private | Out-Null
$env:TEMP = $private
$env:TMP = $private
$env:PCS_RESTORE_FIXTURE_PARENT = Join-Path $private 'restore-fixtures'
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

Record any skip as a skip; this portable route does not run the Linux campaign,
native solver or timing sweeps. On Linux, run the non-overwriting driver:

```sh
python -B scripts/reproduce.py --report ../mask-aware-recheck.json --raw-output ../mask-aware-raw
```

Both output paths must be new and outside this extraction. The driver restores
absent frozen assets from `data/frozen-material.zip`, refusing different existing
bytes, then runs in a private copy. It audits frozen evidence before fresh work
and compares exact inputs/transcripts and timing-independent scientific fields.
The source extraction is checked for non-mutation. The current test count is
discovered from source; the original eight-test record is kept as a historical
observation.

Default reproduction includes the retained arithmetic, finite updates, Boolean
semantics, additional prefix/mixed-modulus controls, local admission and two
small record-workflow checks. It validates saved timing summaries without
remeasuring all timing cases. Each Linux child has one affinity CPU, 2,500 MiB
address space, 110/115-second CPU limits, a 115-second alarm and a 120-second
outer process-group wall limit. Children run sequentially.

Optional `--benchmarks` adds 20 six-path timing inputs and three transfers;
`--smt` adds 48 finite native comparisons and 40 timed SMT configurations.
`--full` selects both. `--quick` omits the original large boundary regeneration.
New timings and timeouts remain new observations, not required reproductions of
a speed ratio. Full commands, phase coverage and resource details are in
`docs/reproduction.md`.

## Contract and consumer

For caller-supplied policy, declared history, affine permutation and guarded
fragments, verification establishes exact-once coverage of each (epoch,target)
and zero forbidden occurrences. The unauthorized penalty is linear multiplicity;
the authorized penalty is its squared deviation from one. Histories are trusted
inputs, and a target can reappear in another epoch. Witness order is
(epoch,counter), not target or wall-clock order.

A full safe check creates an immutable in-process anchor. Update elimination
removes unchanged-row counting queries under that safe premise. Changed context
or history requires a full check; large edits can cost more than full checking.
Parsing, matching and anchor storage still scale with the complete input.
Producer and checker have separate interval/CRT/floor arithmetic but share
parsing, Python and integer semantics.

`src/pcs/admission.py` consumes a verified anchor and holds consumption during
replacement. The fixed-record adapter additionally performs actual local file
reads and exact observed-history reconciliation. Its measured batches pause
reading after one full rebase. Further reads require full reconciliation before
incremental replacement resumes. The direct comparator evaluates the full
symbolic formula with trusted arithmetic; certificate routes include production
and separate checking. All eight workflow configurations remain, including the
six where direct calculation has the lowest median and two where updates do.
See `docs/record-workflow.md` for the complete API and costs.

The declared language allows domain up to 2^32, at most 16 epochs and 128 total
fragments, modulus up to 64, and 1,024 intervals per supplied list. JSON,
transcript and integer limits are defined in `src/pcs/model.py` and
`docs/format.md`; explicit oracles stop at 2^20. A valid schema does not promise
that every transcript fits the format limit or finishes within a benchmark bound.

## Inputs and retained results

| Material | Location |
|---|---|
| Inputs, examples and transcript format | `cases/`, `examples/`, `docs/format.md`, `docs/update-protocol.md` |
| Core evidence and the original failed-attempt accounting | `docs/evidence-map.md`, `results/validation.json`, `results/boundary.json`, `results/resource-accounting.json` |
| 96 update cases, 688 prefixes and mutation controls | `cases/updates.json`, `results/updates.json`, `results/update-contract.json` |
| 20 ordered-endpoint arithmetic inputs and three transfers | `results/runtime/` |
| Separate 64-command Windows campaign, including native SMT | `results/windows-2026-10-06/` |
| Original Linux arithmetic and SMT observations | `results/update-bench/`, `results/transfer/`, `results/smt/` |
| 72 local traversals, 1,440 replacement decisions, 540 holds | `results/record-workflow.json.gz`, `results/record-workflow-summary.json` |
| Proofs, comparisons and source records | `proofs/`, `docs/closest-work.md`, `docs/references.json`, `claim_evidence_ledger.csv`, `external_resources.csv` |

The paper's arithmetic tables and fragment/edit plot data use
`results/runtime/`; the SMT table uses its separate native campaign.
Do not pool these records with original Linux measurements. CPU resolution,
cold anchoring, negative large-edit results and incomplete solver outcomes
remain in the respective measurement records.

For an optional prefix-defect vector figure, install
`requirements-figures.txt` and run
`python -B figures/draw_prefix_defect.py`. It reads
`results/prefix-defect.csv` and writes the vector PDF without rerunning science.
Use `--out` and `--paper-dir` for other destinations. It uses legally installed
Times fonts or Matplotlib's bundled Times-compatible STIX serif; proprietary
fonts are not redistributed. Complete-project table and figure commands are
in `../paper/README.md`.

## Rights and research scope

Original code is covered by `LICENSE`; upstream Z3 notices remain under
`third_party/z3/`. Arguments, code, experiments and writing used substantive
generative-AI assistance. The supplied guarantees are about the stated finite
declarations and local serial consumer. Durable once-only execution,
authenticated external history and physical network operations are outside
that implementation.
