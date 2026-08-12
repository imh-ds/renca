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

**6 to 10 variables is the current validated range, not a product limit.** Comprehensive
psychological datasets commonly carry 15 to 30 variables, and a tool that refuses them is
not a tool for that field. The grid is small because that is what has been simulated so
far, and extending it is the subject of
[the p-extension protocol](../pilots/explore-p-extension-protocol.md).

### The audit labels; it does not refuse

Refusal belongs to `audit_project`, which stops a run for genuine technical or data-quality
failures — missing columns, non-finite values, a variable with no variance, saturated
scales, too few complete rows for the fold structure. Those are reasons the analysis cannot
execute.

Being outside a simulation grid is not such a reason. The analysis executes fine; what is
missing is evidence about how well it performs. So the audit attaches a **label** and the
run proceeds.

| Condition | Label |
|---|---|
| `p` 6-10, and `n` inside the table above | **validated** |
| `p` 11-30 | **unsupported — not yet validated at this network size** |
| `p` above 30 | **unsupported — statistical *and* computational behaviour unevaluated at this size** |
| `p` 6-10 but `n` outside the table | **unsupported — not yet validated at this sample size** |

`n` above 150 with `p` in range is the one extrapolation with support, since recovery rises
monotonically with `n` in every column measured; it is labelled **provisional** rather than
unsupported, and names the largest `n` actually tested.

The label is written into the report and into the evidence bundle manifest, so a reader
downstream sees what evidence stood behind the run. The stronger warning above 30 variables
is separate because two different things are unknown there: whether the results are any
good, and whether the run finishes in reasonable time and memory at all.

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

| Verdict | Available today | Basis |
|---|---|---|
| `explore`, labelled **validated** | yes | inside the measured region above |
| `explore`, labelled **unsupported** | yes | outside the grid; runs, carries the warning |
| `resolve` | **no** | no calibration exists for the revised rule |
| `no_network` | yes | `audit_project` refused on technical or data-quality grounds |

**There is no `linear_only` verdict.** The linear method used in the explore study is a
comparison benchmark, not a renca mode; testing something as a benchmark does not build it
and gives it no evidence of its own. The audit will not name it, recommend it, or fall back
to it. Whether a linear mode should ever exist is a separate decision, not taken.

`no_network` is now reserved for genuine failures rather than for absent evidence. A clean
dataset outside every grid gets `explore` with an unsupported label, not a refusal.

Every verdict carries: the label, the reason code, the region cell consulted, the study and
Actions run the region came from, and whether the label is provisional.

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

## Decisions taken

All three open questions in the first draft of this scope have been settled:

1. **No `linear_only` verdict.** Not added, not endorsed, not offered as a fallback.
2. **The audit labels rather than blocks.** Refusal is reserved for technical and
   data-quality failures, which `audit_project` already owns.
3. **Variable counts outside the grid run with a label**, not a refusal. 6 to 10 is the
   current validated range and explicitly not a product limit; the grid extends via
   [the p-extension protocol](../pilots/explore-p-extension-protocol.md).

## Cost

Small. The lookup is a table, the profile match already exists, and there is no computation
beyond what `audit_project` performs. The work is in the schema, the artifact wiring, and
the tests — not in any new statistics. It should not be started until the resolve region
exists, unless decision 1 resolves toward shipping an explore-only audit first.
