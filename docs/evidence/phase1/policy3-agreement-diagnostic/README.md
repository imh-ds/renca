# Separator-agreement diagnostic — population ceiling

Asks one question about the failure the [section 13.4 comparator gate](../comparator-gate/README.md)
established: if a pair were declared separated only when the **top `k`** ranked candidate
separators *all* separate it, rather than the single one that flatters it most, how much of
the suppression goes away, and what does it cost?

**Status: diagnostic only.** This is not an approved design, nothing here is implemented, and
the packaged calibration profiles do not transfer to it. Recorded so the question does not
have to be re-asked.

## What was run

No new simulation. Each graph is rebuilt from the `replicate` seed already recorded in
`comparator-gate/comparator_gate_results.parquet`, and every quantity is exact oracle `Theta`
for the `linear_gaussian` family — no sampling, no estimator, no test. 200 replications per
edge strength, `p=15`.

The candidate pool is the empty set plus each of the other 13 variables, ranked by
*minimising* cross-fitted bidirectional gain exactly as section 15.4 specifies. This is not a
widened search: `benchmark_project_spec` sets `max_neighbors = p - 1`, so it is the pool the
gate itself ranked over.

**Every rate below is a ceiling.** It describes infinite data. The finite-sample rule must
also clear the calibrated equivalence test, which is strictly more conservative, so a real run
prunes less than this on *both* sides. Levels are not comparable to the gate's observed rates;
only the movement across `k` is informative.

## The trade

`k=1` is the current policy. Full table in `policy3_agreement.csv`.

| edge strength | delta | k | true prune | false prune | familywise |
|---|---|---|---|---|---|
| strong | 0.20 | 1 | 0.999 | **0.664** | 1.00 |
| strong | 0.20 | 3 | 0.954 | 0.224 | 0.97 |
| strong | 0.20 | 5 | 0.897 | **0.100** | 0.73 |
| strong | 0.05 | 1 | 0.988 | 0.150 | 0.90 |
| strong | 0.05 | 5 | 0.717 | 0.018 | 0.26 |
| realistic | 0.20 | 1 | 1.000 | 0.518 | 1.00 |
| realistic | 0.20 | 5 | 0.981 | 0.069 | 0.39 |

At `delta = 0.20` the false-prune ceiling falls by roughly six-sevenths for a tenth of the
pruning. The trade is worse at `delta = 0.05`, where agreement costs 27% of true prunes in the
`strong` condition.

## Why it works

A genuinely absent pair has *many* separators that work. A suppressed real edge usually has
exactly one — the one the search went and found. `policy3_separating_counts.csv`:

| edge strength | delta | pair class | mean candidates that separate | share with >= 5 |
|---|---|---|---|---|
| strong | 0.20 | practically absent | 12.11 | 0.898 |
| strong | 0.20 | practically present | 1.93 | 0.103 |
| strong | 0.05 | practically absent | 9.61 | 0.719 |
| strong | 0.05 | practically present | 0.37 | 0.018 |

Agreement keys on that asymmetry directly, which is why it is not simply a stricter threshold.

## It protects the edges the failure destroyed

`linear_gaussian` / `strong` / `delta = 0.20`, the gate's worst cell. Adjacent pairs bucketed
by true strength given their own parents; the entries are the share wrongly declared a nonedge
(`policy3_by_strength.csv`).

| true strength | edges | k=1 | k=2 | k=3 | k=5 |
|---|---|---|---|---|---|
| <= 0.20 | 196 | 0.949 | 0.776 | 0.628 | 0.510 |
| 0.20-0.30 | 286 | 0.867 | 0.689 | 0.486 | 0.238 |
| 0.30-0.40 | 306 | 0.788 | 0.520 | 0.307 | 0.085 |
| 0.40-0.60 | 447 | 0.676 | 0.347 | 0.186 | 0.107 |
| **> 0.60** | 498 | **0.460** | 0.147 | 0.056 | **0.022** |

The gate's central finding was that suppression is nearly flat across true strength — edges at
a mean `Theta` of 0.713 were driven under 0.20 in 42% of cases. Under agreement the gradient
returns: at `k=5` the strongest bucket falls to 0.022 while the weakest stays at 0.510, and
the weak column staying high is correct behaviour, since those edges genuinely are negligible
at this resolution.

## What it does not fix

Familywise error remains **0.73** at `delta = 0.20` and **0.26** at `delta = 0.05`, in the
population. Over ~86 simultaneous pairs a 2% per-pair error rate across ~15 real edges still
places at least one violation in most graphs.

Agreement shrinks the population counterexample. It does not remove it. Nothing here
rehabilitates a certified-nonedge claim, and the section 11 lifting clause — that direct
adjacencies retain bidirectional conditional importance above the thresholds for *every*
admissible separator — remains falsified.

## Limitations

* **`linear_gaussian` only.** The exact covariance makes the oracle free; `additive_nonlinear`
  would need Monte Carlo `Theta` per candidate set, which is roughly three orders of magnitude
  more compute for a diagnostic.
* **Ceiling, not a prediction.** See above. No statement here bounds a finite-sample rate.
* **Size-1 separators.** Matches the calibrated configuration and the gate. Whether agreement
  behaves the same over a larger pool is untested, and a larger pool is a wider search.
* **No diversity constraint.** The top `k` are taken by rank alone. They are distinct
  variables but may be near-duplicates of one another; a redundant top-`k` would give false
  comfort. The effect appears without needing the refinement, so the refinement was not tried.
* **Calibration does not transfer.** The decision becomes the maximum of `2k` dependent
  one-sided tests rather than 2. That is a different quantity from the one the profiles were
  validated against, and it would need its own Phase-0 calibration before any use.

## Prediction this refuted

The policy was proposed with power collapse named as its likely failure mode — that requiring
agreement would certify almost nothing. That is wrong. At `delta = 0.20` the true-prune ceiling
falls only from 0.999 to 0.897 between `k=1` and `k=5`. The binding limitation is the
familywise column, which the original proposal did not isolate.

## Reproduce

```bash
python docs/evidence/phase1/policy3-agreement-diagnostic/policy3_diagnostic.py
```
