# Native SMT safety comparison

This archived Linux protocol was written after the update benchmarks and before
running the SMT comparison inputs. A library-discovery check found the preinstalled,
MIT-licensed Z3 4.13.3.0 shared library. A one-variable integer smoke test
succeeded. No claim about schedule instances follows from that smoke test.

The current Windows rerun is separate under `results/windows-2026-10-06/`.
It actually used the installed upstream `z3-solver` 5.1.0.0 Windows amd64
package's `libz3.dll`, explicitly selected by the campaign; every native sample
reports `Z3 5.1.0.0`. The installed package metadata and Windows wheel tag are
retained there. No received Linux binary was loaded or redistributed as Windows
code. The finite suite has 14 SAT / 34 UNSAT / 0 UNKNOWN on 48 queries. Timed
full/reduced results are 95 UNSAT + 5 timeout UNKNOWN / 100 UNSAT, excluding
warmups. Case 19 reduced is slower than full on Windows, reversing the archived
Linux ordering. OS and solver version changed together; this does not isolate
either as a causal factor. Windows had no POSIX CPU, memory, alarm or affinity
limits and no peak-RSS measurement. Its zero single-solve CPU medians are timing
resolution limits, not zero wall duration. These current results do not replace
the historical Linux observations described below.

The comparison uses unmodified native Z3 through its documented C API. The
translation uses mathematical integers, constant modular arithmetic, interval
membership, and sums of Boolean fragment indicators. It asks whether any
counter in an epoch disagrees with the desired multiplicity. This is a safety
DECISION baseline, not certified model counting or a proof-checked baseline.
A satisfiable answer will be validated at the returned counter using direct
fragment predicates. An unsatisfiable answer is trusted to Z3; no independent
Z3 proof checker is supplied or claimed.

The full formula contains all fragments. The reduced formula uses only removed
and added fragments and the old policy, conditional on the same fully verified
safe anchor as the arithmetic update. This isolates semantic elimination from
the downstream arithmetic backend. Default native solver settings are used,
with a 10,000 ms per-solve timeout and one thread; no solver option is tuned to
these inputs. There is one warmup and five fresh-context timed solves. Parsing,
solver initialization and solving are included; formula construction is reported
separately. The first 12 finite transition inputs are checked across all epochs,
followed by the same twenty guard-partition benchmark inputs. Counts of sat,
unsat, unknown, timeout, and rejected invalid models are reported separately.
All native output and exact SMT-LIB inputs are retained. Solver timeouts remain
unknown, never counted as safety failures or proof of an advantage.

The portable core remains Python-standard-library only. This optional baseline
needs the separately licensed native library. The retained Linux x86-64 binary
and its upstream license enable offline replay here, but do not imply portability
to other operating systems or architectures. No upstream source is modified.
