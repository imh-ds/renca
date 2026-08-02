# Independent calibration-grid smoke run

This is a deliberately small, independent stress run: 20 seeded replications
per family, `n=300`, five inference folds, and the previously exploratory
linear-scenario critical value `-2.1099877626362535`.  It is **not** eligible
to open the calibration gate: the protocol requires 5,000 calibration
replications and 5,000 independent validation replications in every family.

| Scenario family | Rejections / 20 | Rate |
| --- | ---: | ---: |
| continuous linear boundary | 12 | 60% |
| bounded composite, unsaturated | 8 | 40% |
| bounded composite, saturated | 11 | 55% |
| nonlinear continuous | 15 | 75% |
| learner misspecification | 0 | 0% |

The results show that the linear-scenario critical value does not transfer to
the broader grid.  This is a useful negative result: the formal registry
correctly records it as `rejected`, and no production VIMP estimate can receive
`calibrated_success` from this evidence.  The raw per-replication table and
machine-readable summary are retained alongside this note.
