# Boundary calibration after nested learner selection

The 1,000-replication boundary study was rerun after moving learner selection inside each outer training fold. The nominal 5% directional-equivalence rejection rate improved from 10.8% to 9.5%, but its approximate 95% interval (7.7%–11.3%) remains above 5%.

The correction removed one source of validation leakage but did not restore calibration. This engine remains ineligible for `calibrated_success`. The next investigation must assess ratio influence-function variance, learner-selection/tuning uncertainty, and finite-sample behavior rather than proceeding to formal Phase-0 automation.
