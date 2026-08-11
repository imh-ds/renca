# Resolve feasibility protocol

**Status:** awaiting approval. No implementation may begin, and no claim that the
resolve mode is viable under the revised rule may be made, until this protocol is
approved and executed.

**Question:** under universal separator agreement and its own finite-sample
calibration, can `renca resolve` certify practical negligibility often enough to be
useful while keeping whole-network wrongful pruning rare, and over what region of
sample size, variable count and resolution? The answer defines the operating
region for the mode. As with explore, a finding that the region is empty at
affordable sample sizes is a valid and reportable outcome.

**The minimizing separator rule is rejected and may not be used.** The
`rank_separators` implementation at
[`separators.py:71`](../../src/renca/screening/separators.py) selects the
separator that minimizes bidirectional importance. The k-sweep falsified the
policy that rule serves: requiring the top five candidates to agree still left
73% of networks containing at least one wrongfully deleted edge, and only
agreement across the entire pool met a 5% familywise bar. Freezing the VIMP and
cross-fitting infrastructure does **not** freeze that rule, and any run under this
protocol that invokes ranking is void.

**No existing calibration transfers.** Every shipped profile was trained at a
different rule, sample size, and configuration. This protocol calibrates from
scratch at each configuration it evaluates, and no profile produced elsewhere may
be substituted.

---

## The rule under test, stated exactly

For an unordered pair `(i, j)`, the **separator pool** is the empty set together
with every singleton `{k}` for `k` outside `{i, j}` — that is `p - 1` candidates,
enumerated, never ranked.

The pair is certified negligible only when **every** candidate in the pool
supports practical negligibility in **both** directions. Otherwise the pair is a
retained candidate relationship or unresolved, by the existing three-state logic.

**Why the pool is enumerated rather than sampled.** The k-sweep result was a cliff,
not a slope: familywise wrongful pruning ran between 0.22 and 0.32 at `k = 13` and
fell to between 0.00 and 0.01 at `k = 14`. Nothing short of the whole pool
qualified. A pool defined by any rule other than complete enumeration reintroduces
the failure the sweep established.

**Maximum separator size is one.** The earlier small-network study identified this
as the binding constraint on usefulness, and lifting it is a separate question
with its own combinatorial cost. It is fixed here so that the agreement rule is
what is being measured.

---

## Stage 1 — calibration

For each `(n, delta)` configuration under evaluation, run a full Phase-0
calibration against the five frozen scenario families, boundary-tuned so oracle
`Theta` lands exactly on `delta`.

**Pass criterion:** the resulting record must reach `status = "validated"` under
the existing registry gate in
[`validation.py`](../../src/renca/calibration/validation.py) — at least 5,000
successful replications per family and a 95% upper rejection bound at or below
`alpha` for every family. A configuration whose calibration does not validate is
ineligible and proceeds no further; that is a result, not a setback.

**On multiplicity.** Because the pair certifies only when every component clears,
the decision is an intersection-union test, and such a test preserves its level
for any number of components under any dependence between them. No additional
correction across the `p - 1` candidates is therefore required, and none should be
introduced. This is a structural argument, not a measured one, and Stage 2 exists
partly to check that it survives contact with finite samples.

---

## Stage 2 — network evaluation

**Grid.** `p` in {6, 8, 10} x `n` in {300, 1000, 3000} x two benchmark truths
(linear, nonlinear) = 18 fitting cells, 200 replications each. Each cell is scored
at `delta` in {0.05, 0.10, 0.20}.

**Scoring at three resolutions costs nothing extra.** The VIMP estimates do not
depend on `delta`; it enters only the decision. One set of fits is therefore scored
under all three, which is a threefold saving and is the reason the grid is
affordable at all.

**Truth.** Known networks with a degree cap and the same rejection-sampling guard
used elsewhere in this chain, guaranteeing at least two genuine edges and at least
two genuine nonedges per graph so no cell scores trivially. Real edges are labelled
strong or weak by a threshold fixed before the run, and wrongful pruning is
reported separately for the strong class, because pruning a strong real edge is
the most damaging single error the mode can make.

---

## Metrics and fixed pass/fail criteria

A cell is **eligible** only if criteria 1, 2 and 4 pass. The set of eligible
`(p, n, delta)` cells is the operating region, and it is the artifact the
pre-analysis audit consults.

| # | Metric | Pass criterion |
|---|---|---|
| 1 | Probability a network contains at least one wrongful prune | 95% upper bound `<= 0.05` |
| 2 | Share of genuinely absent pairs certified | `>= 0.30` |
| 3 | Unresolved rate | reported, not gated |
| 4 | Runtime per network, single core | `<= 4 core-hours` |

**1 — the bound, not the point estimate.** House practice throughout this chain is
to report the exact Clopper-Pearson upper bound, and the criterion is stated
against it so that a cell cannot pass on a favourable draw at 200 replications.
Wrongful pruning of *strong* real edges is reported separately and any nonzero
value must be stated prominently even where criterion 1 passes.

**2 — usefulness, and why 0.30.** Below roughly a third of genuine nonedges
certified, the mode answers almost nothing and a researcher is left with a wall of
unresolved pairs. The earlier power probe at `n = 375` reached 0.018, 0.208 and
0.422 at the three resolutions, so this bar is expected to select coarse `delta`
and larger `n` — which is the operating region being mapped, not a failure.

**3 — unresolved rate is the complement and is deliberately not gated.** A high
unresolved rate is honest behaviour, not an error. It is reported so that safety
bought by refusing to answer is distinguishable from safety with retained power.

**Conservatism must be visible, not assumed.** Report criterion 1 and criterion 2
together in every cell. A cell that passes on wrongful pruning while failing on
useful pruning has not demonstrated a safe method; it has demonstrated a silent
one.

---

## Cost, stated before approval

Measured single-core cost of one pair-direction at the `v4` library: 4.7s at
`n = 300`, 5.5s at 1,000, 7.8s at 3,000.

* **Stage 1** is roughly 33 core-hours per `(n, delta)` configuration at `n = 300`,
  rising to about 54 at `n = 3,000`. Across nine configurations this is on the
  order of 350 core-hours.
* **Stage 2** is roughly 2,700 core-hours for the full grid — on the order of three
  days of continuous GitHub Actions at the current concurrency, and it must be
  sharded finely to stay inside the per-job time limit.

**Recommended staging.** Do not dispatch the full grid first. Run one
configuration end to end — `p = 8`, `n = 1,000`, both truths, 200 replications,
approximately 120 core-hours — to confirm the machinery and give a first read on
criteria 1 and 2. Fan out only if that pilot is promising. A full grid dispatched
before the pilot risks spending three days of CI to learn something the pilot
would have shown in three hours.

---

## Limits this study does not exceed

* It establishes nothing about causal direction. No directional quantity is
  produced or reported.
* It establishes nothing about `renca explore`. The two modes condition on
  different sets and measure different quantities; neither calibrates the other,
  and their networks are not comparable as precision levels of one picture.
* It establishes nothing outside the exact configuration calibrated in Stage 1 —
  sample size, variable count, learner configuration, and threshold.
* `max_separator_size = 1` throughout. Nothing here speaks to larger separators.
