# Model and documents

- **PROJECT_NAME:** Mask-Aware Certificates for Affine Schedule Fragments
- **SLUG:** `mask-aware-certificates-for-permutation-complete-stateless-scan-plans`
- **Document set:** `paper/main.pdf` is the fifteen-page manuscript;
  `paper/supplement.pdf` is the six-page *Artifact Protocol for Affine Schedule
  Certificates*. Both are compiled from the accompanying sources. The
  standalone artifact runs independently of paper compilation.
- **Target venue:** IEEE Transactions on Dependable and Secure Computing.

## Scientific scope

The model uses guarded affine schedule fragments, epochs, exclusions and
separate trusted-history and future domains. Its unauthorized-target cost is
linear in the unauthorized mass, and least witnesses follow epoch/counter
order. The manuscript, protocol, schema, implementation and exact inputs use
these same semantics.

Safe-anchor updates localize subsequent checking within this model. The
artifact includes the update checker, exact Boolean encoding and the raw
evaluation records used for the corresponding tables and figures. Development
provenance and third-party licensing remain in the artifact README and license
files.
