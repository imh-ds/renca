# Phase-0 profile for v4_cubic_blend at delta = 0.20 — validated, shipped

GitHub Actions run
[31245856537](https://github.com/imh-ds/renca/actions/runs/31245856537), 2026-08-08, all
57 jobs successful, 81 minutes. Identical to the shipped `delta = 0.05` profile in every
respect except the resolution: same library, same `n=300`, same five scenario families,
same `critical_quantile = 0.04`, same `vimp_fingerprint` (`271bcb55…`).

| | value |
|---|---|
| status | **validated** |
| critical value | **−3.0841** |
| worst upper bound | 0.04444 (`learner_misspecification_v1`) |
| rejection at the setting family | 0.0052 |
| ineligibility, every family | 0.0000 |

## What it buys

Certifying a true nonedge requires `se < delta / |critical|`. The critical value falls 35%
from its 0.05 counterpart, so the tolerated standard error grows faster than `delta` does.

| profile | delta | critical | tolerated `se` |
|---|---|---|---|
| `…-d005-phase0` | 0.05 | 4.7513 | 0.01052 |
| `…-d010-phase0` | 0.10 | 4.0736 | 0.02455 |
| **`…-d020-phase0`** | **0.20** | **3.0841** | **0.06484** |

**A dataset can carry 6.16x the standard error and still certify** — a fourfold widening of
`delta` yields more than sixfold tolerance.

## The claim this profile certifies is weak

At `delta = 0.20`, a certified nonedge says only that the variable contributes at most a
fifth of the outcome's predictable variation. Whether that counts as "practically nothing"
is a substantive judgement about the outcome, and for many behavioural outcomes it will not.
This profile exists so that a dataset whose resolution floor sits near 0.06 can make *some*
certified statement rather than none, not because 0.20 is a defensible default. Prefer the
finest profile your data supports, and state the resolution alongside any nonedge claim.

## Per-family boundary rejection

| family | rate | 95% upper bound |
|---|---|---|
| `bounded_composite_saturated_v1` | 0.0022 | 0.00364 |
| `bounded_composite_unsaturated_v1` | 0.0032 | 0.00486 |
| `continuous_linear_boundary_v1` | 0.0052 | 0.00721 |
| `nonlinear_continuous_v1` | 0.0124 | 0.01530 |
| `learner_misspecification_v1` | 0.0396 | 0.04444 |

The four non-binding families all reject more often than at 0.05 or 0.10 while staying far
under `alpha`, which is the expected direction: at a coarser boundary the scenarios carry
more real signal, so the tail is fatter relative to the shrinking critical value.

`learner_misspecification_v1` is the exception and remains the binding family. Its rate is
flat across all three resolutions — 0.0408, 0.0406, 0.0396 — so its upper bound is in fact
marginally the *safest* here (0.04444, against 0.04571 at 0.05). The family's rejection is
driven by learner bias rather than by the boundary's signal level, and coarsening the
resolution does not touch that. Do not read the flatness as headroom for extending the
series coarser: it says the constraint is insensitive to `delta`, not that it is slack.

## Reproduce

```bash
gh workflow run phase0-calibration.yml --ref <ref> -f learner_library_version=v4_cubic_blend -f profile_id=v4-cubic-blend-n300-d020-phase0 -f delta=0.20
```
