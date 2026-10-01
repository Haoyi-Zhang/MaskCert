# Arithmetic coverage arguments

These are complete mathematical arguments for the model stated here, not a
proof-assistant development and not an assertion of research novelty. The
separate Python implementations and finite oracles test their realization.
No theorem below authenticates a declaration or establishes what a physical
executor actually did.

## 1. Model and statement of the invariant

Let N be a positive integer. Counters and target identifiers are integers in
[0,N). Fix a,b in [0,N) with gcd(a,N)=1 and let pi(i)=(ai+b) mod N.
For N=1, a=b=0 is the sole permitted choice. For each epoch e, a trusted
external declaration supplies unions A_e and X_e of integer half-open
intervals, and the intended targets are U_e=A_e\X_e. A declared history is
part of this trusted input. A proposed continuation supplies additional rows.
The continuation must repeat the same N,a,b; the checker compares these fields
with the independently supplied declaration, not with a value asserted only
inside the certificate.

A row r=(e,l,h,s,rho,G) contributes one occurrence at counter i precisely when
its epoch is e, l<=i<h, i mod s=rho, and pi(i) belongs to its interval guard G.
The constraints are 0<=l<=h<=N, s>=1, and 0<=rho<s. Empty ranges and guards
are permitted. Distinct rows are occurrences even when all their fields are
equal. The rows of an epoch are its history rows followed by its future rows,
retaining input order. There is no implicit deduplication.

Let m_e(i) be the number of contributing rows and u_e(i) the indicator of
pi(i) in U_e. The desired property is

    m_e(i) = u_e(i) for every epoch e and every counter i.

A retry is a separate epoch. Accordingly exact-once means exact-once for
(epoch,target), not exact-once for the target across all epochs. It is
impossible to require both a nonempty retry and global target multiplicity
one when both occurrences count as physical transmissions.

### Lemma 1: the counter invariant is exactly the target invariant

Suppose pi(i)=pi(j). Then N divides a(i-j). Since a and N are coprime, Bezout's
identity implies that N divides i-j. Both counters belong to [0,N), so i=j.
Thus pi is injective, hence bijective on this finite set. A target has exactly
one inverse counter, and every row occurrence for that target is counted by
m_e at that counter. The displayed invariant therefore says that each desired
target occurs once and every undesired target occurs zero times. This includes
excluded targets inside the authorization interval and targets outside it.
The one-point domain satisfies the same argument directly.

The theorem does not require the *unguarded* counter sets to partition [0,N).
For example, N=8, pi(i)=(3i+1) mod 8, and X={1}. A full counter row guarded by
U plus a second row covering only counter zero is safe if both guards are U:
the second row emits nothing. Removing counter zero altogether is also safe.
Two full counter rows with disjoint guards [0,4) and [4,8) are safe when all
targets are desired. An unguarded partition test rejects all three examples.

## 2. A nonnegative defect that avoids cancellation

For a prefix t in [0,N], define

    D_e(t) = sum_{0<=i<t, u_e(i)=1} (m_e(i)-1)^2
             + sum_{0<=i<t, u_e(i)=0} m_e(i).

Every summand is a nonnegative integer. The first is zero exactly for m=1,
the second exactly for m=0. D_e(t)=0 therefore means correctness at every
counter in the prefix. In particular D_e(N)=0 for every e is equivalent to
the desired invariant. D_e(0)=0, and each D_e is monotone in t.

Write B_e(t) for the number of desired inverse counters below t; T_e(t) for
the sum of all guarded row occurrences below t; C_e(t) for the sum of those
occurrences whose target is desired; and Q_e(t) for the sum, over unordered
pairs of *distinct row positions*, of the number of desired counters at which
both rows contribute. Then

    D_e(t) = B_e(t) + T_e(t) - 2 C_e(t) + 2 Q_e(t).       (1)

### Theorem 2: identity (1) is exact

At a fixed counter with multiplicity m, there are m contributing rows and
m(m-1)/2 contributing unordered pairs. Its contribution to the right-hand
side is u + m - 2um + 2u*m(m-1)/2. For u=0 this equals m. For u=1 it equals
1+m-2m+m(m-1)=(m-1)^2. Summing proves (1).

