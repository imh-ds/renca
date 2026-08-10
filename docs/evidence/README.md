# Evidence chain

An index of every study run against this method, in the order it was run, with what each one
established and what it ruled out. Written so that a methods and results section can be built
from it without re-reading the individual directories.

Two conventions used throughout.

**Population versus finite sample.** Several studies compute exact or large-sample population
values with no sampling and no test. Their rates are *ceilings*: they describe what would
happen with infinite data. A finite-sample rule must also clear a calibrated test, which is
strictly more conservative, so real rates fall below them. Ceilings and measured rates are
never mixed in one column.

**Two truths.** Methods are scored against both graphical adjacency in the generating DAG and
*practical* absence at the resolution under test — adjacency minus edges whose oracle `Theta`
falls at or below `delta` in both directions. Neither is honest alone: scoring only on
adjacency charges the method for correctly reporting a negligible edge, and scoring only on
practical absence quietly changes the question to the one this method happens to answer.

---

## 1. Estimator and calibration

| study | directory | what it established |
|---|---|---|
| Phase-0 calibration, v3 | `phase0/v3-nested-blend-n300-d005` | first validated profile at `delta = 0.05` |
| Materiality safeguard | `phase0/v3-nested-blend-n300-d005-materiality-q04` | a bare `psi < 0` test suppresses exactly the pairs the method exists to certify; replaced with a materiality-plus-consistency safeguard |
| Learner library shapes | `phase1/learner-library-shapes` | which relationship shapes the library can represent |
| Phase-0 calibration, v4 | `phase0/v4-cubic-blend-n300-d005`, `-d010`, `-d020` | three validated profiles; adding a cubic member fixed a breach the quadratic library could not see |
| Multi-pair FWER | `phase1/multipair-fwer-v4` and predecessors | familywise control across simultaneous pairs, 5,000 replications |
| Fit-index thresholds | `phase1/fit-index-thresholds*` | mapped predictive adequacy onto error rates; established that an unlearnable *added* variable is the binding failure mode, invisible to the adequacy index |

Critical values, all at 300 inference rows: `-4.751` at `delta = 0.05`, `-4.074` at `0.10`,
`-3.084` at `0.20`. The tolerated standard error grows faster than `delta` because the critical
value shrinks as resolution coarsens.

**These profiles validate the estimator for a single directional contrast on a stated
conditioning set. They are not evidence for any separator-selection policy.**

---

## 2. The comparator gate and what it falsified

**[`phase1/comparator-gate`](phase1/comparator-gate/README.md) — verdict `REDESIGN`.** 400
replications at `p = 15`, `n = 375`, against PC, conservative PC, FCI, GES and EBICglasso swept
over their tuning parameters. 0 of 12 operating regions passed, identically under both
scorings.

The governing pattern: **every region that prunes usefully fails familywise control, and every
region that controls error prunes almost nothing.**

Where the method wins, and it is not small — `additive_nonlinear`, strong edges,
`delta = 0.20`: false-prune 0.049 against PC 0.267, FCI 0.281, GES 0.279, EBICglasso 0.235.
The baselines delete roughly three in ten real edges because a cubic edge carries zero partial
correlation. This is why the verdict was `REDESIGN` rather than `STOP`.

Where it loses — `linear_gaussian`, strong, `delta = 0.20`: false-prune 0.157 against GES 0.010
at *higher* pruning. Worst of six on the condition most favourable to everyone.

**The diagnosis, from population values so nothing is sampling noise.** Specification section
15.4 ranks candidate separators by *minimising* cross-fitted bidirectional gain — the same
quantity the equivalence test then evaluates. For a genuinely adjacent pair that is an active
search for the conditioning set under which the pair looks most separated.

Of 708 real edges, 626 carry `Theta > 0.20` given their true parents but only 226 do given the
separator the method chose: 400 real edges driven under the threshold *in the population*. The
certificates are true statements about the chosen set; the error is rendering them as missing
graph edges. Suppression is not confined to weak edges — edges at mean `Theta = 0.713` were
pushed under 0.20 in 42% of cases.

This falsified the section 11 lifting clause verbatim: *direct adjacencies retain bidirectional
conditional importance above the thresholds for every admissible separator.*

---

## 3. Repairing the selection policy

### [`phase1/policy3-agreement-diagnostic`](phase1/policy3-agreement-diagnostic/README.md)

Does requiring the top `k` ranked separators to *agree* remove the suppression? It shrinks it
sharply — wrongful pruning of strong real pairs falls from 0.460 at `k=1` to 0.022 at `k=5` —
but familywise error remains 0.73. Not sufficient.

The mechanism is an asymmetry worth stating in any write-up: a genuinely absent pair is
separated by many candidate sets (mean 12.1 of 14), a suppressed real edge usually by exactly
one (mean 1.9). Agreement keys on that directly, which is why it is not merely a stricter
threshold.

### [`phase1/separator-agreement-feasibility`](phase1/separator-agreement-feasibility/README.md)

Sweeping `k = 1` to 14 finds exactly one value meeting a 0.05 familywise bar: `k = 14`, the
whole candidate pool. Since 14 is the pool size rather than a tuning constant, the finding is
structural:

> **`E_delta` requires universal quantification over the candidate pool, not existential.
> Specification section 10's `exists S` fails this gate; `for all S` passes it.**

