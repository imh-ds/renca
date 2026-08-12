# Explore gate — the nonlinear map earns its place, and its floor is near `n = 75`

GitHub Actions run
[31549419998](https://github.com/imh-ds/renca/actions/runs/31549419998), 2026-08-12, all
51 jobs successful. 500 replications per cell across five sample sizes, five variable
counts and two data-generating arms: 25,000 networks, each scored against an exact oracle
and against an EBIC-selected Gaussian graphical model.

Executes [`docs/pilots/explore-feasibility-protocol.md`](../../../pilots/explore-feasibility-protocol.md).
Every threshold in that protocol was fixed before this run.

**Verdict: 43 of 50 cells eligible. The operating region is `n >= 75` for most network
sizes, `n >= 100` for six-variable nonlinear networks, and `n = 50` is out.**

## The question this answers

Whether a sparse nonlinear conditional-association map recovers real structure at
psychology-scale samples without inventing structure — and whether it beats what the field
already uses, because otherwise there is no reason for anyone to adopt it.

## What it beats, and by how much

Strong-edge recovery against the incumbent **at matched false inclusion**, so that recovery
bought by drawing more edges does not count:

| | mean gain | range | cells won |
|---|---|---|---|
| **nonlinear data** | **+0.110** | +0.025 to +0.193 | **25 of 25** |
| linear data | +0.001 | −0.065 to +0.052 | 18 of 25 |

Unanimous on the nonlinear arm. On linear data the two methods tie, which is the more
useful half of the result: the flexibility is close to free rather than something paid for
in the cases where the incumbent's assumptions actually hold.

Gains concentrate at `p = 7` and `p = 8` (up to +0.193) and thin at both ends of the
variable range.

## The operating region

Eligible variable counts out of five, by sample size:

| `n` | linear | nonlinear |
|---|---|---|
| 50 | 3 | 1 |
| 75 | 5 | 4 |
| 100 | 5 | 5 |
| 125 | 5 | 5 |
| 150 | 5 | 5 |

All seven failures are recovery failures. **Nothing failed on drawing false edges.**
Six of the seven are at `n = 50`; the seventh is `nonlinear-n75-p6`.

Strong-edge recovery, the gated quantity, bar 0.60:

| `n` | linear p6–p10 | nonlinear p6–p10 |
|---|---|---|
| 50 | 0.507 0.614 0.690 0.603 0.483 | 0.377 0.586 0.688 0.591 0.477 |
| 75 | 0.688 0.774 0.844 0.770 0.725 | 0.523 0.762 0.831 0.758 0.712 |
| 100 | 0.811 0.843 0.899 0.869 0.803 | 0.664 0.856 0.913 0.866 0.826 |
| 125 | 0.872 0.906 0.943 0.916 0.913 | 0.707 0.882 0.951 0.921 0.878 |
| 150 | 0.924 0.944 0.959 0.955 0.922 | 0.763 0.921 0.969 0.946 0.937 |

**Recovery is worst at both ends of the variable range, not at the top.** `p = 8` is the
best cell at every sample size and `p = 6` the worst, which contradicts the intuition that
smaller networks are easier. It agrees with the earlier small-network study, where
degradation as `p` fell was also entirely in usefulness rather than safety.

**The floor is lower than predicted.** The protocol anticipated `n ~ 120-150` on the
parameter-counting argument. The measurement puts it near 75. The prediction was wrong in
the conservative direction and is recorded as such.

## Safety held everywhere

Worst value across all 50 cells:

| Metric | Worst | Bar |
|---|---|---|
| False inclusion among genuine nonedges | 0.0268 | 0.05 |
| Expected spurious edges per network | 0.496 | 1.0 |
| Blank graph when the truth had strong edges | 0.082 | 0.10 |
| Runtime per network, single core | 2.51s | 300s |
| Precision (share of drawn edges that are real) | 0.865 | not gated |

The pilot's safety headroom had halved after the quota amendment, which raised the concern
that 500 replications would show it drifting toward the bar. It did not: 0.0264 at pilot
scale against 0.0268 here, with eight times the replications behind it. The concern was
unfounded and the margin is stable.

Runtime makes the mode interactive by a factor of more than a hundred.

## The finding that does not appear in any gate

Reproducibility is poor. Median Jaccard agreement between the edge sets two independent
datasets from the *same* true network produce:

| `n` | linear | nonlinear |
|---|---|---|
| 50 | 0.330 | 0.192 |
| 100 | 0.553 | 0.461 |
| 150 | 0.664 | 0.534 |

At `n = 100` on nonlinear data two researchers with the same true network would agree on
under half their edges — in a cell that passes every gated criterion.

The likely explanation is arithmetic rather than alarming: weak-edge recovery runs 0.13 to
0.40 and is erratic, while strong-edge recovery is high and stable. Reconstructing the
observed Jaccard from those two rates reproduces the 0.46-0.53 range closely, which places
essentially all of the disagreement in weak edges. **That inference is not measured here** —
the study does not compute Jaccard restricted to strong edges, and it should before any
claim rests on it.

If it holds, the product implication is direct: a single line style for every retained edge
misrepresents what is stable. The protocol's retention path, showing at what pruning
strictness each edge enters, is the artifact that would carry this honestly.

> **Measured since, in [`reproducibility-rerun/`](reproducibility-rerun/README.md).** The
> inference is confirmed in direction and was overstated in degree. Strong edges reproduce
> at 0.90-1.00 inside the operating region and weak edges reach 0.41 at best, so the mixed
> figure above averages a trustworthy component with a near-random one. But weak edges carry
> 61-78% of the disagreement rather than essentially all of it; strong edges still
> contribute 13-25%. Spurious edges are irreproducible noise, agreeing across datasets at
> 0.000, which is the outcome that rules out systematic bias.

## Amendment, disclosed

The per-node selection quota was changed after a first pilot
([31530427179](https://github.com/imh-ds/renca/actions/runs/31530427179)) was run and read.
That pilot derived the quota and the graph's degree cap from two different fractions of
`p - 1`, and at `p` in {7, 8, 9} the rounding put the quota below the cap, so a node at
maximum degree could not have all its edges selected however good the data were. The two
variable counts where the constants happened to agree were the two best performers, which
is what identified the fault.

The correction removed a handicap carried by `explore` alone — the comparator sweeps its
own penalty path without a quota — so it moved results in `explore`'s favour: the mean
nonlinear gain went from +0.073 to +0.125 at pilot scale. It is a correction of a
structural impossibility rather than a tuning choice, and the pilot was re-run from scratch
rather than patched. **Neither pilot's numbers may be cited.**

## Limits

* **The quota is set to the sparsity the design permits.** A real analyst does not know
  that level. This isolates the question asked at the cost of assuming the quota is set
  well, and sensitivity to mis-setting it is not studied.
* **Nothing here establishes absence.** The study measures recovery. An edge not drawn is
  not retained at this setting, and no output may be read as evidence a relationship is
  absent.
* **Nothing here establishes causal direction.** No directional quantity is produced.
* **Nothing here transfers to `renca resolve`.** The two modes condition on different sets;
  `tau` and `Theta` share a functional form and are not comparable.
* **One estimator configuration**, one basis dimension, one retention threshold, one
  subsample count.
* The linear comparator is an incumbent benchmark. Its performance does not authorize
  shipping a linear mode.
* Additive smooth effects only. No interactions are generated or searched.

## Reproduce

```bash
gh workflow run explore-gate.yml --ref main -f replications=500 -f stage=full
```
