# Multi-pair familywise error study — 2 blocks, n=375

Protocol: [`docs/pilots/phase1-multipair-fwer-protocol.md`](../../../pilots/phase1-multipair-fwer-protocol.md).
Produced by GitHub Actions run
[30943525054](https://github.com/imh-ds/renca/actions/runs/30943525054) on
2026-08-04 from `main`, 20 shards x 250 replications, all 21 jobs successful.

Reproduce with:

```bash
python simulations/multipair_fwer.py shard --start 0 --count 250 --blocks 2 --output out/shard-0.parquet
```

## Configuration

5,000 replications of 2 independent boundary blocks: 6 nodes, 15 pairs, 375
complete cases yielding exactly 300 inference rows, 5 folds, `delta=0.05`,
`alpha=0.05`, profile `v3-nested-blend-n300-d005-phase0`. Per replication: 6
within-block null pairs (2 of them exactly on the boundary in both directions)
and 9 cross-block exact nonedges.

## Result 1 — familywise error is controlled

| Quantity | Value |
|---|---|
| Replications with at least one false certification | 4 / 5,000 |
| Familywise error rate | 0.0008 |
| 95% Clopper-Pearson upper bound | 0.00183 |
| Target | 0.05 |

All four errors occurred on boundary pairs and none on the far-from-boundary
`z--x` / `z--y` pairs, which is the coherent pattern: errors appear where the
null is hardest and nowhere else.

**Separator recovery was 10,000 / 10,000.** Every boundary pair in every
replication selected its block confounder, so the pairs really were tested at
`theta = delta`. The error result is therefore genuine rather than an artifact of
testing pairs that had drifted far from equivalence.

This is the first direct evidence on specification section 44 falsification
criterion 1, and it measures the shipped code path end to end, including the
data-dependent shrinkage of the Holm family caused by abstention.

## Result 2 — the procedure almost never prunes

| Quantity | Value |
|---|---|
| True-nonedge certification rate | 2.18% (983 / 45,000) |
| Replications certifying **zero** true nonedges | 82.9% (4,147 / 5,000) |
| Abstention rate | 43.4% (median 13 of 30 directional estimates) |
| Mean Holm family size | 7.24 of 15 pairs |

The blocker is not statistical power in the usual sense. A diagnostic
replication showed true-nonedge directional statistics at a median studentized
value of **-7.46** against a critical value of **-3.095** -- far into the
rejection region. They are discarded before they are ever tested:

```
true nonedge -> psi ~ 0 -> an irrelevant added variable usually makes the full
model slightly worse -> psi < 0 -> theta_hat < 0 -> full_worse_than_reduced
-> status != "success" -> calibration_status != "calibrated_success"
-> no p-value -> dropped from the Holm family -> certification impossible
```

For a true nonedge `theta_hat` falls below zero roughly half the time by
construction, so the rule fires hardest on exactly the pairs the method exists to
prune. The resulting Holm family is dominated by non-separable pairs while the
separable ones are excluded.

`theta_hat < 0` is the strongest available evidence of practical irrelevance. The
readiness plan requires that `full_worse_than_reduced` never be treated as
evidence *of* a nonedge; the implementation additionally treats it as blocking
evidence *against* certification, and that gap is where the power went.

## Result 3 — the conservatism is stacked, and it is not free

An observed familywise error rate of 0.0008 against a nominal 0.05 means the
procedure spends about one sixtieth of its error budget. At least five
independently defensible conservative choices compose here:

1. the calibrated p-value takes the worst-family left tail across five scenario families;
2. the critical value is the minimum of the per-family 5% quantiles;
3. abstention removes would-be rejections;
4. the pair test takes the maximum of two directional p-values;
5. Holm adjusts across the pair family.

Each is reasonable alone. Together they buy far more safety than `alpha`
requires, and the 2.18% pruning rate is what that safety costs.

## Scope

Two blocks, 6 nodes, `n=375`, one delta, Gaussian linear blocks. It establishes
familywise control for this configuration; it does not establish it for larger
node counts, other deltas, other sample sizes, or non-Gaussian data. Results
speak to specification section 44 criteria 1, 3, and 4.
