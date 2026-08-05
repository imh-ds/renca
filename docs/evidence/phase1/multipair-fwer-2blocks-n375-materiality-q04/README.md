# Multi-pair FWER — materiality safeguard, 0.04 critical quantile

Same protocol and configuration as
[`../multipair-fwer-2blocks-n375/`](../multipair-fwer-2blocks-n375/README.md), rerun
against the revalidated profile so the two are directly comparable. Produced by GitHub
Actions run [31026913703](https://github.com/imh-ds/renca/actions/runs/31026913703) on
2026-08-05, 20 shards x 250 replications, all 21 jobs successful.

Profile: `vimp_fingerprint 28e46383…`, `critical_value -5.137323402339938`,
`critical_quantile 0.04`.

## Result

| metric | original | this run |
|---|---|---|
| familywise error rate | 0.0008 | **0.0000** |
| 95% upper bound | 0.00183 | **0.00060** |
| true-nonedge certification | 2.18% | **10.14%** |
| replications certifying none | 82.9% | **47.8%** |
| abstention rate | 43.4% | **1.09%** |
| mean Holm family size (of 15) | 7.24 | **14.71** |
| separator recovery | 100% | 100% |

Distribution of true nonedges certified per replication, out of nine available:

| certified | original | this run |
|---|---|---|
| 0 | 82.9% | 47.8% |
| 1 | 14.8% | 29.4% |
| 2 | 2.0% | 12.6% |
| 3 | 0.3% | 6.3% |
| 4+ | 0.0% | 3.8% |

## Reading

**Familywise error is controlled decisively.** Zero errors in 5,000 replications against
`alpha = 0.05`, with 100% separator recovery confirming the boundary pairs were genuinely
tested at `theta = delta`. The section 16.4 safeguard removed abstention as a source of
error control without costing any.

**The safeguard delivered a 4.7x power gain, and the critical value absorbed most of it.**
Measured against the intermediate `-4.778` critical value, true-nonedge certification was
56.7%. At the shipped `-5.137` it is 10.14%. The difference is the price of the sub-alpha
critical quantile that the acceptance criterion requires.

**The procedure now spends roughly one eightieth of its error budget.** An upper bound of
0.00060 against `alpha = 0.05` is not a near-miss on control; it is a large unused margin.
Combined with 10.14% pruning, the binding constraint has moved: it is no longer the
abstention rule but the stacked worst-family conservatism, which sets both the critical
value (minimum over families) and the p-value (maximum over families) from
`learner_misspecification_v1`. Data unlike that family pays its cost regardless.

## Against the specification's falsification criteria

| section 44 criterion | status |
|---|---|
| 1. familywise error at the boundary | **passes** — 0.0000, upper bound 0.00060 |
| 3. prunes a useful fraction of true nonedges | **unassessable** — 10.14%, but no PC/FCI/EBICglasso baseline exists to compare against |
| 4. unresolvedness | **improved, still high** — 89.9% of exact nonedges unresolved, down from 97.8% |

Criterion 4 is stated for `n >= 2000` and `p = 15`; this study is `n = 300` inference rows
and `p = 6`, so it is indicative rather than a direct test.

## Scope

Two blocks, 6 nodes, `n = 375`, one delta, Gaussian linear blocks, i.i.d. rows. Familywise
control is established for this configuration only.
