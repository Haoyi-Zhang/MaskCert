# Safe-anchor elimination, soundness and chains

## Premises and notation

Fix one epoch and the same bijection from counters to targets before and after
an update. All row predicates are Boolean on a source counter. The old declared
history is unchanged. Match future rows by their complete canonical values,
with multiplicity and earliest-position matching; let r occurrences remain
removed and s remain added. U and V are old/new desired sets (authorization
minus exclusion). Let u and v be their indicators on the permuted target.
The old input and a FULL certificate have already been verified safe.

The proof is mathematical. Finite tests of Python are not mechanized proofs.

## Lemma: removed occurrences are Boolean

Old safety is m(i)=u(i) at every counter. Every removed row is one occurrence
of the old future multiset. Its summed multiplicity R(i) satisfies
0 <= R(i) <= m(i)=u(i) <= 1. Consequently R²=R and uR=R, and distinct removed
row occurrences cannot both contribute at one counter. Empty removed rows are
permitted. Matching does not alter the fixed history. The unchanged contribution
is u-R. If A sums the added rows, new multiplicity is m'=u-R+A >= 0.

## Theorem: exact change-only defect

For v in {0,1}, define d(z,v)=z+v(z²-3z+1). This is z for v=0 and (z-1)² for
v=1. Using u²=u, R²=R and uR=R, direct expansion yields

    d(u-R+A,v)
      = u+v-2uv - R+2vR + A-2v(1-u)A
        + v A(A-1) - 2vAR.

For a source prefix [0,t), sum the equality. The first three indicator terms
sum to the count of the symmetric difference U△V. Write |row ∩ mask|_t for
the exact masked row count restricted to this prefix. Then

    D_new(t) = |U△V|_t
       - sum_removed |row|_t + 2 sum_removed |row∩V|_t
       + sum_added |row|_t - 2 sum_added |row∩(V\U)|_t
       + 2 sum_unordered_added_pairs |intersection∩V|_t
       - 2 sum_added_removed_pairs |intersection∩V|_t.

For A=sum_j a_j with Boolean a_j, A(A-1)=2 sum_{j<k}a_j a_k; for R=sum_k r_k,
AR=sum_{j,k}a_j r_k. These are identities with occurrences, not sets of distinct
row values. That proves the displayed formula without assuming the new plan
is safe. It stays valid for arbitrary policy changes, empty policies/guards,
nonempty declared history, duplicates among added occurrences and every prefix.
The only old-plan restriction needed by this elimination is full safety plus
unchanged context/history. No term counts an unchanged fragment or a removed
pair. Result nonnegativity follows from the exact local-defect expression,
not from the signs of individual aggregate terms.

## Certificate correctness

The checker independently computes the removed/added position lists and every
count request, with the same external schema as full verification. Old/new
policy difference is evaluated by |U|+|V|-2|U∩V|, unless U=V, in which case no
query is needed. Exact endpoint-sweep intersections, extended-Euclidean CRT
composition and the inherited quotient-transcript verifier establish each
requested count. The update header must match the requested prefix and exact
position lists. Trailer counts must equal the reconstructed signed sum.
Missing and trailing records are invalid. Therefore acceptance of a complete
well-formed update transcript returns exactly D_new(t). At t=N, a zero vector
is equivalent to the new declared epoch-target invariant. Mathematical
completeness follows by supplying correct arithmetic transcripts; serialization
and execution resource bounds restrict the concrete supported implementation.

A same-valued transcript can serve two inputs if every reconstructed query and
answer agrees. The soundness claim is the result for each independently supplied
input, not a cryptographic commitment to a unique file or an authenticated log.

## Chains and earliest faults

An initial anchor is issued only after full safe verification. Snapshot inputs
before checking and retain them immutably. Advance only when the complete
update result is safe, and snapshot its input too. Induction on the number of
advances gives the safety premise at each step. An unsafe successor cannot
advance; a valid prefix cannot advance because it is not a complete premise.

For an unsafe new plan, choose the first epoch with positive full defect.
For that epoch, each prefix increment is a nonnegative local defect. Thus the
least counter x is characterized by D_e(x)=0 and D_e(x+1)>0. A full transcript
excludes earlier defective epochs, and these two adjacent prefix transcripts
exclude earlier counters. Direct row membership determines the correct target,
kind and canonical history-first/new-future positions. A substituted prefix or
altered row position is rejected. This is least (epoch,counter), not least
target, earliest actual execution, shortest network trace or smallest file.

## Cost and limits

There are up to three policy counts, two counts per removed and added row,
C(s,2) added-pair counts and sr cross counts per epoch. Empty source/mask and
full-mask shortcuts reduce this number. With E an upper bound on the sizes of
constructed interval sets, each masked count makes O(E) floor queries, each
with O(log N) Euclidean steps. Thus arithmetic work has bound
O((1+r+s+s²+sr) E log N), separately from reading/matching the whole input and
constructing its interval intersections. Integer arithmetic is exact. The
bound is not a constant-time input parser or a claim that machine-word
operations have uniform cost for arbitrary bit widths.

The safe anchor stores O(input size) state. It stores no quadratic array of old
pair counts. This is an in-process trusted capability, not protection against
malicious code already inside the interpreter. Cross-process persistence needs
trusted storage/authentication or full revalidation. At large r,s the change
formula can have more pair work than a full check; measured negative cases are
retained. General incremental query algebra and caching predate this result.

## Why the precondition cannot be silently relaxed

An unsafe empty old plan with U={0} and no update would make the substituted
m'=u, hiding its omission. FULL safety is therefore indispensable for this
formula, not an optional optimization hint. Four scalar counts also do not
recover arbitrary unsafe structure: U={0,1} with multiplicities (2,0) and
(0,2) has B=T=C=2 and Q=1 in both cases. Adding counter zero produces defects
5 and 1. A separate method with additional trusted state could handle these
cases; this theorem does not.
