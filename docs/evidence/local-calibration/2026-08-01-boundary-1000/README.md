# Boundary calibration, 1,000 local replications

## Finding

The current continuous VIMP boundary test rejected practical equivalence in 10.8% of 1,000 replications at a nominal 5% level (approximate 95% interval: 8.9%–12.7%). The configured target was `theta = delta = 0.05`, with 300 observations and five fixed folds. All estimates completed successfully.

This is evidence of anti-conservative inference, not a calibration success. The immediate suspected cause is that the original learner selection chose the lowest-risk candidate using the outer validation fold itself. Subsequent fixes must select learners only from outer-training data and rerun this identical scenario before calibration status can change.

`boundary_1000_summary.json` records configuration and aggregate results. `boundary_1000_results.csv` contains the raw replication ledger.
