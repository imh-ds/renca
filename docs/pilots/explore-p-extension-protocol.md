# Explore p-extension protocol — mapping the operating region up to 30 variables

**Status:** approved in principle. Stage 0 is approved for dispatch. **Stages 1 and 2 are
not**, and may not run until Stage 0's runtime and feasibility results have been reviewed.

## Purpose

The explore mode has been tested at 6 to 10 variables. Comprehensive psychological datasets
commonly carry 15 to 30. This maps how the mode behaves across that range.

**The purpose is not to show that 30 variables works at 100 people.** It very likely does
not. The purpose is to find out *which combinations* of sample size, network size, network
density and relationship shape produce a useful exploratory network — and to say plainly
where they stop.

A result of "above 20 variables you need 250 people" is a complete success. So is "above 20
variables nothing works", provided it is measured rather than assumed.

---

## 1. The ground-truth score, defined before anything runs

Every criterion below is stated in one quantity, and that quantity is computed from the
generating process rather than from any fitted model.

For an ordered pair `i <- j`, let `f_i` be the best predictor of variable `i` from **all**
other variables in the network and `f_i^-j` the best predictor from all others **except**
`j`. Then

    tau(i <- j) = [ E(Y_i - f_i^-j)^2 - E(Y_i - f_i)^2 ] / Var(Y_i)

the share of variable `i`'s total variance that adding `j` explains once every other
variable is already accounted for. The symmetric **relationship strength** is

    tau(i,j) = min( tau(i <- j), tau(j <- i) )

The minimum is used because explore retains a relationship only when both of its nodewise
models select it, so the harder direction governs detection.

**How it is computed.** The generating process is a Gaussian structure pushed through
strictly increasing per-variable transforms, so conditioning on a set of observed variables
is exactly conditioning on the corresponding latent ones, and each conditional distribution
is Gaussian with a known mean and variance. Each conditional expectation is therefore a
one-dimensional Gaussian integral of the transform, evaluated by Gauss-Hermite quadrature —
the same procedure used in
[`explore_gate.oracle_tau`](../../simulations/explore_gate.py). It is calculated, not
estimated by a model, so no criterion can be moved by the behaviour of anything under test.

**The classification, fixed now:**

| class | definition |
|---|---|
| **strong** | `tau(i,j) >= 0.10` |
| **weak** | `0 < tau(i,j) < 0.10` |
| **absent** | `tau(i,j) = 0`, by construction of the generating graph |

Identical to the completed 6-to-10-variable study, so the two sets of results read together.

**Two properties recorded in advance.** Graphs are redrawn if any relationship lands within
0.01 of the 0.10 boundary, so Monte Carlo error in the oracle cannot flip a classification.
And `tau` shrinks as networks get denser, because a relationship shares more of its
explanatory work with its neighbours — so the strong count is not perfectly comparable
across density conditions, and every condition reports the full distribution of `tau`
rather than only counts above the cut.

---

## 2. False connections, redefined

**Primary definition, and the one gated:**

> **false-connection share** = the proportion of *retained* relationships that correspond
> to genuinely absent ones.

Of the lines the method draws, what fraction are spurious. This is the quantity a
researcher reading a network actually faces.

**Uncertainty is reported two ways**, because the obvious interval is wrong on its own:

* an exact Clopper-Pearson 95% interval on the pooled count of retained relationships,
  which treats each drawn line as an independent trial;
* a percentile bootstrap 95% interval resampling *whole replications*, which respects the
  fact that lines within one network are not independent and is therefore the wider and more
  honest of the two.

Both are reported. Where they disagree materially, the bootstrap governs.

### This is a different quantity from the completed study's, and stricter

The completed study gated the share of *genuinely absent pairs* that received a line — a
false-positive rate, with absent pairs in the denominator. The new definition puts retained
edges in the denominator instead. They are not interchangeable.

Recomputed from the completed study's own data:

| variables | worst false-connection share achieved |
|---|---|
| 6 | 0.037 |
| 7 | 0.083 |
| 8 | 0.135 |
| 9 | 0.122 |
| 10 | 0.122 |

A 0.05 bar on the new definition would fail **17 of the 50 cells that already passed**,
including cells inside the current operating region. A 0.10 bar fails 3. A 0.15 bar fails
none.

