# Permutation-Complete Sharding Certificates

This release accompanies **“Mask-Aware Certificates for Permutation-Complete Stateless Scan Plans.”** It contains the 12-page paper, supplementary proofs, a dependency-free Python checker, strict schemas, safe and unsafe examples, retained raw experiments, frozen DOI metadata, and release-quality assurance.

## Claim boundary

For a universe `0..N-1`, one shared affine permutation `(a*i+b) mod N`, a canonical union of authorized target intervals, and bounded congruence fragments, the checker proves a property of the **declared plan**:

- every authorized target has multiplicity exactly one; and
- every target outside the authorization mask has multiplicity zero.

It does not prove that workers executed the plan, that remote side effects committed exactly once, that SHA-256 authenticates an author, or that the method applies unchanged to arbitrary pseudorandom permutations.

## Fast verification

```bash
python software/scripts/reproduce.py
```

The command uses only the Python standard library for the checker and tests. PDF rebuilding additionally requires `pdflatex`, `bibtex`, `pdfinfo`, `pdftotext`, and `pdftoppm`.

Manual certificate commands:

```bash
PYTHONPATH=software python software/pcs.py check \
  examples/declaration.json examples/safe-plan.json \
  examples/safe-plan-certificate.jsonl --require-safe

PYTHONPATH=software python software/pcs.py check-witness \
  examples/declaration.json examples/missing-plan.json \
  examples/missing-plan-witness.json
```

## Layout

- `paper/`: IEEEtran source, generated result tables, figures, bibliography, and build logs.
- `supplement/`: detailed proofs, schemas, tests, and reproduction protocol.
- `software/pcs/`: strict parser, exact arithmetic, certificate and witness checker.
- `software/tests/`: deterministic unit, differential, tamper, and CLI tests.
- `software/scripts/`: example generation, benchmarks, bibliography audit, QA, and reproduction.
- `examples/`: one safe plan and missing, duplicate, and forbidden variants.
- `results/`: raw repeats, CSV views, and retained certificates.
- `docs/`: threat model, claim/evidence map, reference audit, and format specification.
- `qa/`: build, PDF, archive, and clean-room reports.

## Paper builds

```bash
(cd paper && ./build.sh)
(cd supplement && ./build.sh)
```

The release gate requires the main paper to be exactly 12 pages, at least 40 unique rendered bibliography entries, no unresolved references, successful rasterization, and a clean-room artifact rerun.

## License

Source code is released under the BSD 3-Clause License. The paper text and generated documentation are supplied for review and reuse with attribution; publication rights can be updated by the eventual authors.
