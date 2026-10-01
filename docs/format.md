# Exact finite-plan format

All indices and endpoints are decimal JSON integers, not booleans, strings or
floating-point numbers. Unknown fields, duplicate object keys, NaN, Infinity
and integers with more than 40 decimal digits are rejected. A mask is a list
of [low,high] pairs. Intervals must be nonempty, within [0,N), sorted,
disjoint and nonadjacent. Adjacent intervals must first be merged. The empty
list denotes the empty set; [[0,N]] denotes the whole target space.

## Independent declaration

```json
{"n":8,"a":3,"b":1,
 "epochs":[{"allow":[[0,8]],"exclude":[[1,2]]}],
 "history":[]}
```

The permutation is (a*i+b) mod n, and gcd(a,n) must equal one. For n=1,
a=b=0. The intended set in each epoch is allow minus exclude. Both lists are
trusted declarations; exclusion wins where they overlap. The declaration
must come from the source whose policy is being checked, not from an
untrusted certificate generator. The tool does not authenticate its origin.

## Proposed continuation

```json
{"context":{"n":8,"a":3,"b":1},
 "future":[{"epoch":0,"lo":0,"hi":8,"step":1,"residue":0,
             "guard":[[0,1],[2,8]]}]}
```

Every context field must equal the independently supplied declaration.
A row belongs to an epoch and has source counters satisfying
lo<=i<hi and i mod step=residue. It contributes an occurrence only when the
permuted target belongs to guard. An empty source range lo=hi is legal.
`history` contains the same row objects. Positions in history followed by
future define immutable row indices. Rows are not collapsed or deduplicated.
No row asserts a real-time execution, and an epoch does not imply a device.

## JSON-lines arithmetic certificate

The first line is exactly `{"prefix":t}`. For every required floor sum in the
reconstructed query order, the next line is `[value, [[qa,qb,h], ...]]`.
The last line has exactly the fields `defects` (one integer per epoch) and
`accepted` (a Boolean). For whole-plan checking, t=N. Empty progressions,
empty masks and full masks do not consume floor records. Empty pair lattices
are skipped before constructing their masks.

Query order is epochs in declaration order; desired-prefix count; each
selected row in input order (total guarded count then desired guarded count);
then row pairs in lexicographic position order. Each canonical mask interval
contributes the lower-endpoint floor expression followed by the upper-endpoint
floor expression. Every floor expression is evaluated from input geometry.
Quotient triples are checked, not accepted as trusted numerical facts.
Trailing records and premature EOF are errors.

The certificate makes no cryptographic binding claim. A transcript may be
valid for more than one input if all reconstructed statements happen to hold.
Checking it always establishes only the particular supplied input and prefix.

## Least-witness bundle

`witness.json` contains exactly `epoch`, `counter`, `target`, `kind`, `rows`.
The kind is omission, collision or forbidden. The row list is empty for an
omission, the first two matching positions for a collision, and the first
matching position for a forbidden occurrence. `full.jsonl`, `before.jsonl`
and `through.jsonl` certify prefixes N, counter, and counter+1 respectively.
The full certificate establishes that no earlier epoch is faulty. The other
two establish that this is the first faulty counter in the chosen epoch.

The witness ordering is (epoch,counter), not target order, wall-clock event
order or a globally minimum explanation size. A corrupted bundle is not a
valid counterexample to the declaration.

## Supported-format bounds

The executable constants are centralized in `src/pcs/model.py`:

| Object | Bound |
|---|---:|
| Domain | `1 <= N <= 2^32` |
| Fragment modulus | `1..64` |
| Epochs | `1..16` |
| History plus future rows | at most 128 |
| Intervals in each supplied list | at most 1,024 |
| Declaration or plan file | at most 8 MiB |
| Certificate file | at most 64 MiB |
| Certificate line | at most 65,536 bytes |
| Triples per floor query | `1..68` |
| Transcript integer | `0..2^128-1` |
| Explicit counter/replay oracle | `N <= 2^20` |

Boundary-plus-one cases for rows, intervals, epochs, input bytes, certificate
line bytes and the explicit oracle are exercised by `scripts/repair_checks.py`.
A direct internal reader test exercises the total certificate byte limit. The
retained exact-oracle boundary experiment uses exactly `N=2^20`; `2^20+1` is
unsupported by both explicit oracle entry points. The symbolic checker has a
separate `N<=2^32` domain cap.

The limits describe the supported input format. They do not promise that every
schema-valid plan produces a certificate below 64 MiB or completes within the
experiment timeout. Resource rejection is malformed/unsupported status, not an
unsafe-plan verdict.

## Public checker outcomes

For `python pcs.py check DECLARATION PLAN CERTIFICATE`:

- exit 0: certificate is valid and the plan is safe;
- exit 1: certificate is valid and the plan is unsafe;
- exit 2: input is malformed, unsupported, unreadable or the transcript is
  corrupted/inconsistent.

The JSON output always distinguishes `verified` from `accepted`. Certificate
generation is not verification and may successfully write a transcript whose
trailer reports an unsafe plan.

## Trusted and independent components

The checker imports only the shared model/parser/limit module from this
project. It independently reconstructs intersections with an endpoint sweep,
combines congruences with an extended-Euclidean lattice routine, and validates
each supplied quotient/remainder triple. The producer uses different interval,
modular-inverse and floor-sum code. Both rely on the shared schema, Python
runtime and arbitrary-precision integers. The explicit counter and target-
indexed oracles are test-only and are not dependencies of either producer or
checker.

“Input binding” in this format means semantic reconstruction: the supplied
declaration, plan and requested prefix determine the exact query stream and
trailer that can be accepted. The header explicitly binds the prefix. There is
no hash, signature, or cryptographic commitment to a unique input file; two
inputs that reconstruct identical statements may accept the same transcript.
