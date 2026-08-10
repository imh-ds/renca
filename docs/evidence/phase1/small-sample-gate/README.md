# Small-sample gate — `delta = 0.20` needs about 300 rows, and one family decides it

GitHub Actions run
[31419437023](https://github.com/imh-ds/renca/actions/runs/31419437023), 2026-08-10, all 21
jobs successful. 600 replications per family per sample size, 12,000 fits, `delta = 0.20`,
v4 library at `forest_trees = 100`, 5 inference folds.

Step A of the recalibration. Psychology samples are commonly 100-200, and every number in the
evidence chain rests on `n = 375`, chosen only because it yields the 300 inference rows the old
profiles bind to. This asks whether `delta = 0.20` is reachable lower down, cheaply enough that
a negative answer costs a quarter of an hour rather than half a day.

**Verdict: not reachable below `n = 300`. Do not spend Phase-0 cycles at 100, 150 or 200 for
this resolution.**

## What decides it

Certification requires

    standard error <= delta / |critical value|

so the *resolution floor*, `|critical value| x se`, is the finest `delta` a pair whose estimate
is exactly zero could reach. A floor above `delta` means certification is impossible at that
resolution whatever the truth is.

| n | critical value | tolerated se | worst-family se | worst floor | families reachable | `delta = 0.20` reachable |
|---|---|---|---|---|---|---|
| 100 | -5.132 | 0.039 | 0.074 | 0.380 | 1 of 5 | no |
| 150 | -3.926 | 0.051 | 0.062 | 0.243 | 3 of 5 | no |
| 200 | -4.339 | 0.046 | 0.055 | 0.240 | 4 of 5 | no |
| 300 | -3.386 | 0.059 | 0.046 | 0.155 | 5 of 5 | **yes** |

Abstention was zero everywhere: the estimator returns usable estimates at `n = 100`, it just
cannot resolve finely enough to certify.

**The control rung passed.** The miniature estimates `-3.386` at `n = 300` against the shipped
profile's `-3.084` — about 10% more extreme, which is the expected direction for a quantile
read from 600 replications rather than 6,000. That agreement is what licenses reading the other
three rungs; it also means the small-`n` numbers are, if anything, mildly conservative.

**The ordering between 150 and 200 is noise.** At 600 replications the 4% quantile is the 24th
smallest observation, so `-3.926` against `-4.339` should not be read as `n = 150` being better
than `n = 200`. The trend across the four rungs is what carries.

## The mechanism is bias, not just noise

Median `theta_hat` minus the true 0.20, at the boundary:

| family | n=100 | n=150 | n=200 | n=300 |
|---|---|---|---|---|
| continuous_linear_boundary_v1 | 0.000 | -0.004 | -0.002 | 0.000 |
| bounded_composite_unsaturated_v1 | 0.007 | 0.005 | 0.002 | 0.002 |
| bounded_composite_saturated_v1 | 0.017 | 0.019 | 0.013 | 0.009 |
| nonlinear_continuous_v1 | -0.032 | -0.023 | -0.026 | -0.014 |
| **learner_misspecification_v1** | **-0.072** | **-0.046** | **-0.029** | **-0.019** |

The linear family is unbiased at every sample size. The two families whose signal is carried by
a shape the learner has to *find* are biased downward, and the bias grows sharply as the sample
shrinks.

That is the whole story. A downward bias at the boundary pushes the studentized statistic
negative, and the critical value must move further out to hold the rejection rate at 4%. So a
small sample costs twice: a larger standard error *and* a more extreme critical value, and the
resolution floor multiplies the two.

The underlying cause is worth stating plainly for a write-up: **at small `n` a learnable shape
becomes effectively unlearnable.** `learner_misspecification_v1` is
`y = signal * (z*x + x**2 - 1) + error`, an interaction plus a quadratic, both of which
`quadratic_ridge` represents exactly. Nothing about the shape is beyond the library. There is
simply not enough data to fit it, so the expanded model underfits, `theta_hat` collapses toward
zero, and the same failure mode the threshold study documented for genuinely unlearnable
variables reappears from sample size alone.

## One family decides everything

Recomputing with `learner_misspecification_v1` excluded from coverage:

| n | critical value | worst se | worst floor | `delta = 0.20` reachable |
|---|---|---|---|---|
| 100 | -2.689 | 0.067 | 0.181 | yes |
| 150 | -2.549 | 0.054 | 0.137 | yes |
| 200 | -2.525 | 0.044 | 0.112 | yes |
| 300 | -2.603 | 0.036 | 0.093 | yes |

Every sample size clears. The entire small-sample obstacle is a single scenario family, and it
is the one representing an interaction — a shape behavioural research cares about a great deal.

This is not a recommendation to drop it. It is a statement of what the guarantee costs: the
sample-size requirement is the price of covering interaction-carried relationships, and the
coverage boundary is now a measured quantity rather than an assumption.

## What this rules in and out

* **Do not run Phase-0 at 100, 150 or 200 for `delta = 0.20`.** The floors say it cannot work,
  and a full calibration would spend half a day confirming it.
* **`n = 300` inference rows works**, and a profile already exists there.
* **A coarser `delta` at `n = 200` would need to be about 0.25**, since the floor there is
  0.240. At `n = 100` it would need about 0.38, which is vacuous for behavioural data.
* **A smaller learner library is untested and plausible.** At `n = 100` the blend estimates
  weights for four members by 3-fold inner cross-validation on 80 rows. Selection noise on that
  little data is a known source of downward bias in nested comparisons, so a two-member library
  might be *less* biased at small `n` despite being less expressive. That is cheap to test and
  is the only untried lever that could move the coverage boundary rather than accept it.

## Limitations

* **Not a calibration.** 600 replications per family against the 5,000 the registry gate
  requires; no profile is produced and none of these critical values may be used.
* **Quantile noise.** The 4% quantile of 600 observations is the 24th smallest. Differences
  between adjacent rungs of 10-20% are within noise.
* **The critical value depends on `delta`.** These were all measured at `delta = 0.20`, so the
  coarser-`delta` figures above are extrapolations, not measurements.
* **One library and one fold count.** `v4_cubic_blend` at `forest_trees = 100` and 5 inference
  folds throughout, matching the shipped profiles.

## Reproduce

```bash
gh workflow run small-sample-gate.yml --ref main
```
