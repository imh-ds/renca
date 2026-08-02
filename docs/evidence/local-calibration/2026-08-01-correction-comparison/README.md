# Exploratory comparison of calibration corrections

The nested-selection 1,000-replication boundary study supplied an independent calibration distribution. Two corrections were evaluated on 300 new replications from the same simple continuous boundary scenario.

| Method | Boundary rejection rate |
| --- | ---: |
| Unadjusted Wald test | 8.3% |
| Bias-recentered estimate with Wald critical value | 8.3% |
| Simulation-calibrated studentized critical value | 5.0% |

The calibrated critical value was the empirical 5th percentile of the independent calibration studentized-statistic distribution: -2.110, versus the standard-normal 5th percentile of -1.645. The simple point-estimate correction (+0.000603) did not solve the problem.

This is promising evidence for calibration of the decision threshold within this exact data-generating family and configuration, but it is not a general inferential solution. A production calibration gate must bind the critical value to a declared scenario family, sample size/folds, learner configuration, and simulation evidence; it must be validated over an independent grid before enabling certification.
