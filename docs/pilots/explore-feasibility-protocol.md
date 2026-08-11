# Explore feasibility protocol

**Status:** awaiting approval. No implementation may begin, and no claim that the
explore mode is viable may be made, until this protocol is approved and executed.

**Question:** does a sparse nonlinear conditional-association map recover real
structure at psychology-scale sample sizes without inventing structure, and over
what region of sample size and variable count? The answer defines the operating
region for `renca explore`. It is not assumed to be non-empty: a finding that no
cell at or below `n = 150` qualifies is a valid and reportable outcome, and would
mean the nonlinear exploratory mode does not exist at this scale.

**Explicit non-promise.** Nothing here presumes `n = 50` or `n = 75` is workable.
Those cells are included to *locate* the lower boundary, not to demonstrate one.
Prior arithmetic suggests they will fail: a nodewise additive model at `p = 8`
carries seven smooth terms, and at four basis functions each that is twenty-eight
parameters, which stability selection then asks to be fit on subsamples of about
twenty-five rows. The study exists to measure that rather than argue it.

**A linear fallback is a separate decision.** If the nonlinear mode proves
ineligible at some cell, this protocol does not authorize silently substituting
linear terms there. It reports ineligibility. Whether a linear mode should exist,
and under what name and what separate evidence, is a distinct decision taken
later.

---

## Design

**Grid.** `n` in {50, 75, 100, 125, 150} x `p` in {6, 7, 8, 9, 10} x two network
truths (linear, additive nonlinear) = 50 cells. Replications per cell are fixed at
500 before the run.

**Truth.** Each replication draws a known undirected network with a degree cap,
subject to rejection sampling that guarantees at least two genuine edges and at
least two genuine nonedges, so that no cell can score trivially. At `p = 6` the
degree cap permits near-complete graphs, and the earlier small-network study hit
exactly that degeneracy; the guard is carried over deliberately.

Edge strengths are drawn across a range and each edge is labelled **strong** or
**weak** by a threshold fixed before the run. Recovery is scored separately for
the two classes, because weak-edge recovery at `n = 100` is expected to be poor
and gating on it would confuse a design limit with a defect.

The nonlinear truth uses **additive smooth effects only**. No interaction terms
and no interaction hunting. An `n = 50` study has no business searching an
interaction space, and the earlier calibration work established that the
interaction family is the binding constraint everywhere it appears.

**Estimator.** Nodewise strongly regularized additive models, one per variable,
each using every other variable. Group penalty over whole smooth terms.
Stability selection over subsamples. Undirected edge retained under the **AND
rule**: both nodewise models must select it.

**Pre-analysis decisions.** The following are fixed before any run and may not be
adjusted afterwards. Adjusting any of them makes the result fitted rather than
measured, and requires a fresh protocol.

* basis dimension per smooth term;
* penalty selection procedure;
* stability-selection subsample count, subsample fraction, and retention
  threshold `pi`;
* the strong/weak edge threshold;
* replications per cell;
* the seed derivation, which must depend on cell identity and replication index
  rather than execution order, so re-running reproduces the numbers themselves
  and not merely their distribution.

---

## Metrics and fixed pass/fail criteria

A cell is **eligible** only if all five criteria pass. The set of eligible cells is
the operating region, and it is the artifact the pre-analysis audit consults.

| # | Metric | Pass criterion |
|---|---|---|
| 1 | Expected falsely included edges per network | `<= 1.0` |
| 2 | Recovery of strong edges | `>= 0.60` |
| 3 | Probability the network has zero retained edges | `<= 0.10` |
| 4 | Median Jaccard agreement between two independent datasets from one truth | `>= 0.50` |
| 5 | Runtime per network, single core | `<= 300s` |

**1 — false inclusion is the safety criterion.** Stability selection's guarantee is
on the *expected number* of falsely selected edges, not on a familywise rate, so
the bar is stated that way. The realized value must also not exceed the method's
own nominal bound at the chosen `pi`; a realized value above nominal means the
guarantee does not hold in this regime and the cell fails regardless of the
absolute number. `P(at least one false edge)` is reported alongside but is
descriptive, not gating.

**2 — recovery is the usefulness criterion.** A map that finds fewer than three
in five strong relationships is not a map. Overall recovery across both edge
classes is reported and not gated.

**3 — the empty-network rate is the specific failure this study exists to find.**
Three conservative filters act in the same direction here: the group penalty
shrinks weak curves out, stability selection keeps only what survives most
resamples, and the AND rule requires both nodewise models to agree. Each is
individually correct and they compound. If more than one study in ten receives a
blank graph, the tool is unusable at that cell whatever its other properties.

**4 — stability across datasets, not across resamples.** Selection frequency
within one dataset is high for retained edges by construction and therefore says
nothing. The question is whether two researchers with the same true network and
the same sample size would draw the same picture. This is the softest of the five
criteria and its threshold is the least defensible; it is stated in advance
anyway, so it cannot be chosen after seeing the numbers.

**5 — runtime.** A researcher-facing default has to run interactively. The bar
applies at the largest cell.

---

## Reporting

Report per cell, in one table and one plot by `n` with `p` as a series:

* all five metrics with their pass/fail marks;
* overall recovery and weak-edge recovery separately;
* `P(at least one false edge)`;
* the retention-path summary: at what pruning strictness each true edge enters,
  which distinguishes an edge that survives strict pruning from one appearing only
  at the loosest setting.

**Conservatism must be visible, not assumed.** Safety bought by drawing nothing is
not safety. Report criterion 1 and criterion 3 together in every cell, and treat
any cell that passes on false inclusion while failing on the empty-network rate as
a failure of the tool, not a success of its caution.

**Lead the result with the operating region** — the set of eligible cells stated
plainly — and only then with the mechanism. State whether performance degrades
smoothly as `n` falls or collapses at a boundary, because a cliff and a slope
imply different guidance.

---

## Limits this study does not exceed

* It establishes nothing about causal direction or edge orientation, and no
  directional quantity is computed. Per-model selection frequencies exist inside
  the estimator and are not reported as an edge-level output.
* It establishes nothing about `renca resolve`. The two modes condition on
  different sets and measure different quantities; neither calibrates the other.
* Absent edges are **not retained at this setting**. The study measures recovery,
  not absence, and no output of it may be read as evidence that a relationship is
  absent.
* One estimator configuration throughout. A failure here is a failure of this
  configuration, not a proof that no sparse additive method can work.
