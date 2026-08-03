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

Archive the complete output directory outside the package. Treat runs without
`calibrated_success` as exploratory and keep `not_yet_causal` in every
downstream description.
