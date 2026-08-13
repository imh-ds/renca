# renca — post-mortem

**Status: dead.** Declared by the project owner on 2026-08-12. No further work is planned on
either mode. This document is the historical record and the negative-result write-up.

**Lifespan:** 2026-07-31 to 2026-08-12 — thirteen days, roughly twenty simulation studies,
about 200 CPU-hours of compute, 177 passing tests, and no version ever run on a real dataset.

Written so that someone who has never seen this repository can understand what was attempted,
what was measured, what failed, and why. Every number here is traceable to a directory under
[`docs/evidence/`](evidence/) and a GitHub Actions run id. Where a claim rests on an inference
rather than a measurement, that is said.

---

## 1. What renca was supposed to do

The ordinary way to build a psychological network is to measure how strongly variables move
together, draw a line where the association survives some filter, and leave it out where it
does not. A missing line is then ambiguous. It might mean *there is no relationship*, or it
might mean *we did not have enough data to see one*. Nothing in the output distinguishes
those two, and readers routinely treat the first reading as though it were established.

renca's premise was to close that gap. Rather than only asserting that a relationship exists,
it would assert — with a stated and validated error rate — that a relationship is **absent to
a stated resolution**. Concretely: *variable A adds less than δ to the prediction of variable
B, given everything else worth conditioning on, and the chance this statement is wrong is
below 5%.*

Two pieces of vocabulary carry the whole project:

**Θ (theta)** — how much one variable improves prediction of another once a conditioning set
is already accounted for, on a 0-to-1 scale of the outcome's variance. Θ = 0 means the
variable adds nothing.

**δ (delta)** — the resolution: how small Θ has to be before the relationship counts as
practically absent. Three were calibrated: 0.05, 0.10 and 0.20.

[ADR 0001](decision-records/0001-predictive-claim-boundary.md) fixed the scope from the start:
this was a **predictive** claim, not a causal one. `causal_status` was hard-coded
`not_yet_causal` for the life of the project and no causal claim was ever made. That
discipline held. It was not what killed the project.

Late in the project a second mode, **`renca explore`**, was invented: a sparse nonlinear map
of conditional associations for the small samples where the original mode could not operate.
It ran for four days.

---

## 2. The verdict

**Neither mode reached a state where it should be used.**

**The original mode (`resolve`)** works — in the sense that its statistical machinery is
sound and its error control holds — but only at a resolution and sample size that make the
output nearly vacuous for its intended field. At 100 participants the finest claim it can
support is roughly *"this variable explains less than 38% of that one's variance."* Almost
every real effect in behavioural research sits below that, so the statement is true and
useless. Reaching a resolution worth reporting needs about 300 participants at δ = 0.20, and
some conditions need closer to 750.

**The second mode (`explore`)** did not fail statistically — it recovers real structure
reliably and is essentially never blank — but it never established an advantage over the
existing methods it was meant to displace. Its one measured advantage turned out on
inspection not to come from the part that was novel.

**The two modes did not die of the same thing.** They operated in the same low-information
regime, and that regime is the backdrop to both, but the failures are distinct and §3 keeps
them apart. Collapsing them into a single story is tempting because it reads well; it is not
what was measured.

---

## 3. Why each mode died

### 3.1 `resolve` — three causes, one of which is a wall

resolve failed for three separable reasons. Only the third is about information.

1. **Claim semantics.** What was computed was a statement about one pair given one conditioning
   set. What was displayed was a missing line in a network graph, which asserts something much
   stronger. §6.1.
2. **Separator selection.** The rule chose the conditioning set that minimised the very
   quantity the test then evaluated, which is a search for the most flattering evidence. §5.2.
3. **Information and power.** Even after the first two are repaired, the resolution reachable
   at psychology sample sizes is too coarse to be worth reporting. Described below.

Causes 1 and 2 are design errors and are fixable in principle — cause 2 *was* fixed, though
never calibrated. Cause 3 is the one that does not yield to better engineering.

**The resolution floor.** Certification in this design requires

```
standard error  ≤  δ / |critical value|
```

Turn that around and it defines the **resolution floor** — `|critical value| × standard
error` — the finest δ that a pair whose true relationship is *exactly zero* could possibly be
certified at. If the floor is above the δ you want, no amount of correct data analysis gets
you there. The claim is unreachable regardless of what is true in the world.

Both multiplicands work against you, and they work against you from opposite directions:

- **Making the claim safe makes `|critical value|` large.** Every repair that fixed a real
  error made the test stricter. The critical value moved from the textbook −1.645 to −3.08
  at δ = 0.20, and to −4.75 at δ = 0.05.
- **Small samples make the standard error large.** This is unavoidable arithmetic.

Measured floors, from the [small-sample gate](evidence/phase1/small-sample-gate/README.md)
(36,000 fits, three learner libraries):

| library | n = 100 | n = 150 | n = 200 | n = 300 |
|---|---|---|---|---|
| v2 quadratic ridge | 0.479 | 0.284 | 0.240 | 0.144 |
| v3 nested blend | 0.395 | 0.242 | 0.231 | 0.158 |
| v4 cubic blend | 0.380 | 0.243 | 0.240 | 0.155 |

Read the first column as: *at 100 participants, the most precise statement this method can
make is that a relationship explains less than about 38% of the variance.* Psychology samples
are commonly 100–200. Every library clears δ = 0.20 at n = 300 and none clears it below.

**What this does and does not establish.** These floors are a property of *this* estimand,
*this* estimator's standard error and *this* rule's critical value. They are a strong
constraint on any procedure making a comparable inferential absence-certification claim — that
is a real and transferable result. They are **not** an information-theoretic impossibility
proof about network estimation in general. A different estimand, a different target, or a
procedure making a weaker or differently-shaped claim is not bounded by this table, and nothing
in this project tested one. Read §8, finding 1, with that qualification attached.

