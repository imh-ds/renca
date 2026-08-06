# Fit-index threshold study — full run

30,000 replications from GitHub Actions run
[31058614760](https://github.com/imh-ds/renca/actions/runs/31058614760) on 2026-08-06,
20 shards x 50 replications x 30 cells, all 21 jobs successful, 18 minutes.

Supersedes [`../fit-index-thresholds-pilot/`](../fit-index-thresholds-pilot/README.md),
whose "no relationship between adequacy and false pruning" reading was an artefact of
1,200 replications and is **wrong**.

Design: `y = sqrt(A) g(z) + sqrt(T) h(x) + sqrt(1-A-T) e`, everything standardised, so
`R(empty) = 1` and true adequacy is exactly `A`, true Theta exactly `T`. Grid is
`A` in {0, 0.05, 0.15, 0.35, 0.60} x `T` in {0, 0.02, 0.15} x added variable in
{linear, oscillatory}, at `n=300`, `delta=0.05`, `alpha=0.05`, profile
`v3-nested-blend-n300-d005-phase0`. Only `T=0.15` is a true edge, so certifying one is a
false prune.

## Finding 1 — false pruning exceeds alpha when the added variable is unlearnable

Per-cell false-prune rate on true edges:

| true adequacy | added variable linear | added variable oscillatory | 95% upper (oscillatory) |
|---|---|---|---|
| 0.00 | 0.0000 | 0.0040 | 0.0091 |
| 0.05 | 0.0000 | 0.0180 | 0.0266 |
| 0.15 | 0.0000 | 0.0300 | 0.0405 |
| 0.35 | 0.0000 | **0.0640** | **0.0782** |
| 0.60 | 0.0000 | **0.0850** | **0.1009** |

With a learnable added variable: **0 false prunes in 5,000 true-edge replications.** With
an unlearnable one the rate rises monotonically with adequacy and its upper bound exceeds
`alpha` in the two highest cells.

`Theta` here is 0.15 against `delta` 0.05, so these are gross errors rather than boundary
errors. This is a per-test rate; Holm across a family would reduce the familywise figure,
and it does not contradict the multi-pair result, which used learnable scenarios.

## Finding 2 — precision converts bias into false certification

| true adequacy | median theta_hat | median se | median studentized | false-prune rate |
|---|---|---|---|---|
| 0.00 | 0.0509 | 0.02481 | 0.03 | 0.0040 |
| 0.05 | 0.0409 | 0.02231 | -0.39 | 0.0180 |
| 0.15 | 0.0317 | 0.01832 | -1.01 | 0.0300 |
| 0.35 | 0.0279 | 0.01447 | -1.55 | 0.0640 |
| 0.60 | 0.0306 | 0.01096 | -1.73 | 0.0850 |

True `Theta` is 0.15 throughout, so `theta_hat` is biased down by roughly 0.12 in every
row. **The bias does not grow with adequacy; the standard error shrinks.** A better
separator buys precision, and precision is what turns a fixed bias into a statistically
confident wrong answer.

The section 16.4 safeguard fires on 109 of 15,000 oscillatory replications. It cannot help
here: the bias makes `theta_hat` small, not negative, and the safeguard triggers on
materially negative estimates.

## Finding 3 — adequacy tracks yield, and is inversely related to safety

| observed adequacy | correct-prune rate | false-prune rate |
|---|---|---|
| (-inf, 0.00] | 0.398 | 0.0018 |
| (0.00, 0.02] | 0.427 | 0.0042 |
| (0.02, 0.05] | 0.451 | 0.0064 |
| (0.05, 0.10] | 0.487 | 0.0094 |
| (0.10, 0.20] | 0.537 | 0.0134 |
| (0.20, 0.40] | 0.652 | 0.0289 |
| (0.40, inf] | 0.771 | 0.0466 |

Both columns are monotone increasing. Higher adequacy means more true nonedges resolved
**and** more exposure to this failure mode. The index is a yield indicator, and treating it
as a quality mark would invert its meaning with respect to safety.

## What this implies for calibration

The validated scenario families do not span this failure. `learner_misspecification_v1` is
`signal * (z*x + x^2 - 1)`, which the quadratic-ridge member can fit; nothing in the grid
has an added variable the library genuinely cannot represent. The critical value is
therefore calibrated against a set of nulls that excludes the case that breaks it.

Candidate responses, none yet tested:

1. Add an unlearnable-added-variable family to the Phase-0 grid. Either the critical value
   moves further out and control is restored at a power cost, or no critical value fixes it,
   which is itself decisive.
2. Widen the learner library so fewer relationships are unlearnable. This moves the
   boundary rather than removing it.
3. Report the exposure rather than fixing it, and treat high adequacy with an unverified
   library as a documented limitation.

## Scope

`n=300`, `delta=0.05`, single directional test, one synthetic family per learnability
setting, Gaussian inputs. The oscillatory form is deliberately adversarial; whether
comparably unlearnable relationships are common in behavioural data is not established
here. The finding is about a class of failure, not a frequency in practice.