The approach to the bar is a cliff, not a slope: between `k = 13` and `k = 14` familywise falls
from 0.22-0.32 to 0.00-0.01 while correct pruning gives up only 0.02-0.15. Every rule short of
unanimity still lets a pair select the sets that flatter it.

Consequences: section 15.4 becomes unnecessary rather than repaired, since with no selection
there is no ranking; and `E_delta` becomes monotone *increasing* in the pool, so a larger
candidate pool turns conservative instead of adversarial.

A decomposition rules out the deflationary reading. Unanimity includes the empty set, so it
could have been a marginal association screen doing all the work. It is not: dropping the empty
set and requiring only the 13 singletons changes nothing to three decimals in any cell, and the
marginal screen alone deletes 1.6-6.1% of real pairs against 0.0-0.1% for unanimity.

### [`phase1/small-network-feasibility`](phase1/small-network-feasibility/README.md)

`p = 15` is not the intended use. At `p = 4` to 10, performance degrades as the network shrinks
in all twelve conditions — but **entirely in usefulness, never in safety**. Correct pruning
falls; unresolved pairs rise; wrongful pruning stays at or below 0.014 and familywise at or
below 0.050 throughout.

The binding constraint is `max_separator_size = 1`: in a dense small network two variables are
typically joined by several routes at once, so no single variable severs them all. Density is
confounded with `p` here, because a fixed degree cap of 3 makes small graphs denser (0.57 at
`p=4` against 0.26 at `p=10`); a density-matched sweep would separate the two.

---

## 4. Does it survive a real sample?

### [`phase1/unanimity-power-probe`](phase1/unanimity-power-probe/README.md)

At `n = 375`, upper bound on correct pruning: **0.018** at `delta = 0.05`, **0.208** at `0.10`,
**0.422** at `0.20`. Wrongful pruning never exceeds 0.010 and familywise never exceeds 0.029
across all 36 cells.

Only `delta = 0.20` survives. Network size barely matters once real data is involved — the
finite-sample rates are flat across `p = 4, 5, 6` where the population ceilings rose steadily
with `p` — so **sample size, not network size, is the binding constraint.** Between 61% and 87%
of pairs remain unresolved.

### [`phase1/empty-separator-pilot`](phase1/empty-separator-pilot/README.md)

Unanimity requires every pair to clear an `S = {}` check, which no Phase-0 scenario had ever
covered. A paired design — identical rows, identical estimand at the boundary, two conditioning
modes — shows the empty set is **level with a single separator where both are learnable and
better where they are not**.

It also located the real limit. Two cells have a **resolution floor above the `delta` being
calibrated, in both modes**: `linear/cubic` at 0.278-0.281 against `delta = 0.20`. A floor above
`delta` means a pair whose true `Theta` is exactly zero cannot be certified at that resolution
whatever the truth is. Clearing it needs roughly double the inference rows, about 600.

---

## 5. Hypotheses this work refuted, including its own

Recorded because a method paper is stronger for them, and because each was tested rather than
argued away.

| hypothesis | test | outcome |
|---|---|---|
| The suppressing separator is a redundant correlate of an endpoint | 267 edges; separator adjacent to an endpoint in 86.6% of suppressed against 85.2% of non-suppressed cases | **refuted** — no difference; the mechanism remains open |
| Requiring agreement would collapse power | true-prune ceiling falls only 0.999 to 0.897 between `k=1` and `k=5` | **refuted**; the binding limitation is familywise, not power |
| Unanimity is really just a marginal association screen | all-14 against 13-singletons-only | **refuted** — identical to three decimals |
| The empty conditioning set is a structural hazard | paired comparison, 1,500 replications | **refuted** — it is the safer mode |
| Unanimity needs new calibration because it is the maximum of `2(p-1)` dependent tests | intersection-union preserves level for any number of components at any dependence | **overstated** — the multiplicity is free; component validity is what must hold |
| A bare `psi < 0` test detects an inadequate expanded learner | Phase-0 materiality study | **refuted** — it suppresses the pairs the method exists to certify |

---

## 6. What is not yet established

* **No calibration exists for the unanimity rule.** No profile has been produced for it and
  none of the shipped profiles has been shown to transfer.
* **Achievable power is unknown.** Every probe figure is an upper bound; the achievable number
  is below it by an unmeasured margin.
* **The estimand is mean independence, not full independence.** Squared-loss VIMP at zero means
  the added variable does not shift the conditional mean; dependence carried purely in higher
  moments is invisible to it.
* **`delta`-approximate is not exact conditional independence**, which is what causal graph
  theory is built on. Bridging that gap is a theorem target, not an established result.
* **No causal claim is made or supported.** `causal_status` is hard-coded `not_yet_causal`, and
  specification section 20 places causal direction in separate assumption modules — Tier 1 hard
  background knowledge, Tier 2 assumption-conditional packages, Tier 3 display-only heuristics.
* **The product still ships the falsified policy.** `rank_separators` continues to rank by
  minimising the tested quantity; nothing in `src/` has been changed in response to any of the
  above.

---

## 7. Reproducing

Every study is a dispatchable workflow, and every evidence directory records the run id it came
from.

```bash
gh workflow run comparator-gate.yml --ref main
gh workflow run unanimity-power-probe.yml --ref main
gh workflow run empty-separator-pilot.yml --ref main
gh workflow run phase0-calibration.yml --ref main
```

The two oracle studies are standalone scripts inside their evidence directories, deliberately
outside `simulations/` because they test policies the package does not implement.
