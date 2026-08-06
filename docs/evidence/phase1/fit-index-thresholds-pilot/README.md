# Fit-index threshold study — local pilot (SUPERSEDED)

> **This pilot's headline reading is wrong.** It reported no relationship between
> predictive adequacy and false pruning. At 30,000 replications the relationship is
> monotone and increasing, and its upper bound exceeds `alpha` in the two highest
> adequacy cells when the added variable is unlearnable. See
> [`../fit-index-thresholds/`](../fit-index-thresholds/README.md). Retained only as the
> record of what 1,200 replications supported.


**Pilot only: 40 replications per cell, 1,200 total.** Cell-level rates rest on small
counts and the full run supersedes this. Retained because its two findings are large enough
to read at this size and they determine what the full run is for.

Produced locally on 2026-08-05 from `simulations/threshold_study.py`, 30 cells:
true adequacy in {0, 0.05, 0.15, 0.35, 0.60} x true Theta in {0, 0.02, 0.15} x learnability
in {both linear, added variable oscillatory}, at `n=300`, `delta=0.05`, under profile
`v3-nested-blend-n300-d005-phase0`. Only `Theta = 0.15` is a true edge, so certifying one
is a false prune.

## Finding 1 — predictive adequacy does not predict false pruning

| observed adequacy | false-prune rate | correct-prune rate |
|---|---|---|
| (-inf, 0.00] | 0.015 | 0.356 |
| (0.00, 0.02] | 0.000 | 0.383 |
| (0.02, 0.05] | 0.000 | 0.468 |
| (0.05, 0.10] | 0.000 | 0.556 |
| (0.10, 0.20] | 0.030 | 0.540 |
| (0.20, 0.40] | 0.000 | 0.654 |
| (0.40, inf] | 0.024 | 0.746 |

The false-prune column has no trend. **A safety cut-off on predictive adequacy would not be
supported by this evidence**, and imposing one would imply a protection the index does not
provide.

The correct-prune column is monotone, 0.356 to 0.746. Predictive adequacy is a **power**
indicator: it says how much of the structure the analysis can resolve, not whether the
result is trustworthy. That is a narrower claim than the index's framing suggested, and it
is the claim the evidence supports.

## Finding 2 — the index is blind to the failure that causes false prunes

| separator | added variable | median adequacy | median theta bias | false-prune rate |
|---|---|---|---|---|
| linear | linear | 0.1377 | -0.0030 | **0.000** |
| linear | oscillatory | 0.1385 | -0.0240 | **0.025** |

Adequacy is effectively identical across the two, while bias worsens eightfold and the
false-prune rate goes from zero to 2.5%.

This follows from the definition. Predictive adequacy is computed from the *reduced* model,
so it measures whether the **separator** is learnable. False pruning is driven by whether
the **added variable's** contribution is detectable, which the reduced model never sees.
The index cannot observe the quantity that matters for safety.

## What this implies

Distinguishing "the added variable does not matter" from "it matters but the library cannot
fit it" may not be possible from the data alone; specification section 16.4 already treats
learner adequacy as a diagnostic rather than something provable. Candidate partial signals
worth testing are whether nonlinear library members ever win anywhere in the analysis, and
whether that co-varies with bias. None is established here.

The observed false-prune rate stays below `alpha = 0.05` even in the oscillatory cells, so
nothing here contradicts the familywise result. But `Theta = 0.15` is three times `delta`,
so these are gross errors rather than boundary errors, and the scenario is outside the five
families the profile was validated on. The full run should quantify the rate precisely
rather than leave it at 5 events in 200 replications.

## Reproduce

```bash
python simulations/threshold_study.py shard --start 0 --count 40 --output out/shard-0.parquet
python simulations/threshold_study.py summarize --shards out --output threshold-study
```
