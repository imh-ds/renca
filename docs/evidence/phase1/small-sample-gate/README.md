# Small-sample gate — `delta = 0.20` needs about 300 rows, whatever the learner library

GitHub Actions run
[31437903703](https://github.com/imh-ds/renca/actions/runs/31437903703), 2026-08-10, all 61
jobs successful. 600 replications per cell across three learner libraries, five frozen
scenario families and four sample sizes: 36,000 fits at `delta = 0.20`, `forest_trees = 100`,
5 inference folds. Supersedes the v4-only run
[31419437023](https://github.com/imh-ds/renca/actions/runs/31419437023), whose v4 cells this
run reproduces to the digit.

Step A of the recalibration. Psychology samples are commonly 100-200, and every number in the
evidence chain rests on `n = 375`, chosen only because it yields the 300 inference rows the old
profiles bind to. This asks whether `delta = 0.20` is reachable lower down.

**Verdict: not reachable below `n = 300` under any of the three libraries. Do not spend Phase-0
cycles at 100, 150 or 200 for this resolution.**

## What decides it

Certification requires

    standard error <= delta / |critical value|

so the *resolution floor*, `|critical value| x se`, is the finest `delta` a pair whose estimate
is exactly zero could reach. A floor above `delta` means certification is impossible at that
resolution whatever the truth is.

Critical values are **not** comparable across libraries — each has its own `vimp_fingerprint`,
so their statistics are not draws from one distribution. Resolution floors are comparable,
because those are what decide usability.

| library | n=100 | n=150 | n=200 | n=300 |
|---|---|---|---|---|
| v2_quadratic_ridge | 0.479 | 0.284 | 0.240 | 0.144 |
| v3_nested_blend | 0.395 | 0.242 | 0.231 | 0.158 |
| v4_cubic_blend | 0.380 | 0.243 | 0.240 | 0.155 |

Every library clears `delta = 0.20` at `n = 300` and none clears it below. Abstention was zero
everywhere except v2 at `n = 100`, at 0.0017 — the estimator runs fine at 100 rows, it simply
cannot resolve finely enough to certify.

**The control cell passed.** The miniature estimates `-3.386` for v4 at `n = 300` against the
shipped profile's `-3.084`, about 10% more extreme, the expected direction for a quantile read
from 600 replications rather than 6,000.

**Reproducibility.** Every v4 cell here matches the earlier v4-only run exactly, because
`replication_seed` derives each replication's seed from its family and index rather than from
execution order. Re-running reproduces the numbers, not merely their distribution.

## The hypothesis this refutes

The v4-only run showed the small-sample failure is **downward bias**, not noise alone: the
binding family's `theta_hat` sat at 0.128 against a true 0.20 at `n = 100`. The proposed
explanation was model selection — at `n = 100` the v4 blend estimates weights for four members
by 3-fold inner cross-validation on 80 rows, and selection noise on that little data is a known
source of downward bias in nested comparisons. The prediction was that a **smaller library
should be less biased**.

**That prediction is wrong, and the result runs the other way.** At `n = 100` the largest
library has the *smallest* floor (0.380 for v4 against 0.479 for v2).

Bias in `theta_hat` on the binding family, against a true 0.20:

| library | n=100 | n=150 | n=200 | n=300 |
|---|---|---|---|---|
| v2_quadratic_ridge | **-0.090** | -0.040 | -0.025 | -0.018 |
| v3_nested_blend | -0.072 | -0.039 | -0.030 | -0.020 |
| v4_cubic_blend | -0.072 | -0.046 | -0.029 | -0.019 |

The interesting part is *which* difference matters. v3 and v4 are indistinguishable at `n = 100`
(-0.0716 against -0.0715), and they differ by a whole extra member. v2 is clearly worse, and it
differs from v3 not in size but in **how it combines members**: v2 selects one by inner
cross-validation, v3 and v4 form a convex blend.

So the mechanism survives while the prescription dies. **Selection noise does drive the bias —
and blending is what mitigates it.** Picking one member is a harder, higher-variance decision
than weighting several, so the library that only ever selects is the most biased. Removing
members removes the blend's ability to hedge, which makes matters worse rather than better.
The direction of any fix is more averaging, not less.

## What each library is for, and where it shows

On `nonlinear_continuous_v1`, whose signal is a sine that no polynomial basis represents
exactly:

| library | n=100 | n=150 | n=200 | n=300 |
|---|---|---|---|---|
| v2_quadratic_ridge | -0.047 | -0.036 | -0.043 | -0.033 |
| v3_nested_blend | -0.028 | -0.023 | -0.024 | -0.020 |
| v4_cubic_blend | -0.032 | -0.023 | -0.026 | **-0.014** |

v4's cubic member earns its place at `n = 300`, halving the bias against v2. It earns nothing at
`n = 100`, where there is not enough data to fit a cubic term reliably in the first place.

That also changes which family binds. `learner_misspecification_v1` binds in eleven of the
twelve cells; the exception is v2 at `n = 300`, where the interaction bias has shrunk enough
that v2's weakness on the sine family takes over.

The linear family is unbiased under every library at every sample size (worst value -0.004),
which is the control that says none of this is a general estimation defect.

## Where the decision now stands

No library choice makes `delta = 0.20` reachable below `n = 300`, and this was the only untried
lever that could have moved the coverage boundary rather than accepted it. The remaining options
are all trade-offs to be chosen rather than problems to be solved:

* **`n` around 300 at `delta = 0.20`** — works today and a profile already exists, but sits
  above the 100-200 range common in the field.
* **A coarser `delta` at smaller `n`** — the floors put the requirement near 0.24 at `n = 200`
  and near 0.38 at `n = 100`. The latter is vacuous for behavioural data, where most effects
  fall below it.
* **Narrower coverage** — excluding `learner_misspecification_v1` clears every rung (floors of
  0.181, 0.137, 0.112, 0.093 under v4). The sample-size requirement is precisely the price of
  covering interaction-carried relationships.
* **Report achieved resolution rather than certificates** — already implemented in
  `renca.reporting.fit`, informative at any sample size, and it converts a wall of unresolved
  pairs into a graded per-pair bound.

## Limitations

* **Not a calibration.** 600 replications per cell against the 5,000 per family the registry
  gate requires; no profile is produced and none of these critical values may be used.
* **Quantile noise.** The 4% quantile of 600 observations is the 24th smallest, so differences
  between adjacent cells of 10-20% are within noise. The non-monotonicity between `n = 150` and
  `n = 200` should be read that way, not as smaller samples helping.
* **The critical value depends on `delta`.** Everything was measured at `delta = 0.20`, so the
  coarser-`delta` figures above are extrapolations rather than measurements.
* **One fold count and one forest size** throughout, matching the shipped profiles.

## Reproduce

```bash
gh workflow run small-sample-gate.yml --ref main
```
