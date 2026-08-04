# Phase 1 synthetic pilot protocol

**Source and authorization:** deterministic generator in
`examples/phase1_calibrated/generate_data.py`; no restricted data are used.

**Population and variables:** 375 independent synthetic tabular observations
with three continuous process variables sharing a noisy common driver. The
pilot evaluates operational behavior rather than a causal hypothesis.

**Pre-analysis decisions:** complete-case analysis; all three nodes use squared
loss and `delta=0.05`; the fixed Phase-0 profile and its 20/80 selection split
are required. Interpret all outputs as predictive, with no causal promotion.

**Review record:** retain the generated data, configuration, all output
artifacts, and counts of certified, candidate, unresolved, abstention, and
`full_worse_than_reduced` results. Unexpected diagnostics require investigation
rather than suppression.
