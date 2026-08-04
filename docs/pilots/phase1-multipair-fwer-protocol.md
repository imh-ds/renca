# Multi-pair familywise error protocol

**Question:** specification section 44 falsification criterion 1 asks whether
familywise false pruning is controlled at the practical-equivalence boundary.
The Phase-0 profile establishes only the marginal behaviour of a *single*
directional hypothesis with a fixed, known separator, so it cannot answer this.

**Source and authorization:** deterministic generator in
`src/renca/calibration/multipair.py`; no restricted data are used.

**Design:** each replication draws `blocks` independent three-node blocks. Within
a block `z` is a common cause of `x` and `y`, whose residuals carry correlation
`rho` with `rho**2 = delta * (loading**2 + 1)`, placing *both* directional
normalized VIMPs exactly at `delta`. Both directions matter because the pair test
takes the maximum of the two directional p-values; a block with only one side at
the boundary would be dominated by the other and would make the familywise check
vacuously conservative. Cross-block pairs are exact nonedges and measure pruning
power on the same runs.

**Null hypotheses:** every within-block pair. The `x--y` pairs sit exactly on the
boundary; the `z--x` and `z--y` pairs are far above it. Certifying any of them is
a false prune. `familywise_error` is true when a replication certifies at least
one of them.

**Pre-analysis decisions:** 375 complete cases yielding exactly 300 inference rows
under the default 20/80 split, 5 folds, `delta=0.05`, `alpha=0.05`, the
`v3-nested-blend-n300-d005-phase0` profile, and its exact learner configuration.
Any deviation makes the run uncalibrated and unable to certify, which is itself a
valid recorded outcome.

**Conservatism must be visible, not assumed.** Reaching the boundary requires the
pipeline to recover `z` as the separator. A replication that fails to recover it
tests a pair further from equivalence and is therefore conservative, so
`separator_recovery_rate` is reported alongside the error rate; a low recovery
rate would mean the familywise result is weaker evidence than it appears.

**Review record:** retain every shard, the assembled results Parquet, and the
summary JSON. Report the exact Clopper-Pearson upper bound rather than the point
estimate alone, and report the abstention rate and true-nonedge certification
rate so that error control bought by refusing to answer is distinguishable from
error control with retained power.
