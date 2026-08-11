# Explore feasibility protocol

**Status:** approved for execution, pilot stage first. Implementation of the
`renca explore` mode itself remains unauthorized; this protocol builds simulation
code under `simulations/` only and touches nothing in `src/`.

**Question:** does a sparse nonlinear conditional-association map recover real
structure at psychology-scale sample sizes without inventing structure, and does
it beat a linear baseline where it claims to? The answer defines the operating
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
later. The linear baseline defined below is an *incumbent comparator*, not a
fallback, and passing as a comparator does not authorize shipping it.

---

## 1. The score scale, defined before anything else

Every criterion below is stated in one scale, and that scale is the population
quantity the explore estimator targets. No informal labels are used.

For an ordered pair `i <- j`, let `f_i` be the best predictor of `Y_i` from *all*
other variables and `f_i^-j` the best predictor from all others *except* `j`. Then

    tau(i <- j) = [ E(Y_i - f_i^-j)^2 - E(Y_i - f_i)^2 ] / Var(Y_i)

the share of `Y_i`'s total variance that adding `j` explains once every other
variable is already accounted for. The symmetric **edge strength** is

    tau(i,j) = min( tau(i <- j), tau(j <- i) )

The minimum is used because explore retains an edge only under the AND rule, so
the harder direction is what governs detection. Both directional values are
computed for the truth and neither is reported as an edge-level output.

**Strong edge:** `tau(i,j) >= 0.10`. **Weak edge:** `0 < tau(i,j) < 0.10`.
**Nonedge:** `tau(i,j) = 0` by construction of the generating graph.

`tau` is computed as an oracle from the generating process by common-random-number
Monte Carlo at 200,000 rows, in the same manner as
[`oracle_theta`](../../src/renca/calibration/scenarios.py). It is a property of
the truth, never of a fitted model, so no criterion below can be moved by the
estimator's behaviour.

**This is deliberately the same functional form as resolve's `Theta`, on a
different conditioning set** — everything else, rather than a separator. The two
modes therefore report numbers that look alike and are not comparable. That must
be stated wherever both appear.

---

## 2. Design

**Grid.** `n` in {50, 75, 100, 125, 150} x `p` in {6, 7, 8, 9, 10} x two network
truths (linear, additive nonlinear) = 50 cells.

**Truth.** Each replication draws a known undirected network with a degree cap,
subject to rejection sampling guaranteeing **at least two strong edges**, at least
one weak edge, and at least two genuine nonedges. The strong-edge guarantee is
what makes criterion 3 well posed; without it a blank network could be correct.
At `p = 6` the degree cap permits near-complete graphs, and the earlier
small-network study hit exactly that degeneracy, so the guard is carried over.

The nonlinear truth uses **additive smooth effects only** — no interaction terms
and no interaction hunting. An `n = 50` study has no business searching an
interaction space, and the calibration work established that the interaction
family is the binding constraint wherever it appears.

The linear and nonlinear truths are matched on `tau`: the same edge strengths are
induced through different shapes, so the two arms differ in functional form and
not in signal strength. Without that matching, any difference between arms would
confound shape with effect size.

**Estimator under test.** Nodewise strongly regularized additive models, one per
variable, each using every other variable. Group penalty over whole smooth terms.
Stability selection over subsamples. Undirected edge retained under the AND rule.

**Incumbent comparator.** A linear Gaussian graphical model with EBIC selection —
the current default in psychological network analysis. Run on identical data, and
tuned as described in criterion 4.

**Pre-analysis decisions**, fixed before any run and not adjustable afterwards.
Changing any of them makes the result fitted rather than measured and requires a
fresh protocol.

* basis dimension per smooth term;
* penalty selection procedure;
* stability-selection subsample count, subsample fraction, and retention
  threshold `pi`;
* the `tau >= 0.10` strong-edge boundary;
* replications per cell;
* the seed derivation, which must depend on cell identity and replication index
  rather than execution order, so re-running reproduces the numbers themselves
  and not merely their distribution.

---

## 3. Gated criteria

A cell is **eligible** only if all five pass. The set of eligible cells is the
operating region, and it is the artifact the pre-analysis audit will consult.

| # | Metric | Pass criterion |
|---|---|---|
| 1a | False inclusion among genuine nonedges | `<= 0.05` |
| 1b | Expected falsely included edges per network | `<= 1.0` |
| 2 | Recovery of strong edges (`tau >= 0.10`) | `>= 0.60` |
| 3 | P(no retained edges given the truth has `>= 2` strong edges) | `<= 0.10` |
| 4 | Strong-edge recovery against the linear baseline at matched false inclusion, nonlinear truths | must exceed |
| 5 | Runtime per network, single core | `<= 300s` |