The second factorial-moment identity is elementary; it is not claimed as a
new general theorem. Its role is to make overlap and omission unable to
cancel. A mass-only check accepts multiplicities [2,1,1,0] on four desired
counters because the mass and desired cardinality both equal four. The
correct defect is two. Omitting the pair term from (1) gives zero for this
same fault. Requiring raw counter disjointness instead is sound with suitable
coverage and guards, but unnecessarily rejects the three examples above.

## 3. Counting intersections of modular rows

A row's counter set restricted to a prefix is a bounded arithmetic
progression. For lower bound L=l, upper bound H=min(h,t), its first element is
f=L+(rho-L) mod s and its length is max(0,1+floor((H-1-f)/s)).

For two rows, put L=max(l1,l2), H=min(h1,h2,t), g=gcd(s1,s2), and
Delta=rho2-rho1. The intersection is empty if L>=H or g does not divide
Delta. Otherwise let q=s2/g. If q=1 choose k=0. If q>1 choose

    k = (Delta/g) * inverse(s1/g modulo q) modulo q,
    d = s1*q,
    rho = (rho1+s1*k) modulo d.

The bounded intersection has first element L+(rho-L) mod d and the same
length formula with d replacing s. The inverse exists because s1/g and q
are coprime.

### Lemma 3: this construction gives exactly the intersection

Any common solution i=rho1+s1*z must satisfy s1*z=Delta modulo s2. Divisibility
by g is necessary. After division by g, the inverse gives the unique z modulo
q, so the resulting i is unique modulo d=lcm(s1,s2). Conversely substitution
satisfies both original congruences. Taking its least representative at least
L and stopping below H gives exactly all bounded solutions. Empty ranges
are handled before any mask counting.

Only one-row and two-row intersections are needed for (1). There is no
least-common-multiple construction involving every shard. Different old and
new shard moduli can coexist. In particular all residues modulo s1 on
[0,c), followed by all residues modulo s2 on [c,N), are an exact unguarded
partition regardless of whether either shard count divides N. Guarding each
row by U yields a safe continuation. This is a declared-prefix theorem, not
proof that the declared prefix was physically completed.

## 4. Masked progression counts

Let an arithmetic progression be i_j=f+d*j for 0<=j<z, and suppose all its
members belong to [0,N). Write alpha=a*d and beta=a*f+b. Define

    F(z,m,alpha,beta)=sum_{j=0}^{z-1} floor((alpha*j+beta)/m),

for z,alpha,beta>=0 and m>0. For a target interval [u,v) contained in [0,N),
the number of progression elements mapped into it is

    F(z,N,alpha,beta+N-u) - F(z,N,alpha,beta+N-v).       (2)

### Lemma 4: formula (2) is exact

Write alpha*j+beta=qN+r with 0<=r<N. For any endpoint c in [0,N],
floor((alpha*j+beta+N-c)/N)=q+1_{r>=c}. The difference for c=u and c=v is
one exactly when u<=r<v and is otherwise zero. Sum over j. Disjoint interval
masks are handled by summing (2), with no double counting. An empty mask or
zero-length progression contributes zero. A full mask [0,N) contributes z
without requiring a floor transcript. The producer and checker reconstruct
these shortcuts from the input rather than trusting a shortcut assertion.

### Lemma 5: Euclidean recurrence and its proof

Normalize alpha=q_a*m+a0 and beta=q_b*m+b0 with 0<=a0,b0<m. Removing the
quotients contributes q_a*z(z-1)/2+q_b*z. Set

    h=floor((a0*z+b0)/m), r=(a0*z+b0) mod m.

If h=0, the remaining sum is zero. Otherwise a0>0 and

    F(z,m,a0,b0)=F(h,a0,m,r).                          (3)

To prove (3), count the positive horizontal integer levels below the values
(a0*j+b0)/m. For each level q=1,...,h, the number of j in [0,z) with
m*q<=a0*j+b0 is z-ceil((m*q-b0)/a0). It is nonnegative: the last candidate
level is at most the value at j=z; if equality holds it contributes zero.
No larger level contributes. Substitute q=h-k with k in [0,h). Since
m*h=a0*z+b0-r, this number becomes floor((r+m*k)/a0). Summing over k proves
(3). For h=0 all a0*j+b0<m because j<z, also covering z=0.

Each nonterminal step replaces modulus m by a0, and the next remainder is
m mod a0. Every two nonterminal modulus reductions at least halve the old
modulus. Thus there are O(log(m+1)) steps, with a terminal step even for m=1.
The recurrences are exact integer equalities, not floating-point estimates.

