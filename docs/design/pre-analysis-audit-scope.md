# Pre-analysis audit — scope

**Status:** scope awaiting approval. No implementation is authorized. Three decisions at
the end are the user's and block the build.

**What it is.** A step that runs *before* any analysis and answers one question: which mode,
if any, is this dataset inside the measured evidence for? It reads the operating regions
produced by the feasibility studies and reports a verdict, a reason, and the evidence the
verdict rests on.

**What it is not.** It is not a data-quality check. That already exists as
[`audit_project`](../../src/renca/audit/__init__.py), which validates columns, types,
variance floors, scale bounds, boundary mass, missing-data policy, cluster counts and a
minimum row count. Those are questions about whether the data are *analysable*. This is a
question about whether the data are *in evidence* for a particular claim. The two compose:
`audit_project` must pass first, and a dataset can be perfectly clean and still be outside
every mode's region.

---

## Inputs

Only quantities available before results exist:

* complete-case row count, taken from `audit_project`'s `analysis_row_count` rather than
  recomputed, so the two cannot disagree;
* variable count `p`;
* the requested `delta`, the fold count, and the learner configuration;
* the calibration registry;
* the recorded operating regions.

Nothing derived from an estimate, a p-value or a fitted graph is admissible. If the audit
could see results it would stop being a pre-analysis step.

---

## The explore region, as measured

From [the explore gate](../evidence/phase2/explore-gate/README.md), 500 replications per
cell. **Eligible only where both data arms pass**, because linear-versus-nonlinear is a
property of the truth and the analyst cannot know which one they are in. The conservative
intersection is the only defensible read:

| `n` \ `p` | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|
| 50 | no | no | **yes** | no | no |
| 75 | no | **yes** | **yes** | **yes** | **yes** |
| 100 | **yes** | **yes** | **yes** | **yes** | **yes** |
| 125 | **yes** | **yes** | **yes** | **yes** | **yes** |
| 150 | **yes** | **yes** | **yes** | **yes** | **yes** |

The single eligible cell at `n = 50` is `p = 8` and should be treated as a curiosity rather
than a recommendation; it sits alone in a row of failures and one cell is not a region.

### Off-grid rules

Most real datasets will fall outside `n` in {50..150} and `p` in {6..10}. The extrapolation
rules are asymmetric, and deliberately:

* **`n` above 150, `p` in range — provisional yes.** Recovery rises monotonically with `n`
  in every column of the measured grid, so extrapolating upward has support. The verdict is
  marked provisional and names the largest `n` actually measured.
* **`n` below 50 — no.** Below the measured floor with no evidence in that direction.
* **`p` outside {6..10} — not evaluated, in either direction.** Recovery is *non-monotone*
  in `p`: it peaks at `p = 8` and falls at both 6 and 10. There is no safe direction to
  extrapolate, so the audit must decline rather than guess. This is the rule most likely to
  frustrate users and it is the one with the clearest justification.

---

## The resolve region does not exist

Four validated profiles ship, all at 300 inference rows:

| profile | `delta` |
|---|---|
| `v3-nested-blend-n300-d005-phase0` | 0.05 |
| `v4-cubic-blend-n300-d005-phase0` | 0.05 |
| `v4-cubic-blend-n300-d010-phase0` | 0.10 |
| `v4-cubic-blend-n300-d020-phase0` | 0.20 |

**Every one was trained under the minimizing separator-ranking rule that the k-sweep
falsified and that the resolve protocol rejects.** They are valid for what they calibrated
and inapplicable to the revised universal-agreement rule.

So under the revised design the audit's honest answer for resolve is currently **no
configuration is eligible**, and it must say that rather than matching against profiles
that no longer describe the analysis. This is not a defect in the audit; it is the state of
the evidence, and it resolves when the resolve protocol is approved and run.

The mechanical check, once regions exist, is the existing profile match in
[`apply_profile`](../../src/renca/calibration/apply.py) — inference rows, folds, VIMP
fingerprint, `delta` — plus the resolve operating region on `(n, p, delta)`.

---

## Verdicts

| Verdict | Reachable today | Basis |
|---|---|---|
| `explore` | yes | inside the measured region above |
| `resolve` | **no** | no calibration exists for the revised rule |
| `linear_only` | **no** | see below |
| `no_network` | yes | inside no region |

**`linear_only` cannot be issued and this needs a decision.** The explore protocol states
that the linear comparator is an incumbent benchmark whose performance "does not authorize
shipping it as a mode", and the earlier instruction was that a linear fallback "must not be
silently substituted". Recommending it would recommend a mode that does not exist and has
no evidence of its own. Option 1 below resolves this.

Every verdict carries: the reason code, the region cell consulted, the study and Actions
run the region came from, and whether the verdict is provisional.

---

## What it must never do

* Recommend from a pilot. Only full-run evidence defines a region; the explore pilots are
  explicitly non-citable.
* Imply the user's data will behave. Regions are measured on simulated truths — a Gaussian
  graphical model under monotone transforms, additive effects only, a fixed degree cap. The
  verdict is "this configuration sat inside the evaluated region", never "this will work".
* Read anything produced by the analysis.
* Silently substitute one mode for another.

---

## Artifact and placement

A `ModeEligibilityReport` beside the existing `AuditReport`, written to the output directory
and referenced from the evidence bundle manifest so the verdict is part of the permanent
record. When a run proceeds against the verdict, the manifest records that too — the
disagreement is the thing worth preserving.

Placement: after `audit_project`, before the split. It needs no data beyond what the audit
already computed.

---

## Decisions required before implementation

1. **The `linear_only` verdict.** Omit it entirely; or issue it as information only —
   "outside every renca region; a linear graphical model is what the field would otherwise
   use" — without presenting it as a renca mode; or defer until a linear mode has evidence
   of its own. Omitting is the conservative choice and the easiest to reverse.

2. **Advise or block.** When the verdict is `no_network`, does the run refuse, or proceed
   with the disagreement stamped into the manifest? Refusing is cleaner but researchers will
   route around a tool that refuses, and a stamped record is more likely to reach a reviewer
   than a run that never happened. Recommendation: proceed and stamp.

3. **Whether `p` outside {6..10} refuses outright** or emits a strong warning. The
   non-monotonicity in `p` argues for refusing; usability argues the other way, since a
   twelve-variable network is a perfectly ordinary request. Recommendation: refuse for now
   and extend the grid, because a guess here is exactly the kind of unevidenced claim the
   rest of this work exists to avoid.

## Cost

Small. The lookup is a table, the profile match already exists, and there is no computation
beyond what `audit_project` performs. The work is in the schema, the artifact wiring, and
the tests — not in any new statistics. It should not be started until the resolve region
exists, unless decision 1 resolves toward shipping an explore-only audit first.