### 3.2 `explore` — a different failure

explore was not starved of information in the way resolve was. It recovered strong
relationships at 0.826–0.999, produced a blank network essentially never, and reproduced its
strong findings perfectly. On its own terms it worked.

It died of two things, neither of which is the resolution floor:

1. **The novel component added nothing once isolated.** The whole case for explore was that
   modelling curved relationships would beat methods that assume straight ones. A control arm
   running the identical pipeline with straight lines only beat the curved version on **curved**
   data in 15 of 16 conditions, and beat it by 0.086–0.175 on straight data. The earlier
   +0.110 advantage over the incumbent was real and came from the surrounding machinery —
   stability selection, node-wise regression, the AND rule — not from the part that was new.
   This is a variance argument, not an identifiability one: five knots and a cubic degree is
   too much flexibility to pay for at 75–250 rows.
2. **The comparison against the incumbent reversed depending on the matching convention.** The
   pipeline wins 16 of 16 when both methods are held to the same false-connection rate and
   loses when both are held to the same number of lines drawn. Neither convention is wrong;
   they answer different questions. But a single-convention result would have supported a
   confident claim in either direction, and the honest summary is that the pipeline is
   competitive rather than decisive.

Separately, the share of drawn lines that were spurious exceeded its bar in 20 of 32 cells,
**including 7 of the 16 fully linear ones**, and grew with network size and density. That is a
third failure and it is not about curves at all.

### 3.3 What the two share, and what they don't

**Shared:** both operated at 75–375 rows, where variance dominates and every additional
parameter has to earn its keep. That regime is why resolve's standard errors were large and why
explore's flexible basis did not pay for itself.

**Not shared:** resolve's two design failures — drawing a narrow claim wide, and selecting the
conditioning set that flatters the conclusion — have no counterpart in explore. explore's
failure to differentiate its novel component has no counterpart in resolve. It is fair to say
the two modes were attempted in a regime that punishes ambition, and unfair to say they failed
the same way.

One thing does generalise from the pair, and it is worth stating carefully: the incumbent
methods look simple, and at these sample sizes simplicity was competitive in both studies that
compared against them. That is an observation about the comparisons actually run, not a proof
that nothing more sophisticated can ever win.

---

## 4. Chronology

| dates | what happened |
|---|---|
| Jul 31 – Aug 2 | Package skeleton, project schema, audit, stratified splitting, CLI. |
| Aug 2 – Aug 5 | Estimator built. Cross-fitted VIMP, learner library, calibration registry, first validated profile at δ = 0.05. |
| Aug 5 – Aug 7 | Three defects found and fixed in the confirmatory path (§5.1). Cubic member added. Profiles shipped at three resolutions. |
| Aug 6 | Fit-index threshold study — 30,000 replications. Predictive adequacy found to be a yield indicator inversely related to safety. |
| **Aug 8** | **Comparator gate: `REDESIGN`. 0 of 12 operating regions passed.** The separator-selection policy is diagnosed as structurally unsound. This is the pivot point of the project. |
| Aug 9 – Aug 10 | Repair attempts. Top-k agreement insufficient; unanimity over the whole candidate pool is the only rule that controls error. Power probe: only δ = 0.20 survives. |
| Aug 10 | Empty-separator pilot and small-sample gate. The sample-size wall is measured. δ = 0.20 unreachable below n = 300 under any library. |
| **Aug 10 – Aug 11** | **Pivot.** Two-mode design proposed: `explore` for small samples, `resolve` for large. Feasibility protocols written with fixed pass/fail criteria before implementation. |
| Aug 11 – Aug 12 | Explore gate at 6–10 variables. 43 of 50 cells eligible, +0.110 over the incumbent on nonlinear data. Looked like a success. |
| Aug 12 | p-extension Stage 0 (cost) and **Stage 1 (performance): 9 of 32 cells eligible, all in the linear control arm.** The +0.110 is reinterpreted — it came from the pipeline, not the curves. |
| **Aug 12** | **Project declared dead.** |

---

## 5. Complete catalogue of what was tried and what happened

### 5.1 The estimator and its calibration

Four defects were found in the confirmatory path and fixed. All four are recorded because each
was a real error whose repair had a measurable cost, and because the pattern across them
matters more than any one of them (§6.3).

| # | defect | consequence | repair | cost of the repair |
|---|---|---|---|---|
| 1 | Separator ranking scored candidate sets by expanded-model risk rather than incremental importance | Preferentially selected **colliders** — exactly the variables that should not be conditioned on | Replaced with cross-fitted bidirectional gain | None directly; **this repair was itself falsified six days later**, by the comparator gate on 8 August (§5.2) |
| 2 | The nested-learner safeguard abstained on any negative estimate | Discarded the *strongest* evidence for a nonedge — the pairs the method exists to certify | Materiality-plus-consistency rule | Pruning power rose 2.18% → 10.14%, so the repair helped |
| 3 | Calibration had been passing only because of defect 2 | Once the safeguard was fixed, Phase 0 failed outright | Critical quantile set deliberately below alpha (0.04) | A stricter test, so lower power |
| 4 | The learner library could not represent a cubic **at all** | False pruning breached the 5% level, reaching 9.7% | Added a fourth library member rather than substituting | +19% on the standard error; ~10% of pruning power |

Defect 4 deserves expansion because it produced the project's cleanest general finding.

