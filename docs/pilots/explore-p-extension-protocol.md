# Explore p-extension protocol — mapping the operating region up to 30 variables

**Status:** awaiting approval. Nothing is implemented and nothing is dispatched.

## Purpose

The explore mode has been tested at 6 to 10 variables. Comprehensive psychological datasets
commonly carry 15 to 30. This maps how the mode behaves across that range.

**The purpose is not to show that 30 variables works at 100 people.** It very likely does
not. The purpose is to find out *which combinations* of sample size, network size, network
density and relationship shape produce a useful exploratory network — and to say plainly
where they stop.

A result that says "above 20 variables you need 250 people" is a complete success of this
study. So is "above 20 variables nothing works", provided it is measured rather than
assumed.

---

## Definitions, fixed before anything runs

### Strong relationship

For a pair of variables, take the share of one variable's variance that adding the other
explains, once every other variable in the network is already accounted for. Compute it in
both directions and keep the smaller. Call it the pair's **strength**.

A relationship is **strong** when its strength is 0.10 or above, which is the same cut the
previous study used, kept identical so the two sets of results can be read together.

One caution recorded in advance: this number naturally shrinks as networks get denser,
because a relationship shares more of its explanatory work with its neighbours. So strength
is not perfectly comparable across the density conditions, and the study reports the full
distribution of strengths in every condition rather than only the counts above the cut.

### Curved and straight relationships

The previous study made every variable in the nonlinear condition curved, which meant every
relationship in that condition was curved and none could be compared against a straight one.
That made it impossible to ask where the advantage came from.

Here, the nonlinear condition transforms **half** the variables and leaves the rest alone. A
relationship is:

* **curved** if either of its two variables is transformed;
* **straight** if neither is.

Both kinds then exist inside the same network, which is both more like real data and the
only way to answer whether explore's advantage is specifically about curvature.

### Sparse and moderately dense

Density is set by **average number of connections per variable**, not by a percentage,
because a percentage means something very different at 6 variables than at 30.

* **sparse** — on average 2 connections per variable;
* **moderately dense** — on average 4 connections per variable.

At 20 variables, moderately dense means about 40 relationships out of 190 possible pairs.
That is in the range published psychological networks actually show. A fixed percentage
would have produced 30-variable networks with 130 relationships, which nothing in the field
looks like.

### Matched density

Both methods are tuned so they draw the **same number of relationships** as the true network
contains, and their recovery is compared at that setting. This is the fairer everyday
comparison: it asks which method spends a fixed budget of lines better.

### Matched false inclusion

Both methods are tuned so they draw false relationships at the same rate — as close to 5%
of the truly-unconnected pairs as possible without exceeding it — and recovery is compared
there. This is the previous study's comparison, kept for continuity.

Both comparisons use knowledge of the truth to find the setting. Both methods get exactly
the same help, so the comparison is fair even though no real analyst could do it.

### Stability

Draw two completely independent datasets from the *same* true network, at the same sample
size. Run the method on each. Compare the two sets of relationships it drew.

The measure is the share of relationships appearing in both, out of those appearing in
either. Reported separately for strong relationships, weak relationships, and pairs with no
true relationship — because the previous study found those three behave completely
differently and a single combined number hides it. When both runs draw nothing, the
comparison is undefined and excluded rather than counted as perfect agreement.

---

## Three methods, not two

| Arm | What it is | What it isolates |
|---|---|---|
| **explore** | curved terms, group penalty, stability selection | the full proposal |
| **explore-straight** | identical pipeline, straight-line terms only | **what the curves are actually worth** |
| **linear baseline** | EBIC-selected Gaussian graphical model | what the field uses today |

The middle arm is new and it matters. The previous study compared explore against the field
standard, and those two differ in several ways at once — curved terms, but also a different
selection procedure and a different way of handling each variable. A gain could have come
from any of them.

Running the identical pipeline with straight lines only separates the question. If explore
beats explore-straight, the curves earned their place. If it does not, the advantage came
from the machinery around them and the added complexity is not paying for itself.

This is the direct answer to whether nonlinear terms justify themselves, and it is a
question the previous study could not answer.

---

## Stage 0 — the cheap rejection test

**Before either stage, a runtime probe.** 30 variables at 500 people, and 30 variables at
100 people, ten replications each, one job, everything else identical.

Its only jobs are to measure how long a replication takes and how much memory it uses at
the largest cell, and to confirm the machinery survives a network three times larger than
anything it has run on.

**It can reject and cannot approve.** If a single 30-variable replication takes several
minutes, the full plan is unaffordable as written and needs a faster implementation before
any of it is worth paying for. Everything in the cost section below is an extrapolation
from 10-variable timings, and Stage 0 replaces those guesses with measurements.

Estimated cost: **under an hour.**

---

## Stage 1

| | |
|---|---|
| variables | 12, 15 |
| people | 75, 100, 150, 250 |
| density | sparse, moderately dense |
| shape | linear, mixed-curved |
| cells | 32 |
| replications | 500 per cell |

