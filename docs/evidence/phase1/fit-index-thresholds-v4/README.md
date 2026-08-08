# Threshold study against the v4 profile — v4 is worse on both measured axes

30,000 replications from GitHub Actions run
[31079434872](https://github.com/imh-ds/renca/actions/runs/31079434872), 2026-08-06, all
21 jobs successful, 22 minutes. Identical grid and configuration to
[`../fit-index-thresholds/`](../fit-index-thresholds/README.md); the only change is the
profile, `v4-cubic-blend-n300-d005-phase0` at critical value −4.7513 against v3's −5.1373.

Run to test one inference: that adding a cubic member closes the false-prune breach. **It
does not, on this grid.**

## False pruning got worse

True edges, `Theta = 0.15` against `delta = 0.05`:

| true adequacy | added variable | v3 | v4 | v4 95% upper |
|---|---|---|---|---|
| any | linear | 0.0000 | 0.0000 | 0.0030 |
| 0.00 | oscillatory | 0.0040 | 0.0040 | 0.0091 |
| 0.05 | oscillatory | 0.0180 | 0.0200 | 0.0289 |
| 0.15 | oscillatory | 0.0300 | 0.0380 | 0.0495 |
| 0.35 | oscillatory | 0.0640 | **0.0840** | **0.0999** breach |
| 0.60 | oscillatory | 0.0850 | **0.0980** | **0.1149** breach |

Overall false pruning rises from 0.0201 to 0.0244 and correct pruning falls slightly, 0.5670
to 0.5607. Both breaches remain, and both are larger.

## Why: same blindness, looser threshold

| true adequacy | v3 median theta | v4 median theta | v3 median se | v4 median se |
|---|---|---|---|---|
| 0.00 | 0.0509 | 0.0514 | 0.02481 | 0.02512 |
| 0.15 | 0.0317 | 0.0318 | 0.01832 | 0.01855 |
| 0.60 | 0.0306 | 0.0298 | 0.01096 | 0.01109 |

True `Theta` is 0.15 throughout. The estimates are indistinguishable between libraries: a
cubic member does not help with `sin(4x)`, which needs eight turning points. What v4
changed is the critical value, from −5.1373 to −4.7513, making certification easier — and
on a pair the estimator cannot see, easier certification means more false prunes.

A more permissive threshold is only safe if it is paid for by less bias. Here it was not.

## What this study cannot answer

**The grid has no cubic cell.** Its `added_form` values are `linear` and `oscillatory`
only. The shape v4 exists to fix is absent, so the measured benefit of v4 is zero by
construction while its costs are fully counted.

This is a design gap: the grid was built before the shape study identified cubic as the
domain-relevant blind spot. On current evidence v4 should not be adopted, but the evidence
does not yet include the case that motivates it.

The decisive addition is a cubic `added_form`. Expectation, from the shape study: v3
recovers roughly none of a cubic so `theta_hat` falls well below `delta` and false pruning
should be high, while v4 recovers about 46% so `theta_hat` should clear `delta` and it
should not. Running both libraries on that cell would settle adoption.
