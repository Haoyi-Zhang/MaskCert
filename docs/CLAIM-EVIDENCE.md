# Claim–evidence map

| Claim | Primary evidence | Independent/negative evidence | Boundary |
|---|---|---|---|
| `D=0` iff the mask is covered exactly once | Main paper Theorem 1; supplement expanded proof | Small manual fixtures; 1,000 explicit-oracle plans | Declared plan only |
| Mapped interval counts are exact | Floor-sum derivation | 5,000 modular-threshold and 5,000 mapped-interval differential cases | Affine map, bounded congruence fragment |
| Pair counts are exact | Generalized CRT derivation | 3,000 explicit bounded-set intersections | Pairwise source intersection |
| Certificate binds the intended bytes | Canonical input hashes in header | Declaration/plan mismatch tests | Collision-resistant binding, not authentication |
| Transcript edits are rejected | Checker constructs the complete expected transcript | deletion, duplication, reordering, truncation, unknown-field and 200 seeded mutation tests | Trusted checker/runtime |
| Unsafe output has a canonical earliest witness | Prefix-defect theorem | Missing/duplicate/forbidden fixtures, tamper tests | Earliest target order, not execution time |
| Work avoids universe enumeration | Complexity derivation; source inspection | fixed-structure domain-size experiment; explicit-oracle baseline | Still depends on fragment and mask structure |
| Large retained case is safe | Exact construction, retained inputs, certificate and `D=0` | clean-room recheck | Synthetic case, host-specific timing |
| Bibliography records are identifiable | frozen Crossref JSON and exact DOI match | offline uniqueness/completeness audit | Metadata identity, not correctness of each paper |
| Main paper meets release format gate | PDF page count, `.bbl` entry count, logs, raster QA | clean-room rebuild | Final portal metadata remains author responsibility |
