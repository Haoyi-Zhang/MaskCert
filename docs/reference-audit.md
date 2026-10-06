# Reference identity and citation-use audit

Twenty scholarly references are actually used by the twelve-page manuscript.
There is no asserted TDSC minimum citation count. Primary publication records
and the specific technical passages used in comparison were inspected; this is
not a claim that all twenty full papers were read, that each experiment was
independently reproduced, or that a live Crossref audit was executed.

The current Dagstuhl record for the VeriPB paper is LIPIcs volume 379,
43:1–43:21, DOI 10.4230/LIPIcs.CP.2026.43. Its enumeration implementation and
counting discussion are distinguished. URLs below identify source publications,
not substituted web references in the scholarly bibliography.

## zmap
Ten Years of ZMap

Primary record: https://zakird.com/papers/zmap-retrospective.pdf

Supported use: Target-generation and sharding history; no affine implementation compatibility inferred.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## veripb
Proof Logging for Projected Enumeration (and Counting?) Problems in VeriPB

Primary record: https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.CP.2026.43

Supported use: Projected enumeration rules and CakePB implementation; counting discussion is not an evaluated universal counting frontend.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## certifying
Certifying Algorithms

Primary record: https://www.cs.colostate.edu/~rmm/cert11.pdf

Supported use: Checker/certificate separation and limited trusted code; not a new general certifying paradigm.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## cpog
Certified Knowledge Compilation with Application to Formally Verified Model Counting

Primary record: https://arxiv.org/html/2501.12906v1

Supported use: POG plus equivalence proof, graph sharing, Lean checker and weighted counter; stronger mechanization than this artifact.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## projected
Certifying Projected Knowledge Compilation

Primary record: https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.SAT.2025.8

Supported use: Projection certificates and formally verified checking; no enumeration-only strawman.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## cd4
Certifying Top-Down Decision-DNNF Compilers

Primary record: https://ojs.aaai.org/index.php/AAAI/article/view/16776

Supported use: Certified top-down compilation, a relevant nonenumerative exact-counting route; not executed in this artifact.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## mice
Proofs for Propositional Model Counting

Primary record: https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.SAT.2022.30

Supported use: Dedicated #SAT proof systems; not the only or universally strongest baseline.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## strength
The Relative Strength of \#SAT Proof Systems

Primary record: https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.SAT.2024.5

Supported use: Proof-system strength and representations must be separated from runtime or enumeration cost.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## ssat
Knowledge Compilation for Incremental and Checkable Stochastic Boolean Satisfiability

Primary record: https://www.ijcai.org/proceedings/2024/0206.pdf

Supported use: Levelized dec-DNNF, reweighting/cofactoring and CPOG-derived SSAT checking; incrementality plus checkability predates this work.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## pbcount
Towards Projected and Incremental Pseudo-Boolean Model Counting

Primary record: https://arxiv.org/html/2412.14485v1

Supported use: ADD cache reuse for addition/removal of constraints; distinguishes ordinary incremental counting from safe-invariant elimination.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## approx
Formally Certified Approximate Model Counting

Primary record: https://arxiv.org/abs/2406.11414

Supported use: Formally certified PAC counting is a different result contract from an exact deterministic defect, not an invalid method.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## dbtoaster
DBToaster: Higher-order Delta Processing for Dynamic, Frequently Fresh Views

Primary record: https://vldb.org/pvldb/vol5/p968_yanifahmad_vldb2012.pdf

Supported use: Higher-order relational deltas; do not claim novelty for delta algebra or incremental maintenance itself.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## kcmap
A Knowledge Compilation Map

Primary record: https://jair.org/index.php/jair/article/view/10311

Supported use: Compilation languages trade off succinctness, queries and transformations.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## isl
isl: An Integer Set Library for the Polyhedral Model

Primary record: https://lirias.kuleuven.be/retrieve/114886/

Supported use: General integer-set infrastructure; no proof logging or performance claim for this artifact.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## barvinok
A Polynomial Time Algorithm for Counting Integral Points in Polyhedra When the Dimension Is Fixed

Primary record: https://pubsonline.informs.org/doi/10.1287/moor.19.4.769

Supported use: Fixed-dimensional lattice counting is established prior tractability, not a new contribution of the affine specialization.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## z3
Z3: An Efficient SMT Solver

Primary record: https://link.springer.com/chapter/10.1007/978-3-540-78800-3_24

Supported use: Actual optional unmodified native decision baseline, no checked #SAT proof claim.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## hsa
Header Space Analysis: Static Checking for Networks

Primary record: https://www.usenix.org/conference/nsdi12/technical-sessions/presentation/kazemian

Supported use: Static symbolic network checking is operational context, distinct from per-epoch plan multiplicity.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## veriflow
VeriFlow: Verifying Network-Wide Invariants in Real Time

Primary record: https://www.usenix.org/conference/nsdi13/technical-sessions/presentation/khurshid

Supported use: Incremental forwarding-invariant checking; do not claim first incremental network verification.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## netplumber
Real Time Network Policy Checking Using Header Space Analysis

Primary record: https://www.usenix.org/conference/nsdi13/technical-sessions/presentation/kazemian

Supported use: Dependency-based incremental policy checking; not the exact masked multiset certificate here.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## zmap13
ZMap: Fast Internet-wide Scanning and Its Security Applications

Primary record: https://www.usenix.org/conference/usenixsecurity13/technical-sessions/paper/durumeric

Supported use: Stateless traversal motivation, not compatibility, target authorization, or packet experiment evidence.

Primary publication record and relevant passages; not a machine Crossref audit or full independent replication.

## Executable consistency check

The optional `scripts/audit_paper.py --paper PATH` checks citation keys, actual
BBL entries, unique DOIs, recorded fields and source contexts. It is a
consistency check against this curated primary-source ledger, not a program
that can decide whether an argument was cited correctly. The claim-specific
uses above and the manuscript comparison remain inspectable by a human reader.
The twelve-same-TDSC-paper calibration is not completed.
