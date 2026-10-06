# Transfer of update evaluation to the retained large instance

The twenty guard-partition inputs deliberately make source intervals overlap;
they are a stress family, not a production workload. To avoid presenting that
family as representative, the following three transformations of the already
retained Table-III input are fixed before their runs: (1) split the first future
fragment at the midpoint of its source interval; (2) remove that future fragment;
(3) enlarge each excluded interval one target to the left without changing any
fragment. The expected properties are respectively safe, unsafe omission, and
unsafe forbidden output; the third defect is exactly 1024. Old history,
permutation, domain and 1024-interval guard design are not changed. Each case is
an additional transformation, not a replacement for the original observation.

For each case, verify the retained old certificate, generate/check the new full
and update certificate, and measure the full, warm-update and cold-update
checker paths. Use one warmup and three timed repetitions, deliberately fewer
than the small benchmark to fit the 110-second CPU limit. Do not pool these
repetitions with the twenty-input batch study. Preserve every input, certificate,
raw timing and resource observation. A native solver run on this 125-fragment,
1024-mask input is not assumed feasible and is not part of this protocol.
