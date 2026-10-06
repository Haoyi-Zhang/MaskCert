# Optional native SMT comparison dependency

This compact upload view does not redistribute a native Z3 binary. The optional
adapter in `src/pcs/smt_baseline.py` already accepts an explicit library path
or the `Z3_LIBRARY_PATH` environment variable. Extraction, core checking,
default Linux reproduction, and archived-result inspection require no Z3.

Use a platform-compatible library from the
[official Z3 releases](https://github.com/Z3Prover/z3/releases), or the
[upstream-recommended Python package](https://github.com/Z3Prover/z3#python).
The current Windows observations used `z3-solver` 5.1.0.0; its
[official package record](https://pypi.org/project/z3-solver/5.1.0.0/)
includes a Windows x86-64 wheel. An optional user-managed environment can install
that version with `python -m pip install z3-solver==5.1.0.0`. Nothing in this
artifact installs or fetches it automatically. The Python package itself is not
imported by the adapter; select the shared library it supplies.

For example, find the package's native-library directory with:

```sh
python -c "from pathlib import Path; import z3; print(Path(z3.__file__).resolve().parent / 'lib')"
```

On Windows set the full path to the matching `libz3.dll` in PowerShell:

```powershell
$env:Z3_LIBRARY_PATH = 'C:/absolute/path/to/z3/lib/libz3.dll'
```

On Linux select the actual library from the compatible official installation:

```sh
export Z3_LIBRARY_PATH=/absolute/path/to/libz3.so
python scripts/prepare_data.py
python scripts/reproduce.py --smt
```

The experiment scripts already pass through this environment choice to
`Z3Session()`. The Linux resource-bounded reproduction driver is not a Windows
driver. For Windows experiment runners use the separately supplied complete
project workflow; this compact view retains all its saved observations.
Record the actual version on a fresh run; a different version or platform does
not reproduce the old timing distribution. SMT is a trusted safety-decision
baseline, not a certified model counter or an independently proof-checked solver.

## Historical binary provenance and notices

The received artifact included an unmodified preinstalled Z3 4.13.3.0 shared
library, Linux x86-64, acquired from that environment's
`/lib/x86_64-linux-gnu/libz3.so.4`. It was not built or patched by this project;
its original acquisition involved no network download. That binary remains in
the untouched source candidate but is omitted here, not replaced with a DLL.
The preserved `COPYRIGHT` records its MIT license and Debian packaging notices.
Upstream: [Z3](https://github.com/Z3Prover/z3);
[C API](https://z3prover.github.io/api/html/group__capi.html).
