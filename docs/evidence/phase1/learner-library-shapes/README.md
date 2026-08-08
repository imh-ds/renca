# Which relationship shapes can the learner library actually see?

Exploratory local runs, 2026-08-06. Not a calibrated study: 40–150 replications per cell,
`n=300`, `delta=0.05`, single directional estimate, true `Theta = 0.05` in every cell so
recovery is directly comparable across shapes.

Reproduce with `shape_test.py` (recovery by shape) and `library_test.py` (library
comparison, raw output in `library_test_results.parquet`). Both run the real
`fit_crossfitted_vimp`; the library variants change only `VimpSpec` fields and the degree
of the existing polynomial member, so nothing here is a parallel implementation.

## Why this was run

The threshold study found false pruning exceeding `alpha` when the added variable's
contribution could not be represented by the learner library. The obvious next question is
which shapes that actually covers, and whether the affected shapes matter in behavioural
research.

## Finding 1 — recovery tracks representability, not wiggliness

Median `theta_hat` as a share of the true 0.05, current library:

| shape | turning points | share of shape in span of {x, x²} | recovered |
|---|---|---|---|
| linear | 0 | 100% | 98% |
| exponential decay | 0 | 87% | 57% |
| parabola | 1 | 100% | 73% |
| **cubic** | **2** | **0%** | **−4%** |
| sin(1x) | 2 | 85% | 83% |
| sin(2x) | 4 | 15% | 21% |
| sin(4x) | 8 | 0% | 2% |

The third and fourth columns correspond closely; turning points do not predict anything.
A cubic and `sin(1x)` both have two turns, but `sin(1x)` is ~85% linear over the data range
while a cubic in Hermite form is orthogonal to both `x` and `x²` by construction. It is the
one shape the parametric members cannot express at all.

**This matters because cubic associations are within the normal range of social and
behavioural research.** The blind spot is not exotic.

## Finding 2 — a larger forest does not fix it

| library | linear | parabola | cubic | sin(2x) | se vs current | compute |
|---|---|---|---|---|---|---|
| current: degree 2, 10 trees depth 5 | 102% | 77% | **−4%** | 23% | 100% | 1.0x |
| degree 3, 10 trees depth 5 | 104% | 53% | **47%** | 32% | 111% | 1.2x |
| degree 2, **200 trees depth 15** | 101% | 82% | **−8%** | 34% | 109% | **11.1x** |
| degree 3, 200 trees depth 15 | 104% | 55% | 45% | 45% | 113% | 10.7x |

Two hundred deep trees recover **−8%** of a cubic, no better than ten shallow ones, at
eleven times the compute. Forests approximate curves with flat steps and need many splits
in sparse regions to trace a smooth cubic tail; with 240 training rows those points do not
exist. At this sample size non-parametric flexibility is not a substitute for the correct
parametric form.

The compute figure is not incidental. Eleven times would take a Phase-0 run from roughly
45 minutes to about eight hours.

## Finding 3 — replacing degree 2 with degree 3 trades one shape for another

Moving the polynomial member from degree 2 to degree 3 fixed the cubic (−4% to 47%) and
degraded the parabola (77% to 53%).

Degree 3 does include the squared terms; nothing is skipped. The cause is regularisation.
On two variables, degree 3 produces nine features against five for degree 2, and a fixed
ridge penalty spread across more correlated columns shrinks the squared coefficient
harder. The parabola is still representable, just estimated less precisely.

The implied design is to **add** a degree-3 member rather than substitute it, leaving the
cross-validated blend to choose.

## Finding 4 — adding the member works; substituting was the error

`v4_cubic_blend` offers ridge, quadratic, cubic and forest. Raw output in
`v4_test_results.parquet`, produced by `v4_test.py`.

| library | linear | parabola | cubic | sin(2x) | se vs v3 | compute |
|---|---|---|---|---|---|---|
| v3, three members | 102% | 77% | **-4%** | 23% | 100% | 1.0x |
| **v4, cubic added** | 106% | **78%** | **46%** | 34% | **119%** | 1.4x |
| degree 2 *replaced* by degree 3 | 104% | **53%** | 47% | 32% | 111% | 1.2x |

Adding recovers the cubic without the parabola cost that substituting incurred, confirming
the regression came from removing the pure-quadratic option rather than from the cubic
terms themselves.

Median blend weights select by shape: a parabola takes quadratic 0.744 and cubic 0.000, a
cubic takes cubic 0.546 and quadratic 0.000. This is a distribution, not a rule. Individual
datasets sometimes fit a parabola with the cubic member, unsurprising since a cubic basis
contains the quadratic one, so recovered `theta` rather than the weights is the stable
property.

The precision cost is **19%** on the standard error, above the 5-12% predicted before the
run. Whether that reduces power overall cannot be read from this table: a library that
represents cubics should also shrink the bias-driven left tail that currently sets the
critical value, which pushes the other way. Only a recalibration settles it.

## Status

Exploratory. Replication counts are small, this is a single directional test rather than a
network, and no calibration was rerun. Any library change alters `vimp_fingerprint` and
requires a fresh Phase-0 run before it can certify anything.
