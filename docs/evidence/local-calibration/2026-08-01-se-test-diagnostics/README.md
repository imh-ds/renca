# Standard-error and test-calibration diagnostics

## Nested-selection VIMP

From the corrected 1,000-replication boundary ledger, the empirical standard deviation of `theta_hat` was 0.01279 and the mean reported standard error was 0.01198 (ratio 1.068). The standardized statistic had mean -0.209 and standard deviation 1.122. Both slight SE underestimation and negative finite-sample shift contribute to excess left-tail rejection.

## Fixed-ridge isolation

Replacing adaptive learner selection with fixed ridge regression still produced a 9.9% boundary rejection rate in 1,000 replications. Its empirical/mean-SE ratio was 1.026, while the standardized-statistic mean was -0.191. Adaptive selection is therefore not the primary cause.

## Oracle isolation

Using the true reduced, full, and null conditional means in 10,000 replications produced a 6.27% rejection rate. The standardized statistic was nearly unit scale (SD 1.008) with small negative shift (-0.038). This establishes finite-sample non-calibration of the current asymptotic ratio-Wald test itself; learned nuisance models introduce the additional discrepancy.

## Consequence

Do not use an ad hoc standard-error multiplier as the next fix. The next research/engineering work must compare a finite-sample calibration procedure (for example, a studentized bootstrap or a predeclared simulation-calibrated critical value) and a nuisance-bias correction against this same fixed boundary scenario.
