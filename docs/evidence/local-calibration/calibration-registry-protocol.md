# Calibration registry protocol

Each candidate VIMP critical value is bound to a profile ID, target delta,
inference-row count, number of inference folds, alpha, and a SHA-256
fingerprint of the complete `VimpSpec`. Changing any of these creates a new
calibration problem.

The independent validation grid must include these five families:

- a continuous linear boundary case;
- an unsaturated bounded composite;
- a saturated bounded composite;
- a nonlinear continuous relationship; and
- a learner-misspecification case.

For every family, the gate requires at least 5,000 independent evaluation
replications and a one-sided 95% binomial upper bound on the false-certification
rate no larger than 0.05. It also requires at least 5,000 successful
calibration replications used to establish the critical value. A smaller run
is useful diagnostic evidence, but is always recorded as `rejected` and cannot
mark VIMP artifacts `calibrated_success`. Full-worse estimates remain unable
to certify and are reported as an abstention/power diagnostic; their frequency
does not itself invalidate false-certification calibration.

Every family is first boundary-tuned with an independent oracle Monte Carlo
calculation before it enters the train/validation ledger. The calibrated
directional p-value is the maximum family-specific empirical left-tail p-value
with plus-one smoothing. The profile also records the worst-family alpha
critical value. `renca.calibration.run_independent_grid` produces the
seed-traced ledger and `simulations/run_calibration_grid.py` writes its training
distribution, disjoint validation ledger, tuning metadata, and summary record.
The published 1,000/300 linear comparison remains rejected preliminary
evidence, not a production calibration.
