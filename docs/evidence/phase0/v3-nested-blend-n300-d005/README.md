# Superseded Phase-0 profile

**This profile is no longer shipped and must not be used.** It is retained as the
historical record of the first validated Phase-0 run. The current profile is
[`../v3-nested-blend-n300-d005-materiality-q04/`](../v3-nested-blend-n300-d005-materiality-q04/README.md).

It describes an estimator whose nested learner safeguard flagged any negative `psi`,
rather than the specification section 16.4 rule requiring degradation that is material and
consistent across folds. Its `vimp_fingerprint` (`60ffacc5…`) no longer matches the
shipped estimator, so the exact-match gate rejects it automatically.

Its recorded validation is also now understood. The profile cleared the acceptance bar
because ineligible replications cannot reject while remaining in the denominator, so the
family setting the critical value rejected at `alpha * (1 - ineligibility)` =
`0.05 * (1 - 0.143)` = 0.0428, against 0.0434 observed. The margin came from a 14.3%
abstention rate in `learner_misspecification_v1` rather than from the procedure itself.
The criterion was met as written; where the margin came from was not visible at the time.
