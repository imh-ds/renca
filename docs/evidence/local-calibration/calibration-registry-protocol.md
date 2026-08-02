# Calibration registry protocol

Each candidate VIMP critical value is bound to one scenario family, sample size,
number of inference folds, and a SHA-256 fingerprint of the complete `VimpSpec`.
Changing any of these creates a new calibration problem.

The independent validation grid must include these five families:

- a continuous linear boundary case;
- an unsaturated bounded composite;
- a saturated bounded composite;
- a nonlinear continuous relationship; and
- a learner-misspecification case.

For every family, the gate requires at least 5,000 independent evaluation
replications and a one-sided 95% binomial upper bound on the false-certification
rate no larger than 0.05.  It also requires at least 5,000 calibration
replications used to establish the critical value.  A smaller run is useful
diagnostic evidence, but is always recorded as `rejected` and cannot mark VIMP
artifacts `calibrated_success`.

`renca.calibration.run_independent_grid` produces a deterministic, seed-traced
table for the grid.  `validate_grid` reduces it to a registry record.  The
published 1,000/300 linear comparison is deliberately retained as a rejected
record: it is preliminary evidence, not a production calibration.
