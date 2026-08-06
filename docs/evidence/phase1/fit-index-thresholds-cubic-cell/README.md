# Threshold study with a cubic cell — v4 fixes the domain-relevant breach

45,000 replications per library, 45 cells, from GitHub Actions runs
[31082519771](https://github.com/imh-ds/renca/actions/runs/31082519771) (v3) and
[31082538643](https://github.com/imh-ds/renca/actions/runs/31082538643) (v4), 2026-08-06,
all 21 jobs successful in each.

Adds a cubic `added_form` to the grid. Earlier runs tested linear and oscillatory only, so
the shape `v4_cubic_blend` exists to cover was absent and v4's benefit scored zero by
construction while its costs were fully counted. This is the comparison that decides
adoption.

## False-prune rate on true edges

`Theta = 0.15` against `delta = 0.05`, so every certification here is a gross error.

| added variable | true adequacy | v3 | v4 | v3 95% upper | v4 95% upper |
|---|---|---|---|---|---|
| linear | all | 0.0000 | 0.0000 | 0.0030 | 0.0030 |
| **cubic** | 0.00 | 0.0190 | **0.0000** | 0.0278 | 0.0030 |
| **cubic** | 0.05 | 0.0270 | **0.0020** | 0.0370 | 0.0063 |
| **cubic** | 0.15 | 0.0460 | **0.0010** | 0.0584 | 0.0047 |
| **cubic** | 0.35 | **0.0730** | **0.0010** | **0.0880** breach | 0.0047 |
| **cubic** | 0.60 | **0.0970** | **0.0000** | **0.1138** breach | 0.0030 |
| oscillatory | 0.35 | 0.0680 | 0.0750 | 0.0826 breach | 0.0902 breach |
| oscillatory | 0.60 | 0.0860 | 0.0990 | 0.1020 breach | 0.1159 breach |

On cubics v3 breaches `alpha` at the two highest adequacies and rises with adequacy, the
same precision-amplifies-bias pattern seen before. **v4 removes it: at most 0.0020 in any
cubic cell, upper bounds all under 0.0063.**

| | v3 | v4 |
|---|---|---|
| overall false-prune rate | 0.0314 | **0.0162** |
| overall correct-prune rate | 0.6016 | 0.5708 |

v4 roughly halves false pruning and gives up about 5% of correct pruning, relative.

## What v4 does not fix

The oscillatory cells still breach under both, and marginally worse under v4: 0.0680 to
0.0750 at adequacy 0.35, 0.0860 to 0.0990 at 0.60. A cubic member cannot represent
`sin(4x)` and its eight turning points, so the bias is unchanged there while v4's critical
value is more permissive at −4.7513 against −5.1373. A looser threshold on a pair the
estimator cannot see means more false certifications.

**This is the scope boundary, and it should be stated rather than hidden.** Under v4 the
guarantee holds for relationships up to cubic; beyond that, false pruning can exceed
`alpha`. That boundary is unverifiable from data — a user cannot inspect a dataset and
determine the true functional form — so it is an assumption the analysis rests on, not a
condition that can be checked.

## Reading

Adoption turns on how often relationships past cubic occur. Social and behavioural research
reports non-linearity mainly as exponential growth or decay, parabolas, and occasionally
cubics, all of which v4 covers and the first two of which v3 already covered. Against that,
v4 halves false pruning, removes a breach on a common shape, and costs roughly 5% of
correct pruning here and a 10.1% coarser resolution floor.

The residual oscillatory breach is real and slightly worse under v4. It is a limit on both
libraries rather than a reason to prefer v3, which breaches on cubics as well.

## Note on comparability

Replications are now seeded from cell identity rather than grid position, so inserting the
cubic cell does not reseed the others. The linear and oscillatory numbers here therefore do
not byte-match the earlier 30-cell runs; they are statistically equivalent at this size, and
grid additions after this one leave existing cells untouched.
