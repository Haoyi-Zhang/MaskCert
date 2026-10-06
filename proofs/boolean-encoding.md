# Parsimonious Boolean connection

For one fixed epoch and source prefix, the application supplies the exact
multiplicity m(i) and desired-membership bit u(i). Introduce binary primary
indices i,p,q with widths sufficient for the counter domain and maximum
multiplicity. Enforce 0 <= i < t <= N. For each i admit these disjoint tokens:

* u=1,m=0: only p=q=0 (one omission token).
* u=1,m>=1: 0<=p<m-1 and 0<=q<m-1 ((m-1)^2 tokens).
* u=0: 0<=p<m and q=0 (m forbidden-occurrence tokens).

Summing local token counts proves #models = D_e(t) at the level of the
Boolean circuit. In particular #models=0 iff that epoch-prefix has zero
defect. Non-power-of-two counter bit patterns are excluded by i<t; they do
not add models. Widths in the implementation represent every valid product,
remainder and multiplicity before any projection or comparison.

Every auxiliary AND/XOR variable has bidirectional defining clauses. Induct
on gate construction order: after fixed primary inputs, earlier literals have
unique values and the next gate's definition fixes its output uniquely. No
unconstrained auxiliary variables remain. The final unit acceptance constraint
admits this unique extension exactly when the circuit token predicate is true.
Thus conversion to ordinary CNF is parsimonious, not a multiplication of
counts by SAT auxiliary assignments. The fixed constant variable is itself
unit-constrained. Gate reuse preserves the same unique extension.

For safe-anchor reduction, unchanged mass is u-R. Removed row events are
pairwise disjoint and imply u, so u-R equals u AND NOT(OR removed predicates).
Add the new-row indicators and use the identical token predicate for the new
policy. This proves the reduced CNF has the same exact count as the full new
CNF. A general certified backend is free to exploit this same substitution.

This theorem does not assert a proof-size lower bound or runtime disadvantage
for CPOG, projected CPOG, decision-DNNF, VeriPB or any other general system.
It explicitly gives them an exact application encoding. That encoder remains
part of a combined end-to-end correctness boundary: certifying a CNF result
alone does not prove that an arbitrary buggy frontend translated the input
correctly. Here the proof is mathematical and the executable frontend has
finite gate, arithmetic and plan checks, not a proof-assistant theorem.

The archived DIMACS files were generated and finite-validated; an upstream
certified-counting pipeline was not run. The native SMT experiments use a
separate safety-decision formula and trust UNSAT. They are not CNF counting
runs, proof-generation runs or proof-checking timings. UNKNOWN is unresolved.
