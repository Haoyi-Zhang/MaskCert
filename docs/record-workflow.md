# Local record-job admission

`RecordGate` connects the finite schedule contract to actual reads from a
caller-owned fixed-record file. It performs no address mapping or network
operation. Keep the file unchanged while the serial gate is open. Its progress
log lives in memory; it is not a crash-durable once-only execution protocol.

The `direct`, `full` and `incremental` routes accept the same declaration and
plan, enforce the same exact coverage obligation, and use the same detached
snapshots and record iterator. Direct calculation trusts the producer's exact
arithmetic. The certificate routes use the separately implemented checker;
their caller supplies, and pays for, the corresponding transcript.

The gate starts on HOLD. `admit` needs a safe base. `consume` reads fixed-length
records at their target offsets. `replace` first fences consumption, then checks
the proposed policy/plan; a failed proposal stays on HOLD while retaining the
last safe premise. Once reads have begun, `reconcile` requires the new history
to equal the previous declared history plus observed complete reads, then does
a full check on every route. Incremental replacement is available again after
that full rebase. Failed reconciliation does not erase observed progress.

```python
from pcs.record_admission import RecordGate

with RecordGate(path, n=declaration['n'], record_size=64,
                method='incremental') as gate:
    admitted = gate.admit(declaration, plan, full_certificate_lines)
    if admitted:
        records = gate.consume(10)
    # Any replacement now requires exact observed-history reconciliation.
```

The full runnable workflow is in `scripts/benchmark_record_workflow.py`.
It reads a prefix, fences an unreconciled change, reconciles progress and
processes policy/plan replacements before completing the job. Each cycle has
safe repartitions, stale revocation and restoration, their repairs, and a
duplicate followed by repair. Unsafe proposals remain on HOLD. These are
controlled workload edits, not external production incidents.

## Reproduction and cost accounting

From the artifact root, use a new output path:

```sh
python -B scripts/benchmark_record_workflow.py --quick --repetitions 1 --out ../record-check.json
python -B scripts/benchmark_record_workflow.py --repetitions 3 --out ../record-measurement.json.gz
```

Only the first command is included in default scientific reproduction. The
second executes eight larger configurations and is a separate timing route.
The file is prepared outside timing from the disclosed deterministic byte
recipe. Every measured route includes input acquisition, file opening,
transcript generation, initial checking, prefix reads, observed-history
reconciliation and full rebasing, every replacement, final reads, aggregation
and file closing. The direct route has no transcript production. The warm
interval includes both update production and checking. Cold here means
verifier initialization, not an emptied operating-system cache. Pointwise
validation and report serialization are outside timing. Method order rotates
over three repetitions. No favorable ratio is a reproduction requirement.

`results/record-workflow.json.gz` retains all inputs, 72 traversals, their
per-stage timings and 1,440 replacement decisions. It records 331,776 actual
record reads and 540 held replacements. The three routes agree on all
decisions and record sequences. `results/record-workflow-summary.json` is
derived from that observation by `scripts/export_record_workflow.py`, which
also regenerates the paper table when a sibling paper directory exists.
The Windows wall-clock observations include initialization and consumption;
they do not substitute for the older kernel measurements. All eight rows,
including the dense-edit case and configurations where direct calculation
has the lowest median, are retained.

`tests/test_record_admission.py` adds 23 methods for the real file adapter,
including exact history, rejected replacements, malformed certificates,
dictionary mutation, changed files, short reads and failed-read accounting.
The complete portable suite has 65 methods (42 existing plus 23 new); both
ordinary and optimized Python execute it. No old finite cases or old kernel
timings are relabeled as these new workflows.
