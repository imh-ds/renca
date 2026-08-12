# Where explore's disagreement lives — strong edges reproduce, weak edges do not

GitHub Actions run
[31561441669](https://github.com/imh-ds/renca/actions/runs/31561441669), 2026-08-12, all
51 jobs successful. Same protocol, same grid, same 500 replications per cell as the
[recorded full run](../README.md); adds a decomposition of the reproducibility diagnostic
and changes nothing else.

## The claim under test

The full-run write-up found that two independent datasets from the *same* true network
agree on under half their edges at `n = 100` on nonlinear data, in cells passing every
gated criterion. It then **inferred** that essentially all of that disagreement sits in
weak edges, reconstructing the observed Jaccard from the separate strong and weak recovery
rates, and recorded the inference as something to be measured rather than a result.

**The inference is confirmed in direction and was overstated in degree.**

## Agreement between two datasets, by connection type

Median Jaccard. `all edges` is the figure the full run reported.

**Linear**

| `n` | strong | weak | nonedge | all edges |
|---|---|---|---|---|
| 50 | 0.500 | 0.000 | 0.0 | 0.330 |
| 75 | 0.700 | 0.145 | 0.0 | 0.447 |
| 100 | **1.000** | 0.263 | 0.0 | 0.553 |
| 125 | **1.000** | 0.352 | 0.0 | 0.618 |
| 150 | **1.000** | 0.406 | 0.0 | 0.664 |

**Nonlinear**

| `n` | strong | weak | nonedge | all edges |
|---|---|---|---|---|
| 50 | 0.367 | 0.000 | 0.0 | 0.192 |
| 75 | 0.600 | 0.050 | 0.0 | 0.350 |
| 100 | **0.900** | 0.150 | 0.0 | 0.461 |
| 125 | **0.900** | 0.263 | 0.0 | 0.497 |
| 150 | **0.933** | 0.300 | 0.0 | 0.534 |

Inside the operating region, strong edges reproduce at 0.90 to 1.00. Weak edges reach
0.41 at best and sit at 0.00 at `n = 50`. The mixed figure the full run reported is the
average of a trustworthy component and a near-random one, and it understates the first
while flattering the second.

## Share of all disagreement, by connection type

| `n` | linear: strong / weak / nonedge | nonlinear: strong / weak / nonedge |
|---|---|---|
| 50 | 0.454 / 0.470 / 0.076 | 0.404 / 0.423 / 0.173 |
| 100 | 0.258 / 0.673 / 0.070 | 0.245 / 0.612 / 0.143 |
| 150 | 0.129 / 0.784 / 0.088 | 0.170 / 0.681 / 0.150 |

**This is where "essentially all" was wrong.** Weak edges account for 61-78% of
disagreement inside the operating region — a clear majority, not the whole. Strong edges
still contribute 13-25%.

The two views differ because the counts differ: a graph carries more weak edges than
strong ones, so weak edges dominate the *volume* of disagreement even where strong edges
have the higher *rate* of it. The per-class Jaccard is the quantity that answers whether a
given edge can be trusted; the share answers what a reader is mostly looking at.

## A finding not asked for

**Nonedge Jaccard is 0.000 everywhere.** When a spurious edge appears, it essentially never
appears in both datasets.

That is the good case, and it was not guaranteed. A high value here would have meant the
false edges were systematic — the same wrong connection drawn from the same truth twice,
which is a bias and would survive any amount of extra data. Zero means they are
irreproducible noise, which is what replication is supposed to remove.

## Product implication

Strong edges are reproducible enough to show as findings. Weak edges are not: at `n = 150`
on nonlinear data, two researchers with the same truth agree on 30% of them.

A single line style for every retained edge would present those side by side as though
they carried the same weight. The protocol's retention path — showing at what pruning
strictness each edge enters — is the artifact that separates them, and this result says it
is load-bearing rather than decorative.

## Reproducibility, corrected

The rerun was described in [PR #26](https://github.com/imh-ds/renca/pull/26) as bit-identical
to the recorded run. It is not, quite.

**Inputs reproduce exactly.** Across all 25,000 replications, the drawn graphs, the redraw
counts and the true structure match the recorded run without a single difference. Seeding
by identity works as designed.

**Fitted outputs reproduce to about 0.002.** 24 replications of 25,000 (0.096%) differ,
concentrated at `p = 6` where the selection quota is tightest and a borderline decision has
the largest effect. The cause is ordinary floating-point variation across Actions runner
hardware in the SVD and the group-lasso path, not the added code — which draws nothing from
the random number generator.

No gate decision changed: 43 of 50 cells eligible in both runs, the same 43. Largest
disagreement in any summary statistic is 0.006, in one blank-graph rate.

The protocol's claim that re-running reproduces "the numbers themselves and not merely
their distribution" should therefore be read as holding for the design and the generated
data, and as holding to about two decimal places for fitted quantities.

## Limits

Inherits every limit of the [full run](../README.md). In addition:

* Strong and weak are the protocol's `tau >= 0.10` split. Reproducibility is a continuous
  function of edge strength and this reports it at one cut.
* Agreement is measured between two datasets of the *same* size from the *same* truth. It
  says nothing about agreement across studies that differ in either.
