# Section 13.4 comparator gate — REDESIGN

GitHub Actions run
[31282474806](https://github.com/imh-ds/renca/actions/runs/31282474806), 2026-08-08, all 21
jobs successful. 400 replications: `p=15`, `n=375`, degree `<=3`, `max_separator_size=1`,
v4 library, the three calibrated resolutions, against PC, conservative PC, FCI, GES and
EBICglasso swept over their tuning parameters. Every method sees the same rows.

**Verdict: `REDESIGN`, identical under both scorings.** 0 of 12 regions passed. The
programme is not falsified -- section 44 criterion 3 is survived in the nonlinear
conditions -- but no operating region is simultaneously safe and useful.

## The gate result

| family | edges | delta | true prune | false prune | familywise error |
|---|---|---|---|---|---|
| linear_gaussian | realistic | 0.05 | 0.013 | 0.000 | 0.00 |
| linear_gaussian | realistic | 0.10 | 0.155 | 0.002 | 0.02 |
| linear_gaussian | realistic | 0.20 | 0.878 | 0.046 | 0.32 |
| linear_gaussian | strong | 0.05 | 0.058 | 0.002 | 0.03 |
| linear_gaussian | strong | 0.10 | 0.237 | 0.025 | 0.34 |
| linear_gaussian | strong | 0.20 | 0.900 | **0.157** | 0.91 |
| additive_nonlinear | realistic | 0.05 | 0.005 | 0.000 | 0.00 |
| additive_nonlinear | realistic | 0.10 | 0.091 | 0.000 | 0.00 |
| additive_nonlinear | realistic | 0.20 | 0.767 | 0.015 | 0.13 |
| additive_nonlinear | strong | 0.05 | 0.018 | 0.000 | 0.00 |
| additive_nonlinear | strong | 0.10 | 0.108 | 0.002 | 0.03 |
| additive_nonlinear | strong | 0.20 | 0.657 | 0.049 | 0.52 |

Rates are practical-at-delta; the graphical column is in the CSV and tells the same story.

**Every region that prunes usefully fails familywise control, and every region that
controls error prunes almost nothing.** That, not any single rate, is what fails the gate.

## Where the method wins, and it is not small

`additive_nonlinear`, `strong`, `delta = 0.20`:

| method | true prune | false prune |
|---|---|---|
| **renca** | **0.657** | **0.049** |
| PC (0.20) | 0.888 | 0.267 |
| FCI (0.20) | 0.921 | 0.281 |
| GES (0.5) | 0.929 | 0.279 |
| EBICglasso (0) | 0.761 | 0.235 |

Every baseline deletes roughly three in ten real edges, because a cubic edge carries zero
partial correlation and a covariance-based test cannot see it. This method's error is five
to seven times lower at two-thirds of the pruning. That is the design working, and it is
why the verdict is `REDESIGN` rather than `STOP`.

## Where it loses, on the baselines' home turf

`linear_gaussian`, `strong`, `delta = 0.20`:

| method | true prune | false prune |
|---|---|---|
| **renca** | 0.900 | **0.157** |
| GES (0.5) | 0.946 | 0.010 |
| PC (0.20) | 0.872 | 0.028 |
| EBICglasso (0) | 0.645 | 0.001 |

GES prunes *more* at a fifteenth of the error. Here the method is the worst of the six, on
the condition most favourable to everyone.

## Why: the separator search aims at the quantity the test measures

Section 15.4 ranks candidate separators by **minimising** cross-fitted bidirectional gain --
the same quantity the equivalence test then evaluates. For a genuinely adjacent pair that is
an active search for the conditioning set under which the pair looks most separated.

Two diagnostics, `linear_gaussian` / `strong`, oracle values so nothing is sampling noise.

**The certificates are true statements.** Of 708 real edges, 626 carry `Theta > 0.20` given
the true parent set, but only 226 do given the separator the method actually chose. The
chosen separator drives 400 real edges under the threshold *in the population*. So these are
not test failures and not miscalibration -- they stay true with infinite data. What is wrong
is rendering them as a missing edge in a graph.

**It is not confined to weak edges.** Bucketing 356 real edges by their true strength:

| true strength (given parents) | n | mean strength given chosen S | share pushed below 0.20 |
|---|---|---|---|
| <= 0.20 | 45 | 0.087 | 0.889 |
| 0.20-0.30 | 53 | 0.094 | 0.906 |
| 0.30-0.40 | 65 | 0.128 | 0.800 |
| 0.40-0.60 | 86 | 0.171 | 0.709 |
| > 0.60 | 107 | 0.237 | **0.421** |

Edges explaining 71% of predictable variance given their true parents are suppressed to a
mean of 0.24, and pushed under 0.20 in 42% of cases. Suppression falls with strength but
never approaches zero, so this is not the practical estimand quietly absorbing near-threshold
edges -- the search is manufacturing separation at every effect size.

Note the direction of the effect. A poor or empty conditioning set would leave a *larger*
association, since it retains indirect paths. Systematically smaller values are evidence of
selection, not of a mis-specified contrast.

**What the mechanism is not.** The first hypothesis -- that the suppressing separator is a
redundant correlate of an endpoint -- does not survive. Among 267 edges, a separator adjacent
to an endpoint occurred in 86.6% of suppressed cases and 85.2% of non-suppressed ones, which
is no difference at all; screening selects neighbours either way. Mean correlation with the
nearer endpoint differed only 0.65 to 0.74. Which separators suppress, and why, is still
open.

## What this rules out

Recalibration, a finer `delta`, a different critical quantile, and a larger selection split
all leave a population-level fact untouched. The candidates that remain are structural:

1. **Rank separators on something other than the tested quantity** -- validity or
   admissibility rather than smallness of the effect.
2. **Require the claim across several separators** rather than the one that flatters it most.
3. **Narrow the certificate** to incremental predictive value given a stated conditioning
   set, and stop drawing it as a graph edge. Honest, but it concedes the output is not a
   network.

## Limitations

* **One sample size.** `n=375` is the only size with a validated profile, so the comparison
  cannot show how the gap moves with `n`. The baselines were not given a matching handicap.
* **`max_separator_size=1`**, matching the calibrated configuration. Larger separators cost
  27x the ranking compute at this `p` and were not run; whether they reduce or worsen
  suppression is untested and matters, since a larger candidate pool is a wider search.
* **No baseline controls familywise error either** (PC 0.34-1.00, GES 0.15-1.00 in the same
  cells). Over ~86 simultaneous pairs it is a severe standard. Only this method claims it,
  so only this method is held to it -- but the column should not be read as a clean contrast.
* **The nonlinear condition has non-Gaussian marginals** by construction, so Fisher-z is
  misspecified there in two ways at once. Unavoidable if the dependence is to be nonlinear
  at all; the linear condition is the clean head-to-head.

## Reproduce

```bash
gh workflow run comparator-gate.yml --ref main
```
