# Recovery and mismatch audit

## Accepted source lineage

The authoritative recoverable set is the original project archive containing:

1. a six-page manuscript titled *Mask-Aware Certificates for Affine Schedule
   Fragments*;
2. a two-page *Artifact Protocol for Affine Schedule Certificates*;
3. `guard`, `epoch`, `allow`, `exclude`, declared `history`, and proposed
   `future` fields;
4. the mask-aware defect with unauthorized penalty `m`;
5. separate producer and checker arithmetic;
6. exact inputs and retained evidence for Tables II and III.

The project directory, `project.json`, READMEs, review identity, and output
names now use the single slug
`mask-aware-certificates-for-permutation-complete-stateless-scan-plans`.

## Rejected mismatched replacement

The later `pcs-v2`/nine-page-supplement set was not used because its model and
evidence do not match the six-page paper: it has no equivalent guard/epoch/
exclusion/trusted-history semantics, uses a squared unauthorized penalty, and
contains different examples, certificates, results, and authorship metadata.
Changing its title or filenames would not repair that mismatch.

## Restored assets

- matching TeX, bibliography, native TeX figures, and compiled six-/two-page PDFs;
- strict declaration/plan parser and supported-format bounds;
- producer using its own interval/CRT/floor arithmetic;
- checker using endpoint sweep, extended Euclidean congruence composition, and
  verified quotient/remainder triples;
- root `pcs.py`, example declaration/plan/certificate paths, and witness bundle;
- N=64 theorem-order witness `(epoch=0,counter=2,target=17)` and `D(50)=12`;
- full/before/through witness checks and order/row-position rejection tests;
- Table-II and Table-III exact inputs, per-case records, certificate, and resource
  observations, including the retained failed run and source repair;
- non-overwriting clean scientific recheck that does not require the paper,
  matplotlib, network access, GPU, or external model/API services.

## Information that cannot be recovered or asserted

- the actual CPU time of the failed first boundary run was never measured; the
  retained 115 seconds is a budget charge, not an observation;
- the complete interactive campaign CPU total is incomplete;
- actual-author approval of the named manuscript/protocol metadata is absent;
- TDSC submission approval, current-rule compliance, novelty, acceptance, and
  independent review are not established;
- the format has semantic reconstruction and explicit prefix binding but no
  cryptographic commitment to a unique declaration/plan file;
- finite checks do not convert the mathematical arguments into a mechanically
  verified proof or establish physical execution.
