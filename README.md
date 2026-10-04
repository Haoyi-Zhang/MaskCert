# Mask-Aware Certificates for Affine Schedule Fragments

Project key: `mask-aware-certificates-for-permutation-complete-stateless-scan-plans`

This standalone repository is the artifact for the recovered six-page internal
technical note and its two-page Artifact Protocol. The original broad
“Permutation-Complete Sharding Certificates for Stateless Scan Plans” brief was
narrowed to this guarded affine fragment after the general formulation was not
established. TDSC is an intended calibration target only; this repository is
not evidence of an approved, submitted, accepted, or novelty-validated paper.
The incompatible later `pcs-v2` schema and anonymous nine-page supplement are
not part of this artifact.

The repository is self-contained. It does not require the sibling paper,
network access, an account, a solver download, a GPU, a private cache, a model
service, a live scanner, or any target host.

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

## Clean scientific recheck

Use Python 3.10 or later and its standard library. Linux is required for the
resource limits used by the experiment scripts. From this repository root:

```sh
python scripts/reproduce.py
```

The driver copies the repository to a private temporary directory, executes the
scientific scripts sequentially with one affinity CPU and an outer 120-second
per-child timeout, compares scientific fields and claim-critical files with the
retained observations, and confirms that the source extraction was not changed.
It does **not** overwrite the retained results. A faster, incomplete check is:

```sh
python scripts/reproduce.py --quick
```

`--quick` omits the large boundary run and is not a full reproduction. An
optional report may be written only to a path that does not already exist:

```sh
python scripts/reproduce.py --report ../mask-aware-clean-recheck.json
```

Paper compilation and figure-data export are intentionally separate from the
standalone scientific recheck. The artifact neither assumes a `paper/` directory
nor imports matplotlib.

The original experiment scripts remain available individually. Running one of
them directly refreshes its result file and is therefore a new observation,
not the preserved original run:

```sh
python scripts/pilot.py
python scripts/validate.py
python scripts/boundary.py
python scripts/regress.py
python scripts/examples.py
python scripts/repair_checks.py
python scripts/audit_evidence.py
```

Assertions are part of the finite validation; do not use `python -O`. General
arguments are in `proofs/arguments.md`. A successful command is finite evidence
for this implementation, not a formal verification of Python or a proof of
physical execution.

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

- `project.json`: authoritative project identity and venue/author status.
- `results/identity-audit.json`: executable identity/model-lineage check.
- `results/dependency-audit.json`: static standard-library-only import audit.
- `docs/recovery-audit.md`: identity and mismatched-artifact decision.
- `docs/format.md`: precise schema, transcript order, limits, and binding scope.
- `docs/semantic-controls.md`: the six semantics-sensitive finite controls.
- `docs/evidence-map.md`: exact mapping for Tables II and III.
- `docs/reference-audit.md`: the two used references and corrected Dagstuhl record.
- `claim_evidence_ledger.csv`: material claims and their proof/test/result state.
- `cases/`: exact retained generated inputs; no live or public host data.
- `results/validation.json`: aggregate retained finite-evidence counts.
- `results/validation-cases.json`, `results/feistel-cases.json`: per-case results.
- `results/boundary-certificate.jsonl`: the retained 31.296-MiB transcript.
- `results/resource-failure.json`: the first timeout and the empty-lattice repair.
- `results/evidence-map.json`: selection, skip, corruption, and Table mapping.
- `results/repair-checks.json`: repair-specific semantic, limit, witness, and CLI checks.
- `external_resources.csv`: scholarly/workflow source and license ledger.

## Scope, authorship, and provenance

The certificate establishes the logical invariant of the supplied declaration
and plan. It does not authenticate policy or history, attest execution, prove
that a scanner followed the plan, authorize scanning, or implement ZMap's
multiplicative-group traversal. The transcript is semantically tied to the
supplied input because every query is reconstructed, but it is not a digital
signature or cryptographic commitment to a unique file.

The named metadata recovered in the six-page manuscript and two-page protocol
must be confirmed by the actual authors before external use. The anonymous
nine-page supplement was a mismatched artifact and is excluded; no consent,
affiliation approval, corresponding-author role, or submission approval is
inferred. The work is not independent review or a completed TDSC Regular Paper.
