# Empty-separator pilot — GO, and the hazard is somewhere else

GitHub Actions run
[31364918159](https://github.com/imh-ds/renca/actions/runs/31364918159), 2026-08-10, all 6
jobs successful. 1,500 replications, each run through both conditioning modes, `n = 300`
inference rows, 5 folds, `delta = 0.20`, v4 library at `forest_trees = 100`.

Step 0 of the `delta = 0.20` calibration scope. Every Phase-0 scenario conditions on exactly
one variable, so the empty conditioning set that universal agreement also requires had never
been calibrated — and it gates the whole rule, since **every** pair must clear the empty-set
check.

**Verdict: GO. The empty conditioning set is not a hazard, and in the cells that matter most
it is the safer of the two.** The concern that motivated this pilot does not survive it.

## Design

Following the threshold study's parameterisation,

    y = sqrt(A) f(z) + sqrt(T) g(x) + sqrt(1 - A - T) e

gives `R(empty) = 1`, `R({z}) = 1 - T` and `R({x}) = 1 - T`, so **`Theta = T` under either
conditioning set**. The same rows therefore go through `S = {z}` and `S = {}` with the
identical estimand at the identical boundary, and any difference in the statistic is
attributable to the empty set alone rather than to a change of target. `T = delta = 0.20`, so
every replication sits exactly where a critical value is read. `A = 0.35`.

## The paired comparison

`implied_critical_value` is the 4% quantile of the studentized statistic, the quantile Phase 0
reads its critical value from. `resolution_floor` is `|critical| x se` — the finest `delta` a
pair whose estimate is exactly zero could certify.

| separator shape | added shape | critical (empty) | critical (single) | floor (empty) | floor (single) |
|---|---|---|---|---|---|
| linear | linear | -2.026 | -1.995 | 0.085 | 0.067 |
| cubic | linear | -2.379 | -2.334 | 0.107 | 0.098 |
| oscillatory | linear | -2.555 | -3.335 | 0.106 | 0.143 |
| linear | cubic | -5.236 | -6.054 | **0.278** | **0.281** |
| linear | oscillatory | -6.401 | **-13.064** | 0.204 | 0.262 |

Pooled: empty `-4.577`, single `-9.681`. Every replication was usable in both modes; there were
no non-finite statistics and no abstentions.

The empty conditioning set is level with the single separator wherever both are learnable, and
markedly better wherever they are not. The worst cell in the study — an unlearnable added
variable — is twice as extreme with a separator as without one, because the separator lets
`se` collapse to 0.020 while the bias grows to -0.129, and a small standard error under a large
negative bias is what produces a statistic of -13.

## The real finding is about sample size, not the empty set

Two cells have a **resolution floor above the delta being calibrated**, in *both* modes:

* `linear` / `cubic`: floor 0.278 and 0.281 against `delta = 0.20`
* `linear` / `oscillatory`: floor 0.204 and 0.262

A floor above `delta` means a pair whose true `Theta` is exactly zero still cannot be certified
at that resolution — the data cannot resolve that finely, whatever the truth is. At `n = 300`,
against a cubic added variable, `delta = 0.20` is simply out of reach.

Since the floor scales with `se`, and `se` scales with `1/sqrt(n)`, bringing 0.278 under 0.20
needs roughly **double the inference rows — about 600, so around 750 total**. That is a concrete
target, and it is the same constraint the power probe ran into: this is why its correct-pruning
upper bound sat at 0.42 rather than near the 0.78 population ceiling.

## Two things this pilot does not establish

**The absolute levels are not comparable to shipped profiles.** This scenario mix is harsher
than the Phase-0 families — the pooled single-separator critical value here is `-9.68` against
the shipped `-3.084` at the same `delta`. The **paired** comparison is internally valid because
both modes see identical rows; the absolute numbers are not a substitute for a real
calibration, and this pilot produces no profile.

**Separator shape is inert in the empty mode.** With `S = {}` the variable `z` never enters the
fit, so the three `*/linear` empty rows differ only in the shape of the unconditioned part of
`y`. Read the empty column as two distinct conditions — a learnable added variable and an
unlearnable one — rather than five.

## What this changes about the scope

Step 1 was scoped as "calibrate `delta = 0.20` at 300 inference rows", with a sample-size ladder
held back as Step 3 in case power fell short. The floors say it will fall short: at `n = 300`
the cubic cell cannot reach `delta = 0.20` even in principle.

**Fold the ladder into Step 1 and calibrate at 300 and 600 inference rows together.** Running
300 alone would spend a full Phase-0 cycle to confirm a limit this pilot has already measured.

## Reproduce

```bash
gh workflow run empty-separator-pilot.yml --ref main
```
