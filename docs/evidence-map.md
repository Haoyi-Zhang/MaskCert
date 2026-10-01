# Evidence map for Tables II and III

This is a read-only audit of retained files. It does not relabel a new run as
the original observation.

## Table II

- 303 retained affine plans map to `cases/validation.json` and 303 rows in
  `results/validation-cases.json`.
- The 909 prefix comparisons are exactly three actual comparisons for each
  retained plan.
- The 146 witness checks equal the 146 unsafe retained plans.
- The 1,194 corruption checks are actual verifier calls: 588 record-level
  mutations on 294 certificates that contain floor records, plus 303
  truncations and 303 trailing-record checks. Nine shortcut-only certificates
  contain no floor record, so the two record-level mutation types are
  inapplicable rather than silently counted.
- The 123 tiny plans come from 204 candidate `(N,a,b)` triples for `1 <= N <=
  8`; 81 are excluded by the declared `gcd(a,N)=1` precondition. The 96
  arbitrary-mask plans, 3 guard controls, 1 multi-epoch plan and 80 functional
  variants were all retained.
- 276 Feistel truth tables were constructed and compared; 16,656 point checks
  are reported separately rather than added to the 23,676 named obligations.

## Table III

- Input: 61 declared-history residue fragments, 64 future residue fragments,
  1,024 exclusions and 1,024 guard intervals per fragment over `N=2^32`.
- Certificate: 32,816,640 bytes (31.296
  MiB), 514,048 floor-query records and
  1,372,994 checked Euclidean triples.
- Frozen observation: producer 2.768
  CPU s, checker 6.207 CPU s,
  combined-run peak 111.168 MiB. These are the
  retained single-run observations, not values from this audit.
- The failed first run has no measured CPU duration. The 115 s value is an
  explicit budget charge, not an observation. Its repair is the empty-lattice
  short-circuit recorded in `results/resource-failure.json`.

## Exact source map

See `results/evidence-map.json` for machine-readable fields and exact paths.