**1 — false inclusion, gated two ways, and neither is optional.** Explore must not
pass by retaining real edges and avoiding blank graphs while quietly drawing
spurious ones. `1a` is the rate among pairs whose true `tau` is exactly zero, and
it is scale-aware. `1b` is the absolute expected count, which is the quantity
stability selection actually bounds; the realized value must also not exceed the
method's own nominal bound at the chosen `pi`, and a realized value above nominal
fails the cell regardless of the absolute number, because it means the guarantee
does not hold in this regime. Precision — the share of drawn edges that are real —
is reported as a diagnostic.

**2 — recovery, on the scale defined in section 1.** Recovery is additionally
reported as a curve across `tau` bins, which locates the detection boundary in
effect-size terms rather than only at the gate. Weak-edge recovery is reported and
not gated; poor weak-edge recovery at `n = 100` is a design limit, not a defect.

**3 — the blank-network rate, conditioned on the truth.** A blank graph is only a
failure when there was something to find, so the criterion is evaluated on the
subset of replications whose true graph contains at least two strong edges. The
unconditional blank rate is reported alongside as a diagnostic. This is the
criterion the study most exists to check: the group penalty, stability selection
and the AND rule are three conservative filters acting in the same direction, they
compound, and safety bought by drawing nothing is not safety.

**4 — the incumbent comparison, which answers "why use this at all".** Recovery
can always be bought by drawing more edges, so the comparison is made **at matched
false inclusion**: each method's tuning is swept to the operating point where its
false-inclusion rate among genuine nonedges is as close as possible to 0.05 from
below, and strong-edge recovery is read there. On **nonlinear** truths explore's
recovery must exceed the baseline's. If it does not, there is no reason for a
researcher to prefer it, and the cell fails however well it performs in isolation.
On **linear** truths the comparison is reported and not gated — explore is expected
to give something up for its flexibility, and the size of that loss is a number
worth having rather than a failure.

**5 — runtime.** A researcher-facing default must run interactively. The bar
applies at the largest cell.

---

## 4. Diagnostics, reported and not gated

**Reproducibility across datasets.** Metric: the Jaccard index. Objects compared:
the retained edge sets from two independent datasets drawn from the *same* true
network at the same `n` and `p`. Sparse handling: when exactly one set is empty
the index is 0; when **both** are empty the pair is undefined and is excluded from
the distribution and counted separately, because scoring two blank graphs as
perfect agreement would reward the failure criterion 3 exists to catch. Selection
frequency *within* a dataset is not used — it is high for retained edges by
construction and therefore says nothing.

This was previously proposed as a gate at 0.50. **It is a diagnostic here**,
because no principled basis for 0.50 exists; the distribution is reported in full
so a threshold can be argued from evidence later rather than asserted now.

Also reported, none gated: precision; recovery by `tau` bin; unconditional blank
rate; weak-edge recovery; the linear-truth comparison against the baseline; and
the retention path, showing at what pruning strictness each true edge enters,
which distinguishes an edge surviving strict pruning from one appearing only at
the loosest setting.

---

## 5. Staging, and what each stage may conclude

**Pilot.** A reduced-replication run over a subset of cells, sized to complete in
approximately three hours of wall clock. Its purposes are to measure per-cell
runtime so the full grid can be sized honestly, to confirm the machinery end to
end, and to detect a catastrophic design — a blank-network rate near one, a
false-inclusion rate far above nominal, or a runtime that makes the full grid
unaffordable.

**The pilot may reject. It may not approve.** Replication counts at pilot scale
cannot support a 0.05-style performance claim, and no criterion above may be
declared passed on pilot evidence. A pilot that looks good means only that the
full run is worth paying for.

**Full run.** 500 replications per cell, fixed before the run. Only full-run
evidence may establish eligibility, and only the full run may be cited as
establishing that a cell is in the operating region.

---

## 6. Limits this study does not exceed

* It establishes nothing about causal direction or edge orientation, and no
  directional quantity is reported. Per-model selection frequencies exist inside
  the estimator and are not exposed as an edge-level output; the edge-level
  summary is symmetric.
* It establishes nothing about `renca resolve`. The two modes condition on
  different sets, and although `tau` and `Theta` share a functional form their
  values are not comparable and neither calibrates the other.
* Absent edges are **not retained at this setting**. The study measures recovery,
  not absence, and no output of it may be read as evidence that a relationship is
  absent.
* One estimator configuration throughout. A failure here is a failure of this
  configuration, not a proof that no sparse additive method can work.
* The linear comparator is an incumbent benchmark. Its performance here does not
  authorize shipping it as a mode.
