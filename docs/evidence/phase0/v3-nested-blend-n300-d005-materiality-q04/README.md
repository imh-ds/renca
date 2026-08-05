# Phase-0 profile — materiality safeguard, 0.04 critical quantile

**This is the profile shipped in `src/renca/data/calibration/`.** It supersedes
[`../v3-nested-blend-n300-d005/`](../v3-nested-blend-n300-d005/), which described a
different decision rule.

Produced by GitHub Actions run
[30986710818](https://github.com/imh-ds/renca/actions/runs/30986710818) on 2026-08-05,
30 training shards plus 25 validation shards of 1,000 replications, all 57 jobs
successful, 46 minutes.

| | value |
|---|---|
| `profile_id` | `v3-nested-blend-n300-d005-phase0` |
| `vimp_fingerprint` | `28e463837b013a2d7d550a254a89a808ae798de9571d861c1c46611557a9ac71` |
| `critical_value` | −5.137323402339938 |
| `critical_quantile` | 0.04 |
| `status` | **validated** |

## What changed from the superseded profile

Two things, in sequence.

**The section 16.4 materiality safeguard.** `full_worse_than_reduced` previously fired on
any negative `psi`. It now requires degradation that is material — beyond
`nested_safeguard_materiality_z` standard errors — and consistent across folds.
Ineligibility in `learner_misspecification_v1` fell from **14.3% to 0.04%**.

**The critical quantile.** That collapse in abstention caused the first rerun
([30982933264](https://github.com/imh-ds/renca/actions/runs/30982933264)) to be
**rejected**, which exposed a pre-existing flaw. The critical value is the minimum over
families of each family's own training quantile, and the family attaining that minimum is
then validated against the same value on independent draws from its own distribution — so
its rejection rate targets that quantile exactly. At `alpha`, the observed rate sits on
`alpha` and its 95% upper bound exceeds it about half the time.

The superseded profile had cleared the bar only because ineligible replications cannot
reject while remaining in the denominator, making the argmin family's rate
`alpha * (1 - ineligibility)`:

| run | ineligibility | predicted | observed |
|---|---|---|---|
| superseded | 14.3% | 0.0428 | 0.0434 |
| first rerun | 0.04% | 0.0500 | 0.0496 |

Both fit, so that margin was a by-product of refusing to answer rather than a property of
the procedure. Setting the quantile to 0.04 buys it explicitly.

## Validation grid

| scenario family | rejection | 95% upper bound | ineligibility |
|---|---|---|---|
| `continuous_linear_boundary_v1` | 0.0018 | 0.00314 | 0.0000 |
| `bounded_composite_unsaturated_v1` | 0.0000 | 0.00060 | 0.0000 |
| `bounded_composite_saturated_v1` | 0.0000 | 0.00060 | 0.0000 |
| `nonlinear_continuous_v1` | 0.0012 | 0.00237 | 0.0000 |
| `learner_misspecification_v1` | 0.0400 | 0.04486 | 0.0004 |

Every upper bound is at or below `alpha = 0.05`, now without help from abstention.

## Cost, and what is still unmeasured

The critical value moved from −3.095 (superseded) through −4.778 (first rerun) to
−5.137. On the bundled pilot the certified pair's adjusted p rose from 0.0035 to 0.0220 —
it still certifies, with far less margin.

Neither open question is answered by this profile:

- **Familywise error** under the new rule rests on 0 errors in 60 replications, a 95%
  upper bound of 0.0487. The 5,000-replication study must be rerun against this profile.
- **Pruning power** was 56.7% when measured against the −4.778 critical value. At −5.137
  it will be lower, and by how much bears directly on the Phase 1 completion decision
  recorded in [`../../../decision-records/0003-phase1-completion-evidence.md`](../../../decision-records/0003-phase1-completion-evidence.md).
