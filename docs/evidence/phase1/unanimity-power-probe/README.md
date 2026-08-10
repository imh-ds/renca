# Unanimity power probe at n = 375 — survives at delta = 0.20 only

GitHub Actions run
[31356442823](https://github.com/imh-ds/renca/actions/runs/31356442823), 2026-08-10, all 19
jobs successful. 102 replications per cell, 612 total. `p` in {4, 5, 6}, both DGP families,
`realistic` regime only, `n = 375`, `max_separator_size = 1`, v4 library.

The [small-network study](../small-network-feasibility/README.md) put the population ceiling
for universal agreement at 0.39-0.80 correct pruning on small networks. This asks how much of
that a real sample keeps.

**Result: the kill-test did not kill it, but it narrowed the viable region to a single
resolution.** At `delta = 0.20` correct pruning is at most 0.42 with wrongful pruning at or
below 0.010. At `delta = 0.10` the upper bound is 0.21. At `delta = 0.05` it is 0.018 — dead.

## Both rules are upper bounds, not a bracket

The probe reports two unvalidated decision rules. **Neither is calibrated, and the earlier
description of them as bracketing the truth from opposite sides was wrong** — both certify
*more* than a genuine calibrated rule would, so both are upper bounds and the truth lies below
the lower of them.

`normal_holm`
    Normal-approximation one-sided p per direction, maximum across all `2(p-1)` tests, Holm
    across pairs. Correct on multiplicity but far too lax on the test: Phase 0 put the
    calibrated critical value at -4.75, -4.07 and -3.08 for the three deltas, against the
    normal -1.645.

`critical_raw`
    Every one of the `2(p-1)` statistics must clear the shipped delta-matched critical value,
    with no multiplicity adjustment. Correct on the test scale but skips Holm — and Holm only
    ever raises p-values, so the real rule certifies strictly less than this.

A calibrated rule applies **both** the strict critical value **and** Holm. It is therefore
below `critical_raw`, and below `normal_holm`. `upper_bound` in the table is the minimum of the
two; the achievable number is smaller by an unknown margin, and only a Phase-0 run can say how
much smaller.

## What a real sample keeps

`ceiling` is the population value from the small-network study; `upper_bound` is the tighter of
the two rules here.

| family | delta | p | ceiling | normal_holm | critical_raw | upper bound | fraction of ceiling |
|---|---|---|---|---|---|---|---|
| additive_nonlinear | 0.05 | 4 | 0.524 | 0.120 | 0.008 | **0.008** | 0.015 |
| additive_nonlinear | 0.05 | 5 | 0.521 | 0.166 | 0.013 | **0.013** | 0.024 |
| additive_nonlinear | 0.05 | 6 | 0.493 | 0.120 | 0.008 | **0.008** | 0.017 |
| additive_nonlinear | 0.10 | 4 | 0.667 | 0.347 | 0.213 | **0.213** | 0.320 |
| additive_nonlinear | 0.10 | 5 | 0.634 | 0.328 | 0.226 | **0.226** | 0.356 |
| additive_nonlinear | 0.10 | 6 | 0.642 | 0.290 | 0.180 | **0.180** | 0.280 |
| additive_nonlinear | 0.20 | 4 | 0.776 | 0.474 | 0.404 | **0.404** | 0.520 |
| additive_nonlinear | 0.20 | 5 | 0.768 | 0.443 | 0.390 | **0.390** | 0.508 |
| additive_nonlinear | 0.20 | 6 | 0.800 | 0.433 | 0.398 | **0.398** | 0.498 |
| linear_gaussian | 0.05 | 4 | 0.387 | 0.138 | 0.042 | **0.042** | 0.109 |
| linear_gaussian | 0.05 | 5 | 0.384 | 0.148 | 0.030 | **0.030** | 0.077 |
| linear_gaussian | 0.05 | 6 | 0.437 | 0.116 | 0.005 | **0.005** | 0.011 |
| linear_gaussian | 0.10 | 4 | 0.528 | 0.286 | 0.197 | **0.197** | 0.374 |
| linear_gaussian | 0.10 | 5 | 0.533 | 0.323 | 0.229 | **0.229** | 0.429 |
| linear_gaussian | 0.10 | 6 | 0.597 | 0.297 | 0.203 | **0.203** | 0.340 |
| linear_gaussian | 0.20 | 4 | 0.739 | 0.479 | 0.433 | **0.433** | 0.587 |
| linear_gaussian | 0.20 | 5 | 0.701 | 0.478 | 0.430 | **0.430** | 0.614 |
| linear_gaussian | 0.20 | 6 | 0.789 | 0.500 | 0.474 | **0.474** | 0.600 |

Averaged over `p` and family, the upper bound on power is **0.018** at `delta = 0.05`,
**0.208** at `delta = 0.10`, and **0.422** at `delta = 0.20`.

## Error control holds

Across all 36 cells and both rules: wrongful pruning never exceeds **0.010**, and the
probability a whole network contains at least one wrongful deletion never exceeds **0.029**.
Both sit under the 0.05 bar. This is reassuring but is **not** a guarantee — neither rule is
calibrated, and a familywise claim requires a validated profile.

## Two things that shape what a user would see

**Most pairs stay unresolved**: 0.61 to 0.87 across every cell, 0.61 at best. Even in the one
viable region roughly two pairs in three come back "no evidence either way." A small network
under this rule reports a handful of certified nonedges and leaves the rest open.

**Network size barely matters now.** The population ceilings rose steadily with `p`; these
finite-sample rates are flat across `p = 4, 5, 6`. Sample size, not network size, is the
binding constraint once real data is involved — which is why the p-sensitivity worry turns out
to matter less than the resolution choice.

Separately, 1,314 of 37,944 pair-evaluations (3.5%) had at least one direction where the
estimator did not return a usable estimate. They are excluded from certification, which is
conservative.

## What this licenses

**Calibrate at `delta = 0.20` only.** It is the sole resolution where the upper bound leaves
room for a conservative test to still do useful work. `delta = 0.05` is closed — an upper bound
of 0.018 cannot survive a stricter rule. `delta = 0.10`, at 0.21, would likely fall to single
digits once both the calibrated critical value and Holm apply, and is not worth the cost.

That narrows a Phase-0 run from three resolutions to one.

It also fixes the product claim's coarseness: at `delta = 0.20` a certified nonedge asserts
that neither variable explains more than 20% of the other's variance given every candidate
conditioning set. That is a real statement, but a coarse one, and it should be worded that way.

## Limitations

* **Nothing here is calibrated**, and no rate is a guarantee.
* **Upper bounds only.** The achievable power is below every `upper_bound` column by an unknown
  margin.
* **`realistic` regime only.** The `strong` regime was excluded because its population ceiling
  of 0.12-0.47 cannot be rescued by finite-sample evidence.
* **`forest_trees = 10`**, matching the comparator gate's benchmark setting rather than the
  packaged profiles' 100. A larger forest may estimate slightly better; this was a tractability
  choice and it changes the fingerprint.
* **102 replications**, so a familywise rate of 0.029 carries a 95% upper bound near 0.07.
* **One sample size.** `n = 375` was inherited because it gives the 300 inference rows the
  existing profiles bind to. Under a new calibration that number is a free choice, and power is
  the binding constraint, so it should be revisited rather than assumed.

## Reproduce

```bash
gh workflow run unanimity-power-probe.yml --ref main
```