## 5. Transcript checking and completeness boundary

For each floor query the untrusted producer provides a claimed value and a
sequence of triples (q_a,q_b,h). The checker knows the initial z,m,alpha,beta
because it reconstructs every query from the declaration, plan and prefix.
At each triple it verifies

    0 <= alpha-q_a*m < m,
    0 <= beta-q_b*m < m,
    0 <= (alpha-q_a*m)*z+(beta-q_b*m)-h*m < m.

It accumulates q_a*z(z-1)/2+q_b*z. A zero h is permitted only at the last
triple and only when this accumulated value equals the claimed value.
Otherwise the next state is (h,alpha-q_a*m,m,remainder). The checker rejects
missing, malformed, excessive, nonterminal or trailing records. It separately
computes interval intersections, generalized CRT intersections and (1).

### Theorem 6: soundness and mathematical completeness

The quotient inequalities uniquely determine each Euclidean quotient and
remainder. Lemma 5 therefore proves inductively that every accepted floor
value is correct. Lemmas 3 and 4 establish every queried row or pair count.
Theorem 2 establishes every reconstructed D_e(t). Consequently a successfully
verified certificate that reports all zero defects at t=N proves the target
invariant of Lemma 1. An arbitrary producer cannot make an unsafe input pass
as safe merely by changing numerical transcript records.

Conversely, Euclidean division constructs a finite valid transcript for
every required floor query. The producer's exact queries and values satisfy
all mathematical checking rules. Thus the unrestricted mathematical format
can establish the true defect of every well-formed affine plan, including
unsafe plans. A certificate for an unsafe plan may be a perfectly valid
certificate; that is not an acceptance of the plan.

The Python implementation additionally admits only N<=2^32, step<=64,
<=16 epochs, <=128 total rows, <=1024 intervals per supplied list, <=8 MiB
per input JSON file, <=64 MiB per certificate and <=68 triples per floor
query. Those are resource/format bounds, not the mathematical language.
Completeness of the *bounded implementation* is conditional on the produced
transcripts fitting all bounds. An admitted plan is not promised to have a
certificate below 64 MiB. Exhausting a resource limit is not a coverage
counterexample. Canonical input interval lists are sorted, disjoint and
nonadjacent; allow-minus-exclude may internally have more intervals than
either original list.

Within the numeric input bounds, all positive queried progressions remain
inside [0,N). An individual summand of F is below N+2; there are at most N
summands, so 128-bit value bounds are conservative. Initial alpha can exceed
32 bits and beta can approach 64 bits. Every two Euclidean reductions halve
the modulus, giving at most 65 steps for initial m<=2^32; 68 is conservative.
Python uses arbitrary precision, not a claim that unchecked 32-bit or 64-bit
arithmetic is safe.

### Complexity and trust boundary

For one epoch with K rows and interval-list complexity at most E after the
needed mask operations, there are O((1+K+K^2)E) floor queries, each taking
O(log(N+1)) arithmetic steps for fixed step bound. The producer and checker
also spend time constructing masks. The implemented checker's endpoint
sweep sorts events, adding O(K^2 E log(E+1)) work in a worst case where all
pair lattices are nonempty. It skips mask work for empty pair lattices. The
producer uses two-pointer intersections. With variable step encodings, CRT
cost also depends on the bit lengths of those steps. Integer bit costs must
be charged; the arithmetic-operation bound is not a constant-word machine
bound. The counter domain is never enumerated by the symbolic checker.

A streamed certificate uses O(log(N+1)) temporary transcript words for the
current floor query plus the input and current masks. Total certificate size
is O((1+K+K^2)E log(N+1)) words before finite encoding caps. The bound is
polynomial in input dimensions, not independent of input size. No
asymptotic advantage over recomputing the same symbolic counts is claimed.
The checker's value is an auditable, separate implementation and explicit
numerical evidence, not a smaller proven trusted kernel.

The two arithmetic implementations share the JSON/schema parser, Python
integer semantics and interpreter. Neither has been mechanized. The trusted
declaration, filesystem selection of that declaration and input immutability
remain assumptions. Replaying a valid certificate against the same input
produces the same result. This is not a cryptographic commitment, signature,
remote attestation, authorization decision or physical execution receipt.

## 6. Least canonical witness

