# Phase-0 profile for v4_cubic_blend at delta = 0.10 — validated, shipped

GitHub Actions run
[31245842503](https://github.com/imh-ds/renca/actions/runs/31245842503), 2026-08-08, all
57 jobs successful, 67 minutes. Identical to the shipped `delta = 0.05` profile in every
respect except the resolution: same library, same `n=300`, same five scenario families,
same `critical_quantile = 0.04`, same `vimp_fingerprint` (`271bcb55…`).

| | value |
|---|---|
| status | **validated** |
| critical value | **−4.0736** |
| worst upper bound | 0.04549 (`learner_misspecification_v1`) |
| rejection at the setting family | 0.0020 |
| ineligibility, every family | 0.0000 |

## What it buys

Certifying a true nonedge requires `se < delta / |critical|`. Both terms move in the
helpful direction: `delta` doubles, and the critical value shrinks by 14% because the
boundary distribution's left tail is shorter at a coarser resolution.

| profile | delta | critical | tolerated `se` |
|---|---|---|---|
| `…-d005-phase0` | 0.05 | 4.7513 | 0.01052 |
| **`…-d010-phase0`** | **0.10** | **4.0736** | **0.02455** |

**A dataset can carry 2.33x the standard error and still certify.** For scale, the study of
near-independent variables measured `se = 0.00562` on a true nonedge and the bundled example
roughly 0.035; the latter certifies nothing at 0.05 and would at 0.10.

That is a change of question, not a loosening of standards. At `delta = 0.10` the claim is
"this variable contributes at most a tenth of the outcome's predictable variation", which is
a weaker statement, certified with the same error control.

## Per-family boundary rejection

| family | rate | 95% upper bound |
|---|---|---|
| `bounded_composite_saturated_v1` | 0.0002 | 0.00095 |
| `bounded_composite_unsaturated_v1` | 0.0008 | 0.00183 |
| `continuous_linear_boundary_v1` | 0.0020 | 0.00339 |
| `nonlinear_continuous_v1` | 0.0044 | 0.00628 |
| `learner_misspecification_v1` | 0.0406 | 0.04549 |

`learner_misspecification_v1` sets the binding constraint here exactly as it does at 0.05
(0.0408 / 0.04571), and its margin against `alpha` is no thinner. Coarsening the resolution
did not buy slack in the hardest family; it bought slack in the standard error.

## Reproduce

```bash
gh workflow run phase0-calibration.yml --ref <ref> -f learner_library_version=v4_cubic_blend -f profile_id=v4-cubic-blend-n300-d010-phase0 -f delta=0.10
```
