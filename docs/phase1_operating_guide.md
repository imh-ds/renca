# Phase 1 operating guide

The only profile that can issue a hard `certified_nonedge` is
`v3-nested-blend-n300-d005-phase0`. It is a predictive practical-separation
result, never a causal nonedge or direction claim.

## Run the bundled calibrated pilot

From the repository root:

```powershell
python examples/phase1_calibrated/generate_data.py
renca run --config examples/phase1_calibrated/project.yaml --data examples/phase1_calibrated/phase1_calibrated_data.csv --output build/phase1-calibrated
```

The generator writes 375 complete cases. With the default 20/80 split this
creates exactly 75 selection rows and 300 inference rows, as required by the
validated profile. The configuration fixes 5 folds, `delta: 0.05`,
`v3_nested_blend`, and 10 forest trees. Changing any of those settings,
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

**This index does not indicate whether results can be believed.** The threshold study
in `docs/evidence/phase1/fit-index-thresholds-pilot/` measured false-prune rates
across adequacy bins and found no relationship: 0.015, 0.000, 0.000, 0.000, 0.030,
0.000, 0.024 from the lowest bin to the highest. Reading high adequacy as "safe"
would claim a protection the index does not provide.

What it does track, monotonically, is how many genuinely unrelated pairs get
resolved. Use it to anticipate yield:

| observed predictive adequacy | share of truly unrelated pairs expected to resolve |
|---|---|
| 0.40 and above | about three quarters |
| 0.20 to 0.40 | about two thirds |
| 0.05 to 0.20 | about half |
| 0.02 to 0.05 | just under half |
| above 0 to 0.02 | about a third |
| at or below 0 | nothing is interpretable; see below |

These are **provisional**, from a 1,200-replication pilot on one synthetic design, and
they are the scale of the effect rather than precise rates. Your own yield depends on
the structure actually present. The bands are deliberately not labelled good or
acceptable: they describe what to expect, and whether that answers your question is
your judgement, not the software's.

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