## Stage 2

| | |
|---|---|
| variables | 20, 25, 30 |
| people | 100, 150, 250, 500 |
| density | sparse, moderately dense |
| shape | linear, mixed-curved |
| cells | 48 |
| replications | 500 per cell, split across jobs |

Stage 2 runs only if Stage 1 is worth continuing from.

---

## What is measured in every condition

1. **Recovery of strong relationships** — the share found.
2. **Recovery of curved relationships** specifically, against straight ones in the same
   networks.
3. **False inclusion** — the share of truly-unconnected pairs that get a line, and the
   average number of false lines per network.
4. **Stability** across two independent samples, split three ways as defined above.
5. **Blank-network rate** — how often the method draws nothing, counted only on networks
   that genuinely contained at least two strong relationships.
6. **Runtime and peak memory** per network.
7. **Whether the curves pay for themselves** — explore against explore-straight, at both
   matched settings, reported separately for curved and straight relationships.

Everything in 1 through 3 is reported at both matched density and matched false inclusion.

---

## Pass/fail criteria

A condition is **inside the operating region** only if all six pass.

| # | Criterion | Bar | Basis |
|---|---|---|---|
| 1 | False inclusion among unconnected pairs | ≤ 0.05 | **convention** |
| 2 | Average false lines per network | ≤ 1.0 | **product judgment** |
| 3 | Recovery of strong relationships | ≥ 0.60 | **product judgment** |
| 4 | Blank networks, given ≥ 2 strong relationships in the truth | ≤ 0.10 | **product judgment** |
| 5 | Stability of strong relationships across samples | ≥ 0.80 | **evidence-anchored** |
| 6 | Beats the linear baseline on curved relationships, at both matched settings | must exceed | **evidence-free comparison** |

Reported and **not** gated: recovery of weak relationships; stability of weak relationships;
the explore versus explore-straight comparison; runtime; memory; performance on the linear
condition.

### Which of these are actually grounded

**Criterion 6 is the strongest, because it contains no invented number.** "Must beat the
incumbent" needs no threshold — either it does or it does not. Every conclusion resting on
it is as solid as the simulation itself.

**Criterion 5 is grounded in measurement.** The previous study found strong-relationship
stability of 0.90 to 1.00 inside the region where everything else passed, and 0.37 to 0.60
outside it. A bar of 0.80 sits below what good conditions actually produced and above what
failing ones did. This is the one threshold set by looking at real numbers rather than by
picking a round figure.

**Criterion 1 is convention.** 5% is borrowed from the conventional significance level. It
is defensible by custom, not by anything measured here.

**Criteria 2, 3 and 4 are product judgments and should be argued with rather than
deferred to.** Nothing establishes that a map missing 41% of strong relationships is
useless while one missing 39% is fine, or that one false line per network is acceptable and
1.1 is not. They are stated in advance so results cannot be graded after the fact, which is
their real purpose. If any of them is wrong, it is wrong now and can be changed now, before
any run.

**Deliberately not gated: the explore versus explore-straight comparison.** It is the most
interesting question in the study and gating on it would be premature — if the curves turn
out not to pay for themselves, that is a finding about the design worth reporting in full,
not a reason to mark conditions as failures.

---

## Estimated compute cost

**These are extrapolations from 10-variable timings and Stage 0 exists to replace them.**
Cost grows roughly with the square of the variable count, so a 30-variable network is on the
order of nine times a 10-variable one, and the three method arms add roughly a third on top.

| Stage | Cells | Estimated core-hours | Wall clock on Actions |
|---|---|---|---|
| Stage 0 | 2 | under 1 | under 1 hour |
| Stage 1 | 32 | ~90 | ~4 hours |
| Stage 2 | 48 | ~470 | ~1 day |

**One practical constraint.** At 30 variables and 500 people, a single cell at 500
replications is estimated at around 17 hours, which exceeds the 6-hour limit on a GitHub
Actions job. Stage 2 cells must therefore be split into four chunks of 125 replications
each, giving 192 jobs rather than 48. This is bookkeeping, not extra compute, but it has to
be built in from the start rather than discovered when the first job is killed.

For comparison, the completed explore study was about 50 core-hours. Stage 1 is roughly
twice that. Stage 2 is roughly ten times it.

---

## Limits fixed in advance

* Results describe simulated networks — a Gaussian structure pushed through monotone
  transforms, with additive effects only and no interactions generated or searched. Real
  data may not resemble them.
* Nothing here establishes that a relationship is **absent**. The study measures what gets
  found; a pair with no line is a pair not retained at this setting.
* Nothing here establishes causal direction, and no directional quantity is computed.
* Nothing here transfers to the resolve mode.
* The per-variable selection quota is set to the density the design uses. A real analyst
  does not know that. Sensitivity to setting it wrongly is a separate study and grows more
  important as networks get larger.
* The linear baseline is a comparison benchmark. Its performance authorizes nothing about
  shipping a linear mode.