**The proposed bar is 0.10**, deliberately not 0.15: 0.15 would be a bar nothing could fail,
which certifies nothing. 0.10 means at most one drawn line in ten is spurious, and three of
the completed study's cells miss it — so it discriminates. It is a product judgment and is
marked as such below.

**Consequence to note.** The completed 6-to-10-variable region was certified under the old
definition. To keep one consistent operating region from 6 to 30 variables, that region
should be re-derived under the new definition — which needs no re-running, since the
completed study already records the necessary quantity. Both definitions are reported here
so either reading is available.

---

## 3. Curved and straight relationships

The completed study made every variable in the nonlinear condition curved, so every
relationship there was curved and none could be compared against a straight one. That made
it impossible to ask where any advantage came from.

Here the nonlinear condition transforms **half** the variables and leaves the rest alone. A
relationship is **curved** if either of its variables is transformed and **straight** if
neither is. Both kinds exist inside the same network, which is both more like real data and
the only way to attribute an advantage.

---

## 4. Density

Set by **average number of connections per variable**, not by a percentage, because a
percentage means something different at 6 variables than at 30.

* **sparse** — 2 connections per variable on average
* **moderately dense** — 4 connections per variable on average

At 20 variables, moderately dense is about 40 relationships out of 190 possible pairs, which
is the range published psychological networks show. A fixed percentage would have produced
30-variable networks with 130 relationships, which nothing in the field looks like.

---

## 5. Matched comparisons

**Matched density.** Both methods tuned to draw the *same number* of relationships as the
true network contains; recovery compared there. The fairer everyday comparison — which
method spends a fixed budget of lines better.

**Matched false inclusion.** Both methods tuned so their false-connection share is as close
to the bar as possible without exceeding it; recovery compared there. Continuity with the
completed study.

Both use knowledge of the truth to locate the setting, and both methods get identical help,
so the comparison is fair even though no real analyst could perform it.

---

## 6. Stability

Two completely independent datasets from the *same* true network at the same sample size.
Run the method on each. Compare the sets of relationships drawn.

The measure is the share appearing in both out of those appearing in either, reported
separately for strong, weak, and absent pairs — the completed study found those three behave
completely differently and one combined number hides it. When both runs draw nothing the
comparison is undefined and is excluded rather than scored as perfect agreement.

---

## 7. Three method arms

| Arm | What it is | What it isolates |
|---|---|---|
| **explore** | curved terms, group penalty, stability selection | the full proposal |
| **explore-straight** | identical pipeline, straight-line terms only | **what the curves are worth** |
| **linear baseline** | EBIC-selected Gaussian graphical model | what the field uses today |

The middle arm is the important one. The completed study compared explore against the field
standard, and those differ in several ways at once — curved terms, but also a different
selection procedure and a different treatment of each variable. A gain could have come from
any of them. Running the identical pipeline with straight lines only separates the question
completely.

---

## 8. Stage 0 — scaling and feasibility

| variables | 15, 30 |
|---|---|
| people | 100, 500 |
| cells | 4 |
| replications | 10 per cell |
| density | moderately dense (the more expensive of the two) |
| shape | mixed-curved |

**Its purpose is to measure how cost scales, not how well anything performs.** Two variable
counts rather than one is what makes a scaling slope estimable: the cost of 30 variables
alone is a number, while 15 and 30 together say whether growth is quadratic, worse, or
better than the extrapolation assumes.

Reported: wall-clock time per replication broken down by arm, peak memory, and the implied
cost of Stages 1 and 2 recomputed from measurement rather than extrapolation.

**It can reject and cannot approve.** Ten replications establish no performance criterion
and none may be cited from it. It rejects if a replication is slow enough to make the staged
plan unaffordable, or if memory at 30 variables is impractical, or if the machinery fails on
a network three times larger than anything it has run.

---

## 9. Stage 1 and Stage 2 — not approved

| | Stage 1 | Stage 2 |
|---|---|---|
| variables | 12, 15 | 20, 25, 30 |
| people | 75, 100, 150, 250 | 100, 150, 250, 500 |
| density | sparse, moderately dense | sparse, moderately dense |
| shape | linear, mixed-curved | linear, mixed-curved |
| cells | 32 | 48 |
| replications | 500 per cell | 500 per cell, split across jobs |

---

## 10. What is measured in every condition

1. Recovery of strong relationships.
2. Recovery of **curved** relationships, against straight ones in the same networks.
3. **False-connection share**, with both uncertainty intervals; plus the completed study's
   false-positive rate as a diagnostic, and the average count of false lines per network
   **broken down by variable count and density**.