The library's polynomial member used Hermite basis functions, in which the cubic term
`He₃(x) = (x³ − 3x)/√6` is *orthogonal by construction* to both `x` and `x²`. A degree-2
library therefore recovered **−4%** of a genuine cubic relationship — not a little, not
imprecisely, but nothing at all, with the sign wrong.

From [`learner-library-shapes`](evidence/phase1/learner-library-shapes/README.md), recovery of
a true relationship by shape:

| shape | turning points | share expressible in {x, x²} | recovered |
|---|---|---|---|
| linear | 0 | 100% | 98% |
| exponential decay | 0 | 87% | 57% |
| parabola | 1 | 100% | 73% |
| **cubic** | **2** | **0%** | **−4%** |
| sin(1x) | 2 | 85% | 83% |
| sin(2x) | 4 | 15% | 21% |
| sin(4x) | 8 | 0% | 2% |

**Recovery tracks representability, not wiggliness.** A cubic and `sin(1x)` both have two
turning points; the sine is ~85% linear across the data range while the cubic is orthogonal to
everything the library had. Turning points predict nothing.

Two sub-findings from the same study:

- **Flexible non-parametric methods are not a substitute at this sample size.** 200 trees at
  depth 15 recovered **−8%** of a cubic — *worse* than ten shallow trees — at eleven times the
  compute. Forests approximate curves with flat steps and need many splits in sparse regions;
  with 240 training rows those data points do not exist.
- **Substituting was the error, not the cubic.** Replacing the degree-2 member with degree-3
  fixed the cubic (−4% → 47%) and broke the parabola (77% → 53%), because a fixed penalty
  spread over nine correlated features shrinks the squared term harder. Adding a member fixed
  the cubic at no parabola cost.

### 5.2 The comparator gate — the single largest failure