Order faults lexicographically by (epoch,counter). A local witness contains
that epoch, counter and target, the fault kind, and either no row index for
an omission, the first row index for a forbidden emission, or the first two
row indices for a collision. Indices refer to the original concatenated
history-plus-future list, not a sorted or deduplicated list.

### Theorem 7: sound minimality check

Use a full certificate to establish that e is the first epoch with D_e(N)>0.
For candidate counter x, use two further certificates establishing D_e(x)=0
and D_e(x+1)>0. Since every summand is nonnegative, all counters before x
are correct and counter x is defective. Check its target directly and inspect
all rows to reconstruct its local multiplicity and prescribed row indices.
No earlier epoch or counter can be defective. These conditions therefore
prove both a fault and leastness in the specified order.

A producer finds x by binary search because D_e(0)=0, D_e(N)>0 and D_e is
monotone. Maintain low with D_e(low)=0 and high with D_e(high)>0. Updating at
the midpoint preserves the invariant. Termination with high=low+1 yields
x=low. This requires O(log(N+1)) prefix evaluations. The verifier needs only
the full, before and through certificates, not the binary-search history.

This is not the minimum numeric target, the first event in real time, a
minimum number of faulty rows, or the shortest physical execution trace.
Changing the canonical ordering changes the minimality claim.

## 7. Why a circuit-defined Feistel extension is not automatic

The following is a statement about a uniform, unbounded family, not about
the deployed security of a specific Feistel cipher or the fixed 32-bit
implementation limit.

Let f be an arbitrary Boolean circuit on w>=1 input bits. Put B=2^w and
N=B^2, and encode counters x=L*B+R for 0<=L,R<B. Define the w-bit function
F(R)=f(R)*2^(w-1). One Feistel round with F followed by one with the zero
function maps

    (L,R) -> (R,L xor F(R)) -> (L xor F(R),R).

Each round is invertible; the composite is therefore a permutation. Take
the desired target interval U=[N/2,N), and a single counter row [B,N) with
step one and guard U. It omits exactly the source block L=0 and has no
other gaps or duplicates.

### Theorem 8: exact relation to circuit unsatisfiability and counting

For each R, the omitted input (0,R) maps to (F(R),R). Its target belongs to
U exactly when the top bit of F(R) is one, namely when f(R)=1. Injectivity
ensures these targets are distinct and cannot be emitted from a different
source. Every desired target whose inverse source is outside the omitted
block is emitted once. No undesired target is emitted because of the guard.
Thus the plan is safe if and only if f is unsatisfiable, and the number of
omitted desired targets equals the number of satisfying assignments of f.

The descriptions of the two rounds, two interval endpoints, one row and
one guard have size polynomial in the circuit description and w. Therefore
any uniform polynomial-size, polynomial-time-checkable, sound and complete
certificate scheme for safety for this family would yield such a scheme for
arbitrary Boolean-circuit unsatisfiability by applying it to the construction.
This is an implication, not a proof that such a certificate scheme is
impossible and not a proof of a complexity-class separation. It does refute
the inference that efficient invertibility alone establishes the same easy
masked interval counting used for affine maps. The construction establishes
no difficulty result for a particular fixed round function, pseudorandom
round family, cycle-walked cipher or small fixed domain.

The exhaustive finite test covers all 4, 16 and 256 truth tables for w=1,2,3,
respectively, checking every domain point for each. These 276 cases validate
the construction's implementation; they do not replace this general proof.

## 8. What has and has not been established

The mathematical statements above cover fixed affine context, interval
policies, masked mixed-modulus row fragments, declared history, separate
retry epochs, sound numerical transcripts and least canonical witnesses.
They do not establish a new general counting principle. The proof of the
Feistel obstruction is complete for its stated circuit-defined family.

The validation suite compares the producer, checker, direct counter oracle
and independently target-indexed replay oracle on generated finite plans.
Arithmetic and CRT components have their own exhaustive small oracles.
Malformed-input checks and corruption controls are distinct from semantic
faults. One large interval-boundary run initially exceeded its time bound;
the scientific record retains this failure and the empty-intersection repair.
After repair the same case and a 2^20 exact-oracle case complete within the
configured bounds. No live scanner input, operational scan, model service,
network device, human study or externally executed campaign is involved.

Research novelty, a complete closest-work comparison and the journal-native
calibration remain unresolved. This is reusable technical evidence, not a
completed TDSC research paper or an independent review of the proof.