4. Stability across two independent samples, split three ways.
5. Blank-network rate, counted only on networks whose truth held at least two strong
   relationships.
6. Runtime and peak memory per network, per arm.
7. Explore against explore-straight, reported **separately for curved and straight
   relationships**.

Items 1 to 3 are reported at both matched density and matched false inclusion.

---

## 11. Pass/fail criteria

A condition is inside the operating region only if all seven pass.

| # | Criterion | Bar | Basis |
|---|---|---|---|
| 1 | False-connection share | ≤ 0.10 | **product judgment** |
| 2 | Recovery of strong relationships | ≥ 0.60 | **product judgment** |
| 3 | Blank networks, given ≥ 2 strong relationships in the truth | ≤ 0.10 | **product judgment** |
| 4 | Stability of strong relationships across samples | ≥ 0.80 | **evidence-anchored** |
| 5 | Beats the linear baseline on curved relationships, both matched settings | must exceed | **comparison, no threshold** |
| 6 | Beats **explore-straight** on curved relationships | must exceed | **comparison, no threshold** |
| 7 | Does not materially lose to explore-straight on straight relationships | within 0.05 | **product judgment** |

**Criteria 6 and 7 are now gated**, replacing the ungated finding in the previous draft.
Together they are the central claim: the curves must earn their place on the relationships
that are curved, without costing meaningfully on the ones that are not. If explore fails 6,
the added complexity is not paying for itself whatever else is true.

Reported and not gated: weak-relationship recovery and stability; the false-line count by
variable count and density; runtime; memory; performance on the fully linear condition.

**The `<= 1 false line per network` gate from the previous draft is removed.** A single
spurious line means something different in a 6-variable sparse graph than in a 30-variable
one, so it is reported by variable count and density rather than held to one number.

### Which criteria are actually grounded

**Criteria 5 and 6 are the strongest, because they contain no invented number.** "Must beat
the incumbent" and "must beat its own straight-line version" need no threshold — either they
hold or they do not. Conclusions resting on them are as solid as the simulation.

**Criterion 4 is anchored to measurement.** The completed study found strong-relationship
stability of 0.90 to 1.00 inside the region where everything else passed, and 0.37 to 0.60
outside it. A bar of 0.80 sits below what good conditions produced and above what failing
ones did — the one threshold set by looking at real numbers.

**Criteria 1, 2, 3 and 7 are product judgments and should be argued with rather than
deferred to.** Nothing establishes that a map missing 41% of strong relationships is useless
while one missing 39% is fine, or that losing 0.05 to the straight-line version is
acceptable and 0.06 is not. They are fixed in advance so results cannot be graded after the
fact, which is their only real purpose. If any is wrong it is wrong now, before any run.

---

## 12. Estimated compute cost

**Every figure here is extrapolated from 10-variable timings, and Stage 0 exists to replace
them with measurements.** Cost is expected to grow roughly with the square of the variable
count; the third arm adds roughly a third.

| Stage | Cells | Estimated core-hours | Wall clock on Actions |
|---|---|---|---|
| Stage 0 | 4 | under 1 | under 1 hour |
| Stage 1 | 32 | ~90 | ~4 hours |
| Stage 2 | 48 | ~470 | ~1 day |

**One constraint designed in rather than discovered.** At 30 variables and 500 people a
single cell at 500 replications is estimated near 17 hours, which exceeds the 6-hour limit
on a GitHub Actions job. Stage 2 cells must be split into four chunks of 125 replications,
giving 192 jobs rather than 48. Stage 0's measurement will say whether that split is
sufficient or needs to be finer.

For scale, the completed explore study was about 50 core-hours.

---

## 13. Limits fixed in advance

* Results describe simulated networks — a Gaussian structure under monotone transforms,
  additive effects only, no interactions generated or searched. Real data may not resemble
  them.
* Nothing here establishes that a relationship is **absent**. The study measures what gets
  found; a pair without a line is a pair not retained at this setting.
* Nothing here establishes causal direction, and no directional quantity is computed.
* Nothing here transfers to the resolve mode.
* The per-variable selection quota is set to the density the design uses. A real analyst
  does not know that, and sensitivity to setting it wrongly is a separate study that grows
  more important as networks get larger.
* The linear baseline is a comparison benchmark. Its performance authorizes nothing about
  shipping a linear mode.
