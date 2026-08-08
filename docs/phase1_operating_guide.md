# Phase 1 operating guide

Two profiles can issue a hard `certified_nonedge`. **Use
`v4-cubic-blend-n300-d005-phase0`**, which the bundled example declares;
`v3-nested-blend-n300-d005-phase0` remains valid for analyses already bound to
it. Either way the result is predictive practical separation, never a causal
nonedge or direction claim.

## What the estimator can and cannot see

The estimator decides that a variable does not matter by failing to predict better
with it. A relationship whose *shape* the learner library cannot represent is
therefore invisible, and the tool reports absence rather than uncertainty.

v4 offers a linear, a quadratic, a cubic, and a forest member, blended by
cross-validation. Measured recovery of a relationship worth `Theta = 0.05`:

| shape | v3 | v4 |
|---|---|---|
| linear | 102% | 106% |
| exponential decay | 57% | — |
| parabola | 77% | 78% |
| **cubic** | **−4%** | **46%** |
| four or more turning points | 23% | 34% |

v3 recovered *nothing* of a cubic and false-pruned true cubic edges at up to 9.7%,
against `alpha = 0.05`. Under v4 that falls to at most 0.2%. Since social and
behavioural research reports non-linearity mainly as exponential change,
parabolas, and occasionally cubics, v4 covers the usual range and v3 did not.

**The boundary, stated plainly.** For relationships with four or more genuine
turning points, both libraries remain biased and false pruning can exceed `alpha`
— measured at 7.5% and 9.9% in the two highest-adequacy cells under v4, slightly
worse than v3 because v4's critical value is less extreme. Shah and Peters (2020)
show no method can be valid against every functional form without assumptions, so
every method has such a boundary; this is where ours sits.

**Unlike the other scope limits, this one cannot be checked.** You can count your
sample, inspect your outcome type, and confirm your design. You cannot inspect a
dataset and determine whether the true relationship has four turning points — if
you could see it, the estimator could too. Treat "no relationship past cubic" as
an assumption the analysis rests on, and say so when reporting.

## Run the bundled calibrated pilot

From the repository root:

```powershell
python examples/phase1_calibrated/generate_data.py
renca run --config examples/phase1_calibrated/project.yaml --data examples/phase1_calibrated/phase1_calibrated_data.csv --output build/phase1-calibrated
```

The generator writes 375 complete cases. With the default 20/80 split this
creates exactly 75 selection rows and 300 inference rows, as required by the
validated profile. The configuration fixes 5 folds, `delta: 0.05`,
`v4_cubic_blend`, and 10 forest trees. Changing any of those settings,
including a node-specific delta, makes certification unavailable.

## Eligible inputs

Use independent rows and continuous squared-loss targets only. Bounded
composites may be declared with `measurement_level: bounded_composite`, scale
bounds, and `continuous_approximation: true`; the audit must approve their
resolution and boundary mass. Raw ordinal items are ineligible. Binary,
clustered, other sample-size, fold, delta, and learner configurations may
produce exploratory evidence but are outside this calibrated profile.

## Read the evidence

The run writes the audit, split, separator candidates, VIMP estimates,
certificates, `resolution_graph.json`, `resolution_graph.graphml`, edge table,
HTML report, `calibration_eligibility.json`, and an
`evidence_bundle_manifest.json`. The HTML report renders the predictive
ResolutionGraph: solid lines are candidate adjacencies, dashed lines are
unresolved, and certified practical nonedges are deliberately absent while
remaining available in the evidence panel and GraphML audit trail. Line width
encodes directional predictive importance, not a causal effect size. The eligibility artifact names the requested
profile, matching record, and every blocking field. `certified_nonedge` means
both directional predictive gains passed calibrated equivalence testing;
`candidate_adjacency` means no searched separator established practical
separation; `unresolved` means the evidence was insufficient. Abstention and
`full_worse_than_reduced` are diagnostics, never evidence of a nonedge.

`full_worse_than_reduced` now fires only when the expanded model is worse by more
than `nested_safeguard_materiality_z` standard errors *and* in at least
`nested_safeguard_fold_fraction` of folds. Both live in the `vimp` block, so
changing either invalidates any matched profile. The per-estimate
`nested_safeguard` diagnostic records the studentized value, the fold fraction,
and which condition failed, so an abstention can always be traced to its cause.

## Network fit

Every run writes `network_fit.json` and leads the HTML report with indices computed
automatically, requiring no configuration.

Two questions are kept separate throughout, and conflating them is the main way to
misread this report:

- **Can I trust this result?** Answered by the calibration profile. Under a matched
  profile, false pruning is controlled at `alpha`, and that holds whatever the fit
  indices say.
- **How much will this analysis resolve?** Answered by the fit indices below. They
  say nothing about trust.

### Predictive adequacy — expected yield, not trustworthiness

`1 - R(S) / R(empty)`: the share of a target's baseline predictive uncertainty that
the conditioning model actually removed.

**This index does not indicate whether results can be believed, and with respect to
one failure mode it points the wrong way.** The 30,000-replication threshold study in
`docs/evidence/phase1/fit-index-thresholds/` measured both rates across adequacy bins:

