# Grid-calibrated VIMP rehearsal

This reproducible rehearsal used two boundary-tuned training replications and
two disjoint validation replications in each of five frozen scenario families,
at `n=300` with five inference folds. It exercises the profile, artifact-hash,
and independent-validation workflow; it is not a Phase-0 result.

The numerical boundary solver reached normalized oracle VIMP `0.05` in every
family (see `boundary_tuning.json`). The worst-family training-tail critical
value was `-3.005`. The independent validation ledger had no rejections, but
with only two replications its one-sided 95% upper bound is 77.6%. Therefore
the profile is correctly recorded as `rejected` and cannot enable hard
nonedge certification.

The future formal run must use at least 5,000 training replications and 5,000
independent validation replications per family before a registry profile can
be marked `validated`.
