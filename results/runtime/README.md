# Arithmetic measurements

These records measure the ordered-endpoint implementation on Windows 11,
CPython 3.12.14, and an Intel Core i7-12700KF. `platform.json` records the
actual environment and measured source files. `execution.json` records all
23 command exits and wall durations; `logs/` retains both actual streams.

The campaign runs 20 fixed guard-partition inputs on six separate paths and
the three retained large-input transformations. All 23 command exits were
zero. Input objects match `cases/update-bench/` and `cases/transfer/`.
The three transfer defects are 0, 44,738,560 and 1,024. Timings are new
observations, not replacements for prior raw logs.

Factor sweeps use in-memory prepared transcripts, a per-operation batch
calibration to 50 ms CPU or 4,096 calls, one warmup batch and five retained
batches. Transfer checks stream prepared files, including opening, with one
warmup and three retained checks. Warm verification reuses an established
safe anchor. Cold verification includes checking the old base. Certificate
generation is a separately measured path, not part of a checker-stage time.

Children are sequential and have a 120-second outer wall bound. This
Windows run applied no POSIX CPU/memory/alarm/affinity limits and did not
measure peak RSS. CPU deltas are quantized in 15.625-ms increments; batching
reduces zero-resolution observations but does not remove shared-host
variation. A lower separately calibrated median is not itself a paired
end-to-end speedup. All observations, including losses and repeated grid
settings, are retained.

This campaign executes no native SMT, certified-counting backend, scanner
or network experiment. The separate Windows native SMT observations remain
under `results/windows-2026-10-06/`.

From the artifact root, regenerate the paper tables and plot CSVs with:

```sh
python -B scripts/export_extension_data.py --output ../paper/generated --results results/runtime --smt-results results/windows-2026-10-06
```

This export validates all 120 arithmetic timing summaries against their raw
five-batch samples. Figure rendering is a separate Python command in
`paper/figures/draw_evaluation.py`; it does not run an experiment.