| observed predictive adequacy | truly unrelated pairs resolved | false prunes, unlearnable added variable |
|---|---|---|
| 0.40 and above | 0.771 | 0.047 |
| 0.20 to 0.40 | 0.652 | 0.029 |
| 0.10 to 0.20 | 0.537 | 0.013 |
| 0.05 to 0.10 | 0.487 | 0.009 |
| 0.02 to 0.05 | 0.451 | 0.006 |
| above 0 to 0.02 | 0.427 | 0.004 |
| at or below 0 | 0.398 | 0.002 |

Both columns rise together. Higher adequacy means more of the structure resolves **and**
more exposure to the one failure mode that produces false prunes. Read it as expected
yield; reading it as a quality mark inverts its meaning with respect to safety.

The reason is worth understanding. When the added variable's contribution cannot be
represented by the learner library, `theta_hat` is biased sharply downward and stays
biased regardless of adequacy. What adequacy buys is a smaller standard error. Precision
applied to a biased estimate produces a confident wrong answer, so the better your
separator, the more readily that bias clears the certification threshold. In cells where
the added variable was learnable the study saw **zero** false prunes in 5,000
replications, so this is specifically a learner-adequacy exposure, not a general one.

Yield figures come from one synthetic design; your own depend on the structure actually
present. The bands are deliberately not labelled good or acceptable: they describe what
to expect, and whether that answers your question is your judgement, not the software's.

The one hard statement is a degenerate case rather than a cut-off. Adequacy at or
below zero means the conditioning models explained none of the outcome variance, so
the contrast underlying every pair state was uninformative. A dataset of pure noise
resolves *every* pair as a certified nonedge for exactly this reason. That is not a
false certification, but it is indistinguishable from a discovery, and the report
says so plainly.

### Resolution floor — the finest question your data can answer

The finest `delta` the analysis could certify at all, for a pair whose estimate is
exactly zero. It is a precision measure: it combines sample size, data quality, and
learner performance through the standard error, so a small clean sample can resolve
more finely than a large noisy one. If the floor is coarser than your requested
`delta`, most pairs cannot certify regardless of their true values, and the report
says that explicitly rather than leaving it to appear as an unexplained wall of
unresolved pairs.

Treat this as the primary planning quantity. Rather than asking whether your sample
is large enough, run the analysis and read the floor: it tells you the resolution
your data supports, and `delta` should be set at or above it.

### Choosing delta

`delta` is the question you are asking: how small a contribution counts as practically
nothing. Set it too fine and pairs come back `unresolved` regardless of the truth, which
looks like a failed analysis but is a mismatch between the question and the data.

**Do not set `delta` from sample size.** It is tempting to reach for a rule like "n=300, so
use 0.17", and it is wrong. Resolution is governed by the standard error, which combines
sample size *and* how cleanly the separator predicts the target. The same `n=300` gave a
resolution floor of **0.024** in a study of near-independent variables and **0.165** on the
bundled example, where the variables are genuinely related and residual variance is
therefore larger. A clean small sample can out-resolve a noisy large one.

**Read the floor from your own run instead.** Every analysis reports the resolution floor
and a resolution path:

| delta | pairs the data could place below it | status |
|---|---|---|
| 0.020 | 0 of 3 | descriptive |
| **0.050** | **1 of 3** | **primary, calibrated** |
| 0.100 | 1 of 3 | descriptive |
| 0.400 | 3 of 3 | descriptive |

That is the bundled example. It says plainly that two of its three pairs are unresolved
because 0.05 is finer than this data supports, not because the variables are related.

**A caution that matters more than it looks.** The path is descriptive. Only the primary
`delta` has a calibrated profile, so the other rows carry no error guarantee, and reading
the path and *then* choosing a primary resolution destroys the error control entirely --
that is selecting a hypothesis after seeing the answer. Specification section 27 requires
the primary `delta` to be fixed before analysis, and the path exists to inform the *next*
study's design, or to explain the present one, not to reselect within it.

**Raising `delta` needs a profile at that value.** Only `delta = 0.05` is calibrated today.
A study needing 0.10 or 0.20 requires its own Phase-0 run before it can certify anything;
until then such a configuration produces evidence but reports `calibration_failed`. If the
path repeatedly shows your data supports only coarser resolutions, that is the argument for
calibrating one.

### Achieved resolution — the per-pair bound

The per-pair upper limit on `Theta`. Unlike the floor it moves with effect size, so a
network of strong genuine relationships shows large values; that is a property of the
data, not a defect of the analysis. It is reported per pair in `edge_report.parquet`
and stays meaningful for unresolved pairs, where "Theta is at most this" is
informative even without a certificate.

### Why there are no cut-offs

The measured relationship between adequacy and yield is a smooth gradient with no
discontinuity anywhere in it, so any bright line would impose structure the evidence
does not contain. Conventional cut-offs of the kind SEM provides came from simulation
studies mapping index values to error rates, and have themselves been criticised for
being treated as pass marks when the underlying simulations showed continuous
trade-offs. `thresholds_are_validated` is `false` in the artifact to keep this
visible. Report the index value and the yield you observed; that is more informative
than a threshold and easier to defend.

Archive the complete output directory outside the package. Treat runs without
`calibrated_success` as exploratory and keep `not_yet_causal` in every
downstream description.
