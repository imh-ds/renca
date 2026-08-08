# Handoff — state as of 2026-08-08

Working note for continuing in a fresh session. Read
[`outline/phase_1_operational_readiness_plan.md`](../outline/phase_1_operational_readiness_plan.md)
and [`docs/phase1_operating_guide.md`](phase1_operating_guide.md) first; this only covers
what changed recently and what is still open.

## In flight right now

Two Phase-0 calibrations dispatched from branch `feat/calibrate-additional-deltas`
(PR not yet opened):

| run | delta | profile id |
|---|---|---|
| [31245842503](https://github.com/imh-ds/renca/actions/runs/31245842503) | 0.10 | `v4-cubic-blend-n300-d010-phase0` |
| [31245856537](https://github.com/imh-ds/renca/actions/runs/31245856537) | 0.20 | `v4-cubic-blend-n300-d020-phase0` |

Each is ~50 minutes; they queue against the 20-concurrent-job cap, so expect ~2 hours
total. Both use `v4_cubic_blend` at `n=300`, five scenario families, `critical_quantile`
0.04.

**When they finish:** download `phase0-calibration-evidence`, check
`calibration_summary.json` says `"status": "validated"`, archive to
`docs/evidence/phase0/v4-cubic-blend-n300-d0{10,20}/` with a README, add the records to
`src/renca/data/calibration/registry.yml` alongside the existing two, copy each
distribution parquet into `src/renca/data/calibration/<profile-dir>/`, and extend the
parametrised test in `tests/test_calibration_registry.py` that asserts every packaged
profile is an exact validated match. The v4 adoption commit (`284d571`) is the pattern to
copy.

**If either is rejected:** the likely cause is the same one that failed the first v4
attempt — `learner_misspecification_v1` sets the critical value and its upper bound lands
above `alpha`. See
[`docs/evidence/phase0/v4-cubic-blend-n300-d005/README.md`](evidence/phase0/v4-cubic-blend-n300-d005/README.md)
for the mechanism and the sub-alpha quantile fix already in place.

## What is settled

**The estimator and its decision rules.** Four real defects were found and fixed:
separator ranking optimised expanded-model risk instead of incremental importance;
the section 16.4 safeguard abstained on any negative `psi`, discarding the strongest
evidence for a nonedge; the calibration's acceptance margin was supplied by that
abstention rather than by the procedure; and the learner library could not represent a
cubic at all.

**v4 is the default library and profile.** Familywise error 0.0000 with a 0.00060 upper
bound over 5,000 replications, 100% separator recovery, and the cubic false-prune breach
removed (v3 up to 9.7% against `alpha = 0.05`; v4 at or below 0.2%). Costs about a tenth
of pruning power. Evidence in `docs/evidence/phase1/`.

**Reporting.** Network fit indices (predictive adequacy, resolution floor, achieved
resolution) and the section 27 resolution path, both with their limits enforced in the
artifacts rather than only in prose.

## Findings worth not relearning

- **Predictive adequacy is a yield indicator, not a trust one, and is *inversely* related
  to safety.** Higher adequacy means smaller standard errors, and precision applied to a
  biased estimate produces a confident wrong answer. A 30,000-replication study measured
  this; a wording-contract test in `tests/reporting/test_fit.py` stops the framing drifting
  back.
- **Do not set `delta` from sample size.** The same `n=300` gave a resolution floor of
  0.024 in one study and 0.165 on the bundled example. Resolution is governed by the
  standard error, which combines sample size with how cleanly the separator predicts.
- **Recovery tracks representability, not wiggliness.** A cubic and `sin(1x)` both have two
  turning points, but the cubic is orthogonal to `x` and `x^2` by construction and so is
  invisible to the degree-2 members.
- **Forests are not a substitute at `n=300`.** 200 trees at depth 15 recovered −8% of a
  cubic, no better than ten shallow ones, at 11x compute.
- **The scope boundary past cubic is real and unverifiable.** Both libraries stay biased
  there and false pruning can exceed `alpha`. Unlike sample size or outcome type, a user
  cannot inspect data and check it. Documented as an assumption to report.

## Open, in the order I would take them

1. **Finish the two delta profiles** (above). Converts "unresolved with an explanation"
   into certificates for datasets whose floor is coarser than 0.05.
2. **Comparator baselines — the formal Phase 1 blocker.** Specification section 41 requires
   PC, conservative PC, FCI/RFCI, and EBICglasso; none exist in the repository. Section 44
   criterion 3 asks whether the method is "materially better than at least one standard
   comparator", and that is currently unevaluable in either direction. This has been open
   since the first assessment and is the single thing standing between the present evidence
   and a defensible Phase 1 exit.
3. **A representative pilot.** Phase 1B still rests on a three-node synthetic smoke test.
   Needs a public or authorised tabular dataset.
4. **Shard sizing.** Multi-pair shards run ~100 minutes, long enough that one lost runner
   costs a whole run because `summarize` needs every shard. Halving
   `replications_per_shard` and doubling the matrix leaves compute and wall clock unchanged
   under the 20-job cap.
5. **Oscillatory shapes.** Deliberately deferred. Fixing them costs power to protect
   against relationships past cubic, which behavioural research reports as rare. Revisit
   only if an application demands it.

## Parked

`feat/unlearnable-scenario-family` holds an unmerged scenario family plus a
`scenario_family_coverage` gate fix, waiting on a decision about how adversarial the
calibration's worst case should be. The frequency as written (`sin(4x)`) is four times past
what behavioural research reports and would push the critical value to about −17, requiring
roughly 7,000 cases to certify anything. The v4 work partly supersedes the question.

## Operating notes

- Tests: `pytest`, 131 passing. CI runs them on Python 3.11–3.14 plus one Windows job.
- Local Python is 3.14 with no editable install; a virtualenv is needed to run the suite.
- All studies shard on GitHub Actions. The public repo is capped at 20 concurrent jobs, so
  throughput past that comes from the per-runner worker fan-out, which defaults to the core
  count (4 on standard runners).
- Every study is seeded by identity rather than execution order, so worker counts and grid
  additions never change results.
