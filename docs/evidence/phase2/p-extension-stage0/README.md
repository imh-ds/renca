# p-extension Stage 0 — cost grows with network size, not with sample size

GitHub Actions run
[31621617259](https://github.com/imh-ds/renca/actions/runs/31621617259), 2026-08-12, all 5
jobs successful. 15 and 30 variables at 100 and 500 people, 10 replications per cell,
moderately dense, mixed curved-and-straight — the most expensive combination in the grid, so
every figure here is an upper bound rather than a best case.

Executes Stage 0 of
[the p-extension protocol](../../../pilots/explore-p-extension-protocol.md).

**Stage 0 can reject a plan and cannot approve one.** Ten replications establish no
performance criterion, and nothing here may be cited as evidence about how well the mode
works. It measures cost, and it replaces the protocol's extrapolated cost figures with
measurements.

**Verdict: the staged plan is affordable, roughly a third of what was extrapolated. Nothing
rejects it.**

## Measured cost

| variables | people | explore | explore-straight | baseline | oracle | per replication | peak memory |
|---|---|---|---|---|---|---|---|
| 15 | 100 | 6.38s | 6.18s | 0.57s | 0.96s | **20.6s** | 230 MB |
| 15 | 500 | 4.32s | 4.58s | 0.31s | 1.00s | **15.2s** | 239 MB |
| 30 | 100 | 13.77s | 9.72s | 0.91s | 4.42s | **44.3s** | 233 MB |
| 30 | 500 | 11.89s | 13.02s | 0.86s | 5.80s | **45.1s** | 241 MB |

Per-replication cost carries one further explore fit beyond the three arms, because
stability requires a second independent dataset.

## The finding

**Sample size barely moves the cost.** At 30 variables, five times the rows changes the
cost by 2% — 44.3s against 45.1s. At 15 variables the larger sample is *faster*.

The work is dominated by the loop over variables, subsamples and penalty steps, none of
which grow with row count; the matrices inside that loop are small enough that row count is
noise against loop overhead. More data can even shorten the penalty path, by reaching the
selection quota in fewer steps.

**Cost grows sub-quadratically in network size.** The measured slope is 1.10 at 100 people
and 1.57 at 500, against the 2.0 the protocol assumed. Doubling the variable count roughly
doubles the cost rather than quadrupling it.

**Memory is not a constraint.** 241 MB at the largest cell, against several gigabytes
available on a runner. The protocol's concern that 30-variable behaviour might be
computationally impractical is answered: it is not.

## Corrected cost for the remaining stages

| | protocol extrapolation | measured projection |
|---|---|---|
| Stage 1 (32 cells) | 90 core-hours | **58** |
| Stage 2 (48 cells) | 470 core-hours | **228** |

Both fall well below what was budgeted. For scale, the completed 6-to-10-variable study was
about 50 core-hours, so Stage 1 costs about the same as that study and Stage 2 about four
times it.

**Sharding is still required.** A 30-variable cell at 500 replications is 6.3 hours against
the 6-hour limit on a GitHub Actions job. Two chunks clears it arithmetically, but at 3.1
hours each that leaves little margin on a slow runner; four chunks is the safer split and
costs nothing extra.

## A defect in this study's own arithmetic, corrected

The first version of the projection scaled cost by sample size. It predicted 9s per
replication for the 30-variable 100-person cell against 44.3s measured — a fivefold
under-estimate — and made Stage 1 and Stage 2 look like 20 and 119 core-hours rather than 58
and 228.

The projection now scales by variable count alone and uses the steeper of the two measured
slopes, so it errs high. Sanity check: it predicts 15.2s for 15 variables, against 15.2s
measured.

The numbers in this README are the corrected ones. The verdict file in this directory was
regenerated from the run's own recorded results with the fixed code, so it agrees.

## The graph construction was repaired before this run

An earlier dispatch ([31616795270](https://github.com/imh-ds/renca/actions/runs/31616795270))
failed at 15 variables and moderate density: the sampler could not draw a network carrying
the two strong relationships the protocol requires.

The cause was that positive definiteness had been guaranteed by diagonal dominance, which
sets each diagonal entry to the sum of a node's edge magnitudes and so roughly halves every
partial correlation when the average degree doubles — welding density to relationship
strength. Graphs carrying two strong relationships fell from 12 of 12 at 2 connections per
variable to 4 of 12 at 4. Relationship strengths are now heterogeneous, a few strong and the
rest modest, with a unit diagonal so the off-diagonal entries are the partial correlations
themselves. See [PR #28](https://github.com/imh-ds/renca/pull/28).

Redraws in this run averaged 0.2 to 0.8 per replication, so the repair holds at both network
sizes.

## Limits

* **No performance claim.** Ten replications per cell. Recovery, false connections,
  stability and every gated criterion are unmeasured here and unmeasurable at this count.
* One density and one shape arm — the most expensive of each. Sparse and fully-linear cells
  will cost less, so the projections stay upper bounds.
* Timings are GitHub Actions runner hardware. A different machine will differ, though the
  *ratios* that produced the scaling slope should hold.
* The slope rests on two variable counts. It describes the interval between them and is an
  extrapolation outside it, including at the 12-variable end of Stage 1.

## Reproduce

```bash
gh workflow run explore-p-extension.yml --ref main -f replications=10 -f stage=0
```
