# Semantics-sensitive controls

`python scripts/repair_checks.py` executes the following finite controls with
both symbolic verification and the explicit oracles where applicable. The
machine-readable record is `results/repair-checks.json`; it is a repair recheck,
not a relabeling of the original Table-II run.

1. **Empty authorization with repeated output.** Two occurrences at one
   unauthorized target have defect 2. This confirms the unauthorized penalty is
   linear `m`, not squared `m^2=4`.
2. **Empty fragment.** An empty source range retains its row position but emits
   nothing and does not make an otherwise complete plan unsafe.
3. **Overlap only at an exclusion.** Raw source overlap mapping only to an
   excluded target is harmless after guards and exclusion semantics.
4. **Mutually exclusive guards.** Identical source ranges are safe when their
   target guards partition the desired set.
5. **Cross-epoch reuse.** The same target may be covered once in each retry
   epoch because the certified object is `(epoch,target)`.
6. **Declared-history protection.** A future continuation completes the trusted
   declared history; duplicating that history is detected, and a transcript
   cannot simply be reused after changing the declaration.

The same script validates the theorem-order witness, full/before/through prefix
bundle, swapped-prefix and changed-row rejection, malformed transcript fields,
input/certificate/line/row/interval/epoch bounds, explicit-oracle boundary and
boundary+1, checker imports, and public CLI exit codes 0/1/2.
