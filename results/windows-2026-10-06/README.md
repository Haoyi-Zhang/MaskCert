# Current Windows measurements: 2026-10-06

This is the current measurement directory for the 64-command P100 campaign.
It contains only that campaign's fresh outputs, exact benchmark/solver inputs,
and copied execution logs. The received historical Linux observations remain
at the parent `results/` paths; they were not overwritten or relabeled.

The campaign was run in an isolated current-source copy at
`repair_workspace/experiments/P100/artifact`. `execution.json` retains the actual
source output and Windows DLL paths, not rewritten delivery paths. Each of its
64 entries has real exit code 0 and an empty corresponding stderr log. This
means the experiment commands completed, not that all plans were safe or all
SMT decisions completed.

| Commands | Fresh scientific evidence |
| --- | --- |
| 0: finite native SMT validation | `smt-validation.json`: 48 decisions on 12 retained plans, 14 SAT / 34 UNSAT / 0 UNKNOWN; returned SAT counters checked directly |
| 1--20: update cases 00--19 | `update-bench/`: all 20 new plans are safe; full/update defects agree; six operations, five calibrated timed batches per operation |
| 21--23: split/remove/revoke | `transfer/`: defects 0 / 44,738,560 / 1,024; full, warm and cold routes agree; one warmup and three timed repetitions |
| 24--63: twenty full/reduced SMT pairs | `smt/`: 95 UNSAT / 5 timeout UNKNOWN full samples; 100 UNSAT reduced samples; warmups excluded from these totals |

`cases/` retains the fresh 20 update inputs, three transfer inputs, 40 benchmark
SMT formulas and 48 finite SMT formulas. The finite plan definitions are the
first 12 records of the unchanged parent `cases/updates.json`. Six transfer
JSONL files are actual fresh certificates. The old anchor certificate remains
`results/boundary-certificate.jsonl` outside this directory.

## Platform and interpretation

The host was Windows 11, CPython 3.12.14, with the upstream `z3-solver` Windows
amd64 package 5.1.0.0. All native samples report `Z3 5.1.0.0`. The library was
the explicitly selected Windows `libz3.dll`; the received Linux `libz3.so.4`
was not loaded. The installed distribution's `METADATA` and `WHEEL` are copied
under `z3-package-metadata/`, documenting its upstream project identity, MIT
license and Windows tag. The DLL itself is not redistributed here. This local
metadata is not an independent audit of a downloaded binary's supply chain.
Historical Linux solver measurements used Z3 4.13.3.0.

Each command had a 120-second parent wall timeout and finite format bounds.
No POSIX CPU/address-space/alarm/affinity controls applied, and no peak RSS
was measured; null RSS is unavailable, not zero. The raw CPU deltas show
15.625-ms quantization. Batched arithmetic times are normalized by their actual
iteration counts. Four single-solve reduced SMT configurations (05, 12--14)
have zero median CPU deltas but positive wall durations: they are below the
observed CPU timing resolution, not instantaneous solutions. Cross-platform
and cross-version timing changes are not causal speedup estimates.

At 120 rows, full/warm/cold arithmetic medians are
203.125 / 3.90625 / 218.75 ms. For edit size 64 they are
78.125 / 218.75 / 281.25 ms: a large warm update loses. The 32-row edit point
is no longer a near-equality (78.125 / 62.5 ms full/warm). Transfer warm medians
are 0.15625--0.203125 CPU seconds, versus 3.484375--3.5625 full and
3.734375--3.84375 cold. No Windows memory comparison is available.

SMT case 04 has full/reduced medians 1.03125 / 0.015625 CPU seconds. Case 19
reverses the historical ordering: 0.234375 / 0.34375 seconds, so reduced is
slower here as well as in specialized arithmetic. Case 09 full has five
unresolved timeout samples; its 10-second CPU median is not a completed solve.
CNF variable/clause sizes are unchanged and mean encoded, not counted or
proof-checked. No CPOG, d4/CD4, VeriPB or CakePB pipeline ran in this campaign.

Streaming transfer files use Windows CRLF line endings, whereas the retained
Linux files use LF. Their physical/checker-accounted byte sizes therefore
differ despite identical queries and mathematical contents. The current
transfer table reports the actual Windows sizes; in-memory update certificate
lengths use LF and match the retained values.

## Paper data

The three extension tables and fragment/edit plot CSVs in `paper/generated/`
select this directory explicitly. From the complete project root:

```sh
python artifact/scripts/export_extension_data.py --results artifact/results/windows-2026-10-06 --output paper/generated
```

Without `--results`, the exporter retains its historical Linux source. Original
boundary, pilot, failed-attempt and finite-validation observations were not
remeasured by this 64-command campaign. Solver UNSAT responses remain trusted,
not independently proof checked; exact finite agreement does not establish
general correctness or operational scanner behavior.
