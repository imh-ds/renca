# p-extension Stage 1 — the curves do not pay for themselves

GitHub Actions run
[31623644723](https://github.com/imh-ds/renca/actions/runs/31623644723), 2026-08-12, all 33
jobs successful. 12 and 15 variables x four sample sizes x sparse and moderate density x
linear and mixed shapes: 32 cells, 500 replications each, 16,000 networks.

Executes Stage 1 of
[the p-extension protocol](../../../pilots/explore-p-extension-protocol.md), every threshold
fixed beforehand.

**Verdict: 9 of 32 cells eligible, and every one of them is in the fully linear control arm.
No cell containing curved relationships qualifies. The smooth terms lose to straight lines
on the relationships they exist to capture.**

## The headline

Criterion 6 asked whether explore beats **its own straight-line version** on curved
relationships. That arm exists because the completed 6-to-10-variable study compared explore
only against the field standard, and those two differ in several ways at once, so a gain
could have come from the curves or from the machinery around them.

It came from the machinery.

Recovery of curved relationships at matched false inclusion:

| density | variables | people | explore | explore-straight | field standard |
|---|---|---|---|---|---|
| sparse | 12 | 250 | 0.421 | **0.477** | 0.381 |
| sparse | 15 | 250 | 0.362 | **0.452** | 0.344 |
| moderate | 12 | 250 | 0.400 | 0.393 | 0.273 |
| moderate | 15 | 250 | 0.356 | **0.361** | 0.234 |

`explore-straight` wins in 15 of 16 cells. Both renca arms beat the field standard, and the
straight one beats it by more.

**This reinterprets the completed study.** Its `+0.110` advantage over the field standard
was real, and it was not the curves — it was stability selection, nodewise regression and
the AND rule. Nothing in that study could have separated the two, which is exactly why the
third arm was added.

## The curves are not neutral; they cost

Criterion 7 asked whether explore *holds* against its straight version on relationships that
are genuinely straight, within a tolerance of 0.05. It fails in **all 16** cells, by 0.086
to 0.175 — two to three times the tolerance.

| density | variables | people | explore | explore-straight | loss |
|---|---|---|---|---|---|
| sparse | 15 | 250 | 0.445 | 0.620 | **0.175** |
| sparse | 12 | 75 | 0.285 | 0.436 | **0.151** |
| moderate | 12 | 250 | 0.445 | 0.531 | 0.086 |

So the smooth terms lose modestly where curvature exists and heavily where it does not.
Across this grid they are strictly harmful.

## The matched-density comparison reverses the matched-false-inclusion one

Criterion 5 required beating the field standard at **both** matched settings. It fails in all
16 mixed cells, and the reason is instructive:

| density | variables | people | matched false inclusion | matched density |
|---|---|---|---|---|
| | | | explore / standard | explore / standard |
| moderate | 15 | 75 | 0.179 / 0.152 | 0.396 / **0.542** |
| moderate | 15 | 250 | 0.356 / 0.234 | 0.541 / **0.650** |
| sparse | 12 | 250 | 0.421 / 0.381 | 0.566 / **0.658** |

Explore wins when both methods are held to the same **false-connection rate** and loses when
both are held to the same **number of drawn lines**. Requiring both comparisons is what
exposed this; either alone would have told a clean and misleading story.

## What did work, everywhere

All 32 cells passed criteria 2, 3 and 4, with room to spare:

| Metric | Bar | Range across all 32 cells |
|---|---|---|
| Recovery of strong relationships | ≥ 0.60 | 0.826 – 0.999 |
| Blank networks given a findable truth | ≤ 0.10 | 0.000 – 0.006 |
| Stability of strong relationships | ≥ 0.80 | **1.000 everywhere** |

Strong relationships are found almost always, networks are essentially never blank, and two
independent samples agree on the strong relationships **perfectly** in every cell. The
pipeline is sound. The basis is what fails.

## The other failure, and it is not about curves

Criterion 1 — the share of *drawn* relationships that are spurious, bar 0.10 — fails in 20
of 32 cells, **including 7 of the 16 fully linear cells**. It is worst where networks are
larger and denser:

| condition | false-connection share |
|---|---|
| sparse, 15 variables, best cell | 0.067 |
| moderate, 12 variables, worst cell | **0.179** |

Bootstrap intervals are narrow — typically ±0.01 — so these are not borderline calls.

This continues a trend rather than starting one. The completed study's worst value under
this definition was 0.135 at 8 to 10 variables; at 12 to 15 with moderate density it reaches
0.179. **The share of drawn lines that are spurious grows with network size and density**,
and 0.10 is not reachable at moderate density in this range under any arm.

## What this does not establish

* **It is one basis configuration.** Five knots and a cubic degree may simply be too
  flexible for 75 to 250 rows; a leaner smooth basis might pay for itself where this one
  does not. The protocol fixed this configuration in advance and the result is a failure of
  *it*, not a proof that no smooth basis can work.
* **`explore-straight` has never been tested at 6 to 10 variables.** The completed study had
  no such arm. Its advantage here does not transfer backwards without measurement.
* Nothing here authorizes shipping a linear mode. `explore-straight` is a study arm built to
  attribute a difference, and it has no evidence of its own beyond this grid.
* Nothing here establishes absence, causal direction, or anything about `renca resolve`.
* Stage 1 covers 12 and 15 variables. Stage 2's 20 to 30 remain unmeasured.

## Reproduce

```bash
gh workflow run explore-p-extension.yml --ref main -f replications=500 -f stage=1
```
