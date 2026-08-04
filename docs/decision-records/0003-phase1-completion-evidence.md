# Phase 1 completion evidence and options

**Status:** open. This record assembles the evidence for the Phase 1 completion
decision and states the options. It does not select one.

## Evidence

### Operational pilot

[`0002-phase1-pilot-decision.md`](0002-phase1-pilot-decision.md) recorded a
reproducible calibrated run on the bundled synthetic protocol: audit eligible,
exact profile match, 6 successful directional estimates, and a mixed ledger of
one certified nonedge, one candidate adjacency, and one unresolved pair. Its
counts and diagnostics still hold after the separator-ranking change; only a
separator it does not record differs.

That pilot is 3 nodes and 3 pairs. It demonstrates operability, not usefulness on
representative data, and Phase 1B still requires a public or authorized tabular
pilot.

### Multi-pair familywise error study

[`docs/evidence/phase1/multipair-fwer-2blocks-n375/`](../evidence/phase1/multipair-fwer-2blocks-n375/README.md)
records 5,000 replications of a 6-node, 15-pair configuration at `n=375` under
the validated profile.

| Specification section 44 criterion | Result |
|---|---|
| 1. Familywise error at the boundary | **Passes.** 0.0008 observed, 95% upper bound 0.00183 against alpha=0.05 |
| 3. Prunes a useful fraction of true nonedges | **Fails.** 2.18% of exact nonedges certified |
| 4. Unresolvedness | **Fails.** 82.9% of replications certified no true nonedge at all |

Separator recovery was 10,000/10,000, so the boundary pairs were genuinely tested
at `theta = delta` and the error result is not conservative by accident.

## Interpretation

Error control is real and was measured on the shipped code path, including the
data-dependent shrinkage of the Holm family that abstention causes. The estimator
is behaving correctly: true-nonedge directional statistics reach a median
studentized value of -7.46 against a critical value of -3.095.

The pruning failure is a decision-rule problem, not an estimator problem. A true
nonedge drives `psi` below zero roughly half the time, which raises
`full_worse_than_reduced`, which blocks calibration, which removes the pair from
the Holm family before it is ever tested. The rule fires hardest on exactly the
pairs the method exists to prune, and `theta_hat < 0` is the strongest available
evidence of practical irrelevance.

The readiness plan requires that `full_worse_than_reduced` never be treated as
evidence *of* a nonedge. The implementation additionally treats it as blocking
evidence *against* certification. Those are different rules, and the difference
is where the pruning power went.

Separately, spending 0.0008 of a 0.05 budget indicates stacked conservatism:
worst-family p-values, the minimum per-family critical value, abstention, the
intersection-union maximum, and Holm. Each is defensible alone.

## Options

**Proceed.** Defensible only for the operational claim. The calibrated route is
reproducible and its scope is visible, but a tool that certifies 2% of exact
nonedges will not be useful on real data, and shipping it invites users to read
`unresolved` as a substantive finding when it is mostly an artifact of the
abstention rule.

**Extend calibration.** Additional inference sample sizes would help, since the
300-row ceiling forces users to discard data. It does not address the pruning
failure, which is not sample-size driven at these effect sizes.

**Redesign, scoped.** Revisit the abstention rule and the conservatism stack,
keeping the estimator. Constraints: `run_independent_grid` scores
`reject = (status == "success") and ...`, so the critical value and null
distribution were computed *with* abstention and a change invalidates the
profile and requires a full Phase-0 recalibration; and abstention does real work
in `learner_misspecification_v1`, which shows a 14.3% ineligibility rate, so it
cannot simply be removed.

## Open questions for the decision

1. Should a negative `theta_hat` be treated as admissible equivalence evidence
   rather than an abstention, with learner adequacy policed by a separate
   diagnostic that does not gate certification?
2. Which layers of the conservatism stack are load-bearing? A study that varies
   one layer at a time would show which are buying safety and which are only
   buying loss of power.
3. Does the familywise result hold at larger node counts? The study covers 6
   nodes; the specification's target operating region is `p=15`.

## Scope of the evidence

Two blocks, 6 nodes, `n=375`, one delta, Gaussian linear blocks, i.i.d. rows.
Familywise control is established for this configuration only.