[`evidence/phase1/comparator-gate`](evidence/phase1/comparator-gate/README.md) · run
[31282474806](https://github.com/imh-ds/renca/actions/runs/31282474806) · 400 replications,
p = 15, n = 375, against PC, conservative PC, FCI, GES and EBICglasso each swept over its
tuning parameters, every method seeing identical rows.

**Verdict: `REDESIGN`. 0 of 12 operating regions passed, identically under both scoring
conventions.**

The governing pattern, which no amount of tuning moved:

> **Every region that prunes usefully fails error control, and every region that controls
> error prunes almost nothing.**

| δ | correct pruning | wrongful pruning | familywise error |
|---|---|---|---|
| 0.05 | 0.005 – 0.058 | ≤ 0.002 | 0.00 – 0.03 |
| 0.10 | 0.091 – 0.237 | ≤ 0.025 | 0.00 – 0.34 |
| 0.20 | 0.657 – 0.900 | 0.015 – 0.157 | 0.13 – 0.91 |

**Where it won, and it was not small.** On nonlinear relationships at δ = 0.20, renca deleted
real edges 4.9% of the time against PC 26.7%, FCI 28.1%, GES 27.9%, EBICglasso 23.5% — every
baseline destroying roughly three real edges in ten, because a cubic relationship carries zero
partial correlation and a covariance-based test is blind to it. Five to seven times lower
error at two-thirds of the pruning. This is why the verdict was `REDESIGN` and not `STOP`, and
in hindsight that decision extended the project by four days.

**Where it lost.** On plain linear data at δ = 0.20 — the condition most favourable to
everyone — renca deleted 15.7% of real edges where GES managed 1.0% *at higher pruning*. Worst
of six methods on the easiest condition.

#### The diagnosis, and why it could not be fixed by tuning

The specification ranked candidate conditioning sets by **minimising** the very quantity the
subsequent test evaluated. For a pair that is genuinely connected, that is not a search for
the right conditioning set. It is an active search for the conditioning set under which the
pair *looks* most separated.

Two oracle diagnostics settled it using population values, so nothing below is sampling noise:

**The certificates were true statements.** Of 708 genuinely connected pairs, 626 exceeded
Θ = 0.20 given their true parents, but only 226 did given the separator the method actually
chose. **The selection step drove 400 real relationships under the threshold in the
population** — they stay under it with infinite data. The certificates were not miscalibrated
and not noisy. They were narrow true statements being *rendered* as missing lines in a graph.

**It was not confined to weak relationships.** Share of real edges pushed below 0.20, bucketed
by their true strength:

| true strength given true parents | n | mean strength given chosen set | share pushed under 0.20 |
|---|---|---|---|
| ≤ 0.20 | 45 | 0.087 | 0.889 |
| 0.20 – 0.30 | 53 | 0.094 | 0.906 |
| 0.30 – 0.40 | 65 | 0.128 | 0.800 |
| 0.40 – 0.60 | 86 | 0.171 | 0.709 |
| > 0.60 | 107 | 0.237 | **0.421** |

Relationships explaining 71% of predictable variance were suppressed to a mean of 0.24 and
pushed under threshold in 42% of cases. The direction is diagnostic: a *poor* conditioning set
would leave a **larger** apparent association, because it retains indirect paths. Systematically
smaller values are the signature of selection, not of misspecification.

This falsified a clause the specification had asserted verbatim — that direct connections
retain importance above threshold *for every admissible conditioning set*. They do not.

**What this ruled out immediately:** recalibration, a finer δ, a different critical quantile
and a larger selection split all leave a population-level fact untouched. Only structural
changes remained.

### 5.3 Repairing the selection policy

Three studies, in order.

**Top-k agreement is insufficient.**
[`policy3-agreement-diagnostic`](evidence/phase1/policy3-agreement-diagnostic/README.md).
Requiring the top 5 ranked conditioning sets to agree cut wrongful pruning of strong real
pairs from 0.460 to 0.022 — a large improvement — but familywise error remained **0.73**. Not
close to usable.

The mechanism is worth recording: a genuinely absent pair is separated by many candidate sets
(mean 12.1 of 14); a wrongly suppressed real pair usually by exactly one (mean 1.9). Agreement
keys directly on that asymmetry, which is why it is not merely a stricter threshold.

**Only unanimity works, and that is a structural result.**
[`separator-agreement-feasibility`](evidence/phase1/separator-agreement-feasibility/README.md).
Sweeping k from 1 to 14 found exactly one value meeting a 0.05 familywise bar: **k = 14, the
entire candidate pool.** Because 14 was the pool size rather than a tuned constant, the finding
is not a parameter choice:

> The claim requires **universal** quantification over the candidate pool, not existential.
> "There exists a conditioning set under which the pair is separated" fails. "For all
> conditioning sets" passes.

The approach to the bar is a cliff, not a slope: between k = 13 and k = 14 familywise error
falls from 0.22–0.32 to 0.00–0.01 while correct pruning gives up only 0.02–0.15. **Every rule
short of unanimity still lets a pair select the evidence that flatters it.**

Two consequences: the entire separator-ranking step became unnecessary rather than repaired
(with no selection there is no ranking), and the claim became monotone *increasing* in pool
size, so a larger candidate pool turns conservative instead of adversarial.

A deflationary reading was ruled out. Unanimity includes the empty conditioning set, so it
might have been a plain marginal-association screen doing all the work. It is not: dropping
the empty set and requiring only the 13 singletons changes nothing to three decimal places,
and the marginal screen alone deletes 1.6–6.1% of real pairs against 0.0–0.1% for unanimity.

**Small networks make it quiet, not unsafe.**
[`small-network-feasibility`](evidence/phase1/small-network-feasibility/README.md), 5,600
graphs at p = 4 to 10. Correct pruning declines steadily as the network shrinks in **all twelve
conditions** — twelve conditions, twelve declines, nothing improves at small p. But wrongful
pruning of strong real pairs is 0.000 in 83 of 84 cells. Small networks do not break the rule;
they make it stop saying anything.

The binding constraint is that conditioning sets were limited to one variable. In a dense
small network two variables are typically joined by several routes at once, so no single
variable severs them all, and the pair falls into "unresolved."

### 5.4 The sample-size wall

**Only one resolution survives a real sample.**
[`unanimity-power-probe`](evidence/phase1/unanimity-power-probe/README.md), n = 375. Upper
bounds on correct pruning, averaged across network sizes and data-generating families:

| δ | upper bound on useful output |
|---|---|
| 0.05 | **0.018** — dead |
| 0.10 | 0.208 |
| 0.20 | **0.422** — the only survivor |

Error control held throughout (wrongful pruning ≤ 0.010, familywise ≤ 0.029), but **61% to 87%
of all pairs came back "no evidence either way"** in every cell. Even in the single viable
region, roughly two pairs in three are unresolved. And network size barely mattered once real
data was involved — the finite-sample rates are flat across p = 4, 5, 6 where the population
ceilings had risen steadily. **Sample size, not network size, is the binding constraint.**

Every figure in that table is an **upper bound**, not an estimate. Both decision rules probed
certify *more* than a properly calibrated rule would. The achievable number is below the lower
of them by an unmeasured margin. An earlier description of the two rules as bracketing the
truth from opposite sides was wrong and was corrected in the record.

**Some conditions cannot reach δ = 0.20 at n = 300 even in principle.**
[`empty-separator-pilot`](evidence/phase1/empty-separator-pilot/README.md), 1,500 paired
replications. Two cells showed a resolution floor **above** the δ being calibrated — 0.278 and
0.204 against δ = 0.20. Clearing that needs roughly double the inference rows: about 600, so
around 750 participants total.

This pilot also refuted its own motivating concern. The empty conditioning set, which
unanimity requires every pair to clear and which had never been calibrated, turned out to be
**level with a single conditioning set where both are learnable and markedly safer where they
are not.** The hazard was somewhere else.

**No learner library rescues small samples.**
[`small-sample-gate`](evidence/phase1/small-sample-gate/README.md), 36,000 fits. The floors in
§3. This was the last untried lever that could have moved the sample-size boundary rather than
accepted it.

It also refuted a plausible hypothesis in the opposite direction from the prediction. The
small-sample failure is downward *bias*, not noise, and the proposed explanation was model
selection on too little data — predicting that a **smaller library should be less biased.**
The result runs the other way: at n = 100 the *largest* library has the *smallest* floor
(0.380 for the four-member library against 0.479 for the two-member one). The mechanism
survives while the prescription dies — selection noise does drive the bias, and **blending
several members is what mitigates it**, while picking one is a higher-variance decision.
The direction of any fix is more averaging, not less.

**The fallback number was quietly unsafe.** When no calibration profile matches the run — which
was *every* run at psychology sample sizes — the reported per-pair upper limit fell back to a
textbook normal approximation. Derived from the small-sample gate's own replication data, that
limit sat below the true value in about **27% of replications at n = 150**, against the 5% its
stated level promises, and the failure is in the dangerous direction: the number exists to
argue a relationship is small, so a too-narrow margin makes the tool over-eager to declare
absence. A dedicated study to see whether the multiplier could be calibrated at 100–200 rows
was built (branch `test/resolution-coverage`, workflow `resolution-coverage.yml`) and
deliberately **never dispatched** — by then the underlying question had been overtaken.

### 5.5 The `explore` pivot

**The gate that looked like success.**
[`explore-gate`](evidence/phase2/explore-gate/README.md) · run
[31549419998](https://github.com/imh-ds/renca/actions/runs/31549419998) · 25,000 networks at
6–10 variables, scored against an exact oracle and against an EBIC-selected Gaussian graphical
model as incumbent.

43 of 50 cells eligible. Recovery of strong relationships beat the incumbent by **+0.110 on
nonlinear data in 25 of 25 cells** at matched false inclusion, and tied on linear data. Safety
held everywhere — worst false-inclusion rate 0.0268 against a 0.05 bar. The usable floor came
out near 75 participants, *lower* than the protocol had predicted.

Two things in that study were not gated criteria and mattered more than the criteria did:

**Reproducibility was poor, then partially rescued.**
[`reproducibility-rerun`](evidence/phase2/explore-gate/reproducibility-rerun/README.md). Two
independent datasets drawn from the *same* true network agreed on under half their edges at
n = 100 on nonlinear data — in cells passing every gated criterion. Decomposing it:

| n | strong edges | weak edges | spurious edges | all edges |
|---|---|---|---|---|
| 100 | **0.900** | 0.150 | 0.000 | 0.461 |
| 150 | **0.933** | 0.300 | 0.000 | 0.534 |

Strong relationships reproduce at 0.90–1.00; weak ones reach 0.41 at best. The headline figure
averages a trustworthy component with a near-random one. **Spurious edges agree at 0.000
everywhere** — when a false connection appears it essentially never appears twice, which rules
out systematic bias and is the good outcome. An earlier claim that "essentially all"
disagreement lives in weak edges was **overstated**: weak edges carry 61–78% of it and strong
edges still contribute 13–25%.

**The +0.110 was misattributed.** Nothing in that study could separate a gain caused by the
nonlinear curves from a gain caused by the surrounding machinery — stability selection,
node-wise regression, the AND rule. A third study arm was added specifically to find out.

**Stage 1 — the decisive negative result.**
[`p-extension-stage1`](evidence/phase2/p-extension-stage1/README.md) · run
[31623644723](https://github.com/imh-ds/renca/actions/runs/31623644723) · 16,000 networks at
12 and 15 variables, three arms: `explore` (curved), `explore-straight` (identical pipeline,
straight lines only), and the field-standard incumbent.

**9 of 32 cells eligible — and all nine are in the fully linear control arm. Not a single cell
containing curved relationships qualified.**

| criterion | result |
|---|---|
| Beat the straight-line version on **curved** data | **fails 15 of 16** |
| Hold level with the straight-line version on **straight** data (tolerance 0.05) | **fails 16 of 16**, by 0.086 to 0.175 |
| Beat the incumbent at **both** matched settings | **fails 16 of 16** |
| Spurious share of drawn lines ≤ 0.10 | fails 20 of 32, including 7 of 16 *linear* cells; worst 0.179 |
| Recovery of strong relationships ≥ 0.60 | **passes everywhere**, 0.826 – 0.999 |
| Blank network when the truth was findable ≤ 0.10 | **passes everywhere**, 0.000 – 0.006 |
| Reproducibility of strong relationships ≥ 0.80 | **passes everywhere — 1.000 in all 32 cells** |

So the smooth terms lose modestly where curvature exists and heavily where it does not. Across
this grid they are **strictly harmful**.

**This reinterpreted the earlier study.** The +0.110 was real and it was not the curves. It was
the pipeline. Which is exactly what the third arm was built to detect, and it detected it.

**Requiring two comparisons is what exposed the rest.** The incumbent comparison reverses
depending on how the two methods are matched:

| comparison | pipeline vs incumbent, curved data | straight data |
|---|---|---|
| matched false-connection rate | wins 16/16, +0.069 | wins 16/16, +0.103 |
| matched number of lines drawn | wins 4/16, −0.017 | wins 1/16, −0.023 |

Either comparison alone would have told a clean and misleading story. An earlier claim in this
project that "both renca arms beat the field standard" was true at matched false-inclusion and
**false at matched density**, and was corrected.

### 5.6 Defects in the studies themselves

Recorded because a negative result is only worth as much as the instrument that produced it,
and several of these would have corrupted the conclusions had they not been caught.

| defect | how it would have misled | how it was caught |
|---|---|---|
| The fit-index pilot (1,200 replications) reported **no** relationship between predictive adequacy and false pruning | The full 30,000-replication run found a strong monotone relationship *in the opposite direction to safety*. The pilot reading is wrong and is marked superseded | Scale |
| Explore's per-node selection quota and the simulated graph's degree cap derived from two different fractions, so at 7, 8 and 9 variables full recovery was **structurally impossible** | Would have made a whole region look like an estimator limitation | The only two variable counts where the constants happened to agree were the two best performers |
| The matched-comparison routine returned the *first* admissible operating point rather than the best | Flattered renca and gave the incumbent 0.000 recovery on linear data; would have made two criteria meaningless | Inspection of an implausible zero |
| Positive-definiteness enforced by diagonal dominance welded network density to relationship strength — doubling the connection count halved every relationship | Stage 0 could not draw a valid dense graph at all and failed outright. The **first** attempted fix made it worse (0 of 12 admissible), which is what revealed the real constraint | Job failure |
| `tracemalloc` inflated Stage 0 timings roughly 3× (54s vs 17s per replication) and tracks only the Python allocator, missing numpy entirely | Would have corrupted the single measurement Stage 0 existed to take | Implausible magnitude |
| The cost projection scaled by sample size | Predicted 9s per replication against 44.3s measured — a 5× under-estimate that made the remaining stages look like 20 and 119 core-hours instead of 58 and 228 | Comparison against Stage 0's own measurements |
| A rerun was described as bit-identical | 24 of 25,000 replications (0.096%) differ by ~0.002 from floating-point variation across runner hardware. Inputs reproduce exactly; fitted outputs to about two decimals | Direct comparison |

The last one is a fair characterisation of the project's reproducibility overall: **seeding by
identity works** — every generated dataset reproduces exactly across runs, worker counts and
grid changes — and fitted numbers reproduce to about two decimal places.

---

## 6. Where ambition derailed it

### 6.0 The central mistake

Everything in this section is an instance of one thing:

> **The project optimised for continuing to solve the current specification, rather than
> repeatedly asking whether the specification still deserved to exist.**

The vocabulary was never the problem. These documents say *gate*, *stop*, *falsify* and
*redesign* throughout, and they mean it — the criteria were fixed in advance and they were
scored honestly. But **in execution those words consistently resolved to "do not build the next
planned subsystem yet." They did not once resolve to "halt, report what just happened, and
require a fresh decision about whether this should continue."**

The record makes this checkable:

| the gate | what it found | what happened next |
|---|---|---|
| Comparator gate, 8 Aug | 0 of 12 regions passing; the selection policy structurally unsound in the *population* | Repair studies began the same day. Of the three structural options it listed, option 3 — *narrow the claim and stop drawing a graph* — was written down and never surfaced as a decision to be taken |
| Separator-agreement, 9 Aug | Only unanimity over the entire pool controls error; the ranking step is now unnecessary rather than repaired | Proceed to measure unanimity's power |
| Power probe, 10 Aug | Two resolutions dead; the third leaves 61–87% of pairs unresolved | Proceed to the sample-size question |
| Small-sample gate, 10 Aug | δ = 0.20 unreachable below n = 300 under any library — the last available lever | **Invent a second mode** |
| p-extension Stage 1, 12 Aug | 9 of 32 cells, all in the control arm | Halt |

Four decisive negative results in five days, and each one produced *the next study* rather than
*a decision point*. Only the last one — where the failure was total and admitted no repair —
stopped anything.

**Why this matters more for AI-directed research than for the human kind.** An agent that is
good at executing a well-specified next step will keep generating well-specified next steps
indefinitely, and each one will be locally defensible. Competence at continuation is not
judgment about whether to continue, and the two are easy to confuse from inside the loop
because continuation *looks* like progress and produces artifacts on schedule.

The rigour made this worse rather than better. Sloppy continuation announces itself. Rigorous
continuation — pre-registered criteria, control arms, disclosed amendments, honest scoring —
is *more* persuasive at each step, and supplies a steady stream of evidence that the work is
being done properly. It was being done properly. That was never the question. The question was
whether it should have been done at all, and the apparatus that answered every other question
was structurally incapable of raising that one.

**Where the decision function actually lived.** Worth recording precisely, because it is the
strongest evidence for the thesis. Every genuinely decisive test in this project was demanded
from outside the execution loop:

* The **`explore-straight` control arm** — the thing that killed explore — was an owner
  requirement. It had been drafted as an interesting-but-ungated finding.
* **Both matched comparisons** were an owner requirement. Either alone would have supported a
  confident and misleading conclusion.
* The **halt on the calibration-coverage study** was an owner instruction, against an in-flight
  plan to keep going.
* The **decision to close the project** was an owner decision, not a gate outcome.

The gates measured well. They never terminated anything. The terminating function was external
to the loop for the entire life of the project, and no one noticed, because the loop kept
producing good work.

### The five instances

Five decisions, in the order they were made. Each was locally defensible, and each is a case of
§6.0. Together they are the reason the project ran for thirteen days rather than four.

### 6.1 Drawing a narrow claim as a wide one

**The largest single design error, as distinct from the process failure in §6.0.**

The estimator only ever supported a statement about *one pair, given one stated conditioning
set*. That statement was correct. It was then **rendered as a missing line in a network
graph**, which is a claim about the pair given everything — a much stronger assertion that
nothing in the machinery established.

The comparator gate proved this precisely: the certificates were **true** and the drawing was
**wrong**. 400 of 708 real relationships were suppressed in the population, not by noise, not
by miscalibration, but by the gap between what was computed and what was displayed.

A graph is an extremely strong visual assertion, and it is very easy to render a modest
quantity into one.

**A note on how to characterise the technical work**, because an earlier draft of this document
said it was "consistently sound" and that is not defensible against the rest of the document.
This project produced four genuine estimator and calibration defects (§5.1), a fallback
interval that was unsafe in the dangerous direction on every run at its target sample sizes
(§5.4), at least six defects in the simulation studies themselves (§5.6), a central repair that
was never calibrated, and a shipped implementation that still runs the falsified policy (§7).

The fairer statement is that **the project eventually developed a strong empirical
falsification apparatus despite repeated technical and design defects.** The apparatus is the
achievement — pre-registered criteria, control arms designed to attribute gains, adversarial
external comparison, disclosed amendments, seeding by identity. It is what caught the defects,
including most of its own. It should not be described in a way that implies the thing it was
auditing was clean.

### 6.2 Searching for the evidence that supports the conclusion

The specification ranked conditioning sets by minimising the exact quantity the test then
evaluated. Stated plainly, the method tried every way of looking at a pair and kept the one
where the pair looked most separated — then tested whether the pair was separated.

Nobody set out to do this. It arose from two locally sensible choices — "pick the best
conditioning set" and "test incremental importance" — that were unsound in combination. It
survived because it was never stated in one sentence until the gate forced it.

**The test that caught it was the one comparing against existing methods.** Every internal
check had passed. It took an adversarial comparison with an outside standard to expose it.

### 6.3 Every repair widened the machinery; none narrowed the claim

Look at §5.1 as a sequence rather than four independent items:

| repair | effect on the machinery | effect on the claim |
|---|---|---|
| Cubic library member | +1 member, +19% standard error | unchanged |
| Materiality safeguard | more conditions to evaluate | unchanged |
| Sub-alpha quantile | stricter critical value | unchanged |
| Unanimity | from 2 tests per pair to 2(p−1) | unchanged |

Four repairs, four costs to precision, and the promise the tool made to its user never moved.
The correct response after the second or third of these was to **narrow the claim** — to stop
drawing a graph and report incremental predictive value given a stated conditioning set, which
is what the machinery actually supported and what the comparator gate explicitly listed as an
option. That option was recorded and never taken, because it "concedes the output is not a
network."

Conceding that in early August would have ended the project four days earlier with a smaller,
honest tool instead of no tool.

### 6.4 `REDESIGN` instead of `STOP`

The comparator gate returned 0 of 12 passing regions. It was recorded as `REDESIGN` rather
than `STOP` on the strength of one genuinely impressive result: on nonlinear relationships,
renca's error rate was five to seven times lower than every established method.

That result was real and remains real. But it justified continuing with a design whose
selection step had just been proven structurally unsound in the population — and the resulting
repair (unanimity) was still uncalibrated when the project ended.

The honest reading of that gate was available on the day: *the one thing this does better is
handle nonlinear relationships that partial-correlation methods cannot see; everything else
about the design is broken.* That reading points at a narrow tool for a specific problem. It
was instead read as "the design works, the policy needs repair."

### 6.5 Inventing a second product instead of accepting a small first one

By 10 August the measurements were unambiguous: the original mode needed ~300 participants at
its coarsest resolution and ~750 in some conditions, and 61–87% of pairs would come back
unresolved. That is a narrow product. It is not *nothing* — nobody else certifies absence at
all — but it is much smaller than the ambition.

Rather than build that narrow thing, a **second mode was invented** to cover the sample sizes
the first could not reach. It was designed, protocol'd, implemented and killed inside four
days.

The pivot was executed unusually well. Protocols with fixed pass/fail criteria were written
*before* implementation; a control arm was added specifically to attribute any gain; two
independent matched comparisons were required; the incumbent was given the same oracle
assistance. That rigour is precisely why the mode died quickly and cleanly instead of shipping.

But the underlying move — *the honest version of this is too small, so build a bigger one* —
is the same move as §6.4 and §6.3, and it is the one that consumed the last third of the
project. The `explore` mode existed for four days and never had an independent reason to
exist beyond covering for the first mode's limitations.

---

## 7. What was never tested

Stated plainly so that no one reads this document as more conclusive than it is.

- **No real data. Ever.** Every study in the evidence chain is synthetic. The most realistic
  end-to-end check in the repository is a three-node smoke test. Whatever this project
  established, it established about simulated data.
- **The unanimity rule was never calibrated.** It is the repair for the project's central
  failure, and **no calibration profile was ever produced for it.** None of the four shipped
  profiles was shown to transfer, and under unanimity the decision is the maximum of 2(p−1)
  dependent tests against the maximum of 2 the profiles were validated for. Every number
  reported for unanimity is an upper bound, not an achievable rate.
- **The package still ships the falsified policy.** `rank_separators` in
  [`src/renca/screening/separators.py`](../src/renca/screening/separators.py) continues to rank
  by minimising the tested quantity. **Nothing in `src/` was ever changed in response to any
  finding in this document.** Any run of the shipped package invokes the rule the comparator
  gate falsified.
- **n ≈ 600–750 was never run.** The empty-separator pilot identified it as the concrete target
  for reaching δ = 0.20 in the hard conditions. No study was run there.
- **Conditioning sets larger than one variable were never tested.** This is the binding
  constraint on usefulness at small network sizes. It costs 27× the compute at 15 variables and
  was never attempted. Whether it reduces or worsens the suppression problem is unknown — a
  wider candidate pool is also a wider search.
- **`explore`'s smooth basis was tested at one configuration only** — five knots, cubic degree.
  It may simply be too flexible for 75–250 rows. A leaner basis was costed at ~30 core-hours
  and never run. The result is a failure of *that* configuration, not a proof that no smooth
  basis can work.
- **`explore-straight` was never tested at 6–10 variables**, so its advantage at 12–15 does
  not transfer backwards without measurement.
- **20 to 30 variables were never measured** (Stage 2, costed at 228 core-hours).
- **The estimand is mean independence, not full independence.** Dependence carried purely in
  higher moments was invisible to the whole method by construction.
- **Approximate independence is not exact conditional independence**, which is what causal
  graph theory is built on. Bridging that was always a theorem target and was never attempted.
- **Which conditioning sets suppress, and why, is still unknown.** The leading hypothesis —
  that the suppressing variable is a redundant correlate of an endpoint — was tested and
  **refuted**: 86.6% of suppressed cases against 85.2% of non-suppressed, no difference at all.

---

## 8. What is worth keeping

Not a consolation list. These are results that were measured properly and that someone else
could use.

**Findings with value outside this project:**

1. **Inferential absence-certification is out of reach at behavioural-research sample sizes.**
   Measured resolution floors: ~0.38 at n = 100, ~0.24 at n = 200, ~0.15 at n = 300, stable
   across three learner libraries. **Scope, stated precisely:** this constrains procedures that
   certify approximate conditional independence with calibrated error control on a
   variance-explained scale — a real and transferable bound on that class. It does **not**
   establish that network estimation in general is information-limited at these sample sizes,
   and no study here tested a different estimand. The claim is about a family of procedures,
   not about the data in the abstract.
2. **Nonlinear flexibility does not pay for itself at 12–15 variables and 75–250 rows.** The
   identical pipeline with straight lines beats it on curved data in 15 of 16 conditions and by
   0.086–0.175 on straight data. Measured with a control arm designed to attribute the
   difference. The field keeps proposing nonlinear network methods; this is a properly
   controlled measurement of what one costs.
3. **Predictive adequacy is a yield indicator inversely related to safety.** Better
   conditioning buys precision, and precision applied to a biased estimate produces a
   confidently wrong answer. Both correct pruning (0.398 → 0.771) and wrongful pruning
   (0.0018 → 0.0466) rise monotonically with it across 30,000 replications. Treating a
   goodness-of-fit index as a trust mark inverts its meaning.
4. **Recovery tracks representability, not wiggliness** — with the full shape table in §5.1,
   and the corollary that flexible non-parametric methods are not a substitute for the right
   parametric form at n ≈ 300.
5. **Selecting the most favourable conditioning set is structurally unsound**, with a
   population-level quantification of what it costs (400 of 708 real relationships suppressed)
   and the finding that only unanimity over the entire candidate pool controls error — a cliff
   between k = 13 and k = 14, not a slope.
6. **In this pipeline, spurious connections are irreproducible noise rather than systematic
   bias** (agreement 0.000 across independent datasets in every cell), while strong connections
   reproduce at 0.90–1.00. That decomposition is the argument for showing edge stability rather
   than a single line style, and it applies to any network method.

**Reusable methodology:**

- **An exact non-linear oracle.** A Gaussian graphical model pushed through *strictly monotone*
  per-node transforms preserves conditional independence exactly — verified at 0.0 on
  non-edges. Monotonicity is load-bearing: a non-monotone transform discards the latent sign
  and can manufacture dependence that is not in the skeleton.
- **Seeding by identity, not execution order**, so worker counts and grid additions never
  change results. This worked and is the reason several defects above were provable rather than
  suspected.
- **Protocols with pass/fail criteria fixed before the run.** Every amendment to a
  pre-registered constant was disclosed and the affected pilot re-run from scratch rather than
  patched.
- **Fair-baseline notes.** EBICglasso needs an unpenalised
  refit to be scored fairly, conservative PC has the same skeleton as PC so it is one baseline
  not two, `graphical_lasso` returns no exact zeros so naive edge counting overcounts,
  and composed nonlinear transforms break Fisher-z on non-normality rather than nonlinearity.
  Each of these is a way to accidentally beat a baseline that is not actually being beaten.

**The evidence chain itself.** [`docs/evidence/README.md`](evidence/README.md) indexes every
study in the order it was run, with what each established *and what it ruled out*, including a
table of six hypotheses this project raised and then refuted — four of them its own. It was
written so a methods and results section could be built from it without re-reading the
directories, and it still can be.

---

## 9. If anyone restarts this

Not a recommendation to restart. If someone does, these are the things this project paid for
and they should not pay for again:

1. **Decide what the output is before building the estimator.** If the answer is a network
   graph, then every quantity computed must support a statement about a pair given *everything
   else*, not given a chosen subset. That constraint should be enforced from the first commit.
2. **Never let the selection step optimise the quantity the test evaluates.** State the
   selection rule and the test statistic in one sentence. If that sentence contains the same
   quantity twice, the design is unsound.
3. **Compute the resolution floor first.** `|critical value| × standard error` at the target
   sample size, before writing an estimator. If it exceeds the δ the field cares about, stop.
   That single calculation would have ended this project in its first week.
4. **Compare against real incumbents early, on their home turf, at more than one matched
   operating point.** Every internal check here passed. The external comparison broke it, and
   the two matched comparisons disagreed with each other.
5. **Always include a control arm that isolates the novel component.** The +0.110 that
   sustained a four-day pivot was produced by the surrounding machinery, and only an arm
   designed to attribute it could show that.
6. **When a repair costs precision and leaves the claim unchanged, narrow the claim instead.**
7. **Give every gate explicit termination semantics, written before it runs.** A gate that only
   answers "may the next subsystem be built?" cannot end a project, however honestly it is
   scored. Each gate should state in advance what result would mean *the specification no
   longer deserves to exist*, and a failing gate should return control to the owner rather than
   flow into the next study. This is the lesson with the widest application beyond this
   repository, and it is the one this project paid the most for. See §6.0.

---

## 10. Repository state at close

| | |
|---|---|
| Default branch | `main` |
| Tests | 177 passing |
| Open pull requests | none — [#30](https://github.com/imh-ds/renca/pull/30) closed unmerged, 2026-08-12 |
| Shipped calibration profiles | 4, all `validated`, all bound to 300 inference rows — **all for the falsified policy** |
| Simulation studies run | ~20, all recorded under `docs/evidence/` with run ids |
| Studies built but never dispatched | `resolution-coverage` (branch `test/resolution-coverage`) |
| Protocols written but never run | [`resolve-feasibility-protocol.md`](pilots/resolve-feasibility-protocol.md); Stage 2 of [`explore-p-extension-protocol.md`](pilots/explore-p-extension-protocol.md) |
| Designs scoped but never implemented | [`pre-analysis-audit-scope.md`](design/pre-analysis-audit-scope.md) |
| Parked unmerged | `feat/unlearnable-scenario-family` — a deliberately adversarial calibration family. `sin(4x)` would push the critical value to about −17, requiring ~7,000 participants to certify anything |
| Real datasets analysed | **none** |

Every workflow remains dispatchable and every evidence directory records the run id it came
from, so any number in this document can be reproduced.

---

*Recorded 2026-08-12, on the decision to end the project.*
