# PCS v2 format specification

This document is normative for the included reference implementation. Detailed semantics and proofs are in the supplement.

## Canonical JSON

UTF-8; object keys sorted for hashing; compact separators; array order preserved; no duplicate object keys. Validation precedes hashing. Unknown fields are errors.

## Declaration

```json
{
  "schema": "pcs-declaration-v2",
  "universe": 64,
  "permutation": {"kind": "affine", "multiplier": 5, "offset": 7},
  "authorized": [[1, 2], [3, 4]]
}
```

The multiplier must be coprime to the universe. Authorized intervals are sorted, nonempty, disjoint, nonadjacent, and bounded by the universe.

## Plan

```json
{
  "schema": "pcs-plan-v2",
  "fragments": [
    {"id": "f000", "phase": "committed", "lo": 0, "hi": 64,
     "stride": 4, "residue": 0}
  ]
}
```

Identifiers are unique and strictly increasing. A phase is `committed` or `planned`. Every fragment must select at least one counter in `[lo,hi)`.

## Certificate

Canonical JSONL rows:

1. header;
2. one fragment row per fragment;
3. one pair row for each lexicographically ordered pair;
4. summary.

Every row includes `seq`, `prev_sha256`, and `row_sha256`. The first predecessor is 64 zeroes. A row digest hashes the canonical row without `row_sha256`.

## Witness

A witness is one canonical JSON object with schema `pcs-witness-v2`, input digests, category, target, inverse source, authorization state, expected/actual multiplicity, covering fragment IDs, prefix defects, total defect, and object digest. It must equal the checker-recomputed least-target witness.
