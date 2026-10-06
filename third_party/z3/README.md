# Optional native SMT comparison dependency

Unmodified preinstalled Z3 4.13.3.0 shared library, Linux x86-64. Upstream:
https://github.com/Z3Prover/z3 ; C API: https://z3prover.github.io/api/html/group__capi.html
MIT license and Debian packaging notices are in COPYRIGHT. Acquired from the
working environment's /lib/x86_64-linux-gnu/libz3.so.4, not built or patched by
this project. No network download or external execution was involved. The
library is used only by the optional SMT safety baseline, not the checker or
arithmetic experiments. It is a trusted solver, not independently proof-checked.
On a different platform use an appropriately licensed system libz3 through the
adapter's explicit library argument; do not load an incompatible binary.
