# Phase-0 profile for v4_cubic_blend — validated, but net coarser than v3

**Not shipped.** Produced to answer one question: whether v4's precision cost is repaid by
a tighter critical value. It is not.

GitHub Actions run
[31075807715](https://github.com/imh-ds/renca/actions/runs/31075807715), 2026-08-06, all
57 jobs successful, 52 minutes. Same five scenario families, same `n=300`, `delta=0.05`,
`critical_quantile=0.04` as the shipped v3 profile, so the only difference is the library.

| | v3 (shipped) | v4 |
|---|---|---|
| `vimp_fingerprint` | `28e46383…` | `271bcb55…` |
| status | validated | **validated** |
| critical value | −5.1373 | **−4.7513** |
| worst upper bound | 0.04486 | 0.04571 |

## The net is worse

Certifying a true nonedge needs `se < delta / |critical|`, so what matters is the product
`|critical| x se` — the resolution floor.

| | critical | se on a true nonedge | resolution floor |
|---|---|---|---|
| v3 | 5.1373 | 0.00472 | **0.02426** |
| v4 | 4.7513 | 0.00562 | **0.02671** |

The critical value did tighten, by 7.5%, but the standard error grew 19.1%. **v4 resolves
10.1% less finely than v3.** The prediction that a richer library would repay its precision
cost through a shorter left tail was wrong: the tail moved, but not nearly enough.

Per-family boundary rejection barely moved, which is consistent with the library change
mattering little for these five families. `learner_misspecification_v1` is
`signal * (z*x + x^2 - 1)`, already inside the degree-2 member's span, so a cubic member
adds almost nothing there.

| family | v3 | v4 |
|---|---|---|
| `continuous_linear_boundary_v1` | 0.0018 | 0.0022 |
| `bounded_composite_unsaturated_v1` | 0.0000 | 0.0002 |
| `bounded_composite_saturated_v1` | 0.0000 | 0.0000 |
| `nonlinear_continuous_v1` | 0.0012 | 0.0030 |
| `learner_misspecification_v1` | 0.0400 | 0.0408 |

## So the trade is explicit

Adopting v4 costs about 10% of resolution and buys cubic visibility: recovery of a cubic
goes from −4% to 46%, which should also close the false-prune breach the threshold study
found for shapes the library cannot represent.

That last clause is inference, not measurement. Before paying 10% resolution, rerun the
threshold study against this profile and confirm the breach is actually gone.

## Reproduce

```bash
gh workflow run phase0-calibration.yml --ref <ref> \
  -f learner_library_version=v4_cubic_blend \
  -f profile_id=v4-cubic-blend-n300-d005-phase0
```
