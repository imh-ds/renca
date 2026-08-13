# renca

**This project is dead. It was declared closed on 2026-08-12 and is not maintained.**

Do not use this package. The code that ships still implements a separator-selection rule that
was measured to be structurally unsound, and none of its calibration profiles apply to the
repair that replaced it.

renca was an attempt to build psychological network models that could assert a relationship is
**absent** — with a stated and validated error rate — rather than only that one is present. It
ran for thirteen days across roughly twenty simulation studies. It did not reach a state where
it should be used.

**The one-line result:** certifying absence with calibrated error control is out of reach at
the sample sizes behavioural research actually works with. At 100 participants the finest
statement this method could support was roughly *"this variable explains less than 38% of that
one's variance"* — true, and useless. That bounds this class of procedure; it is not a claim
that network estimation in general is impossible at these sample sizes.

**The process result**, which travels further than the statistical one: the project's gates
were scored honestly and never terminated anything. They answered "may the next subsystem be
built?" when the question that needed asking was "does this specification still deserve to
exist?" See [§6.0 of the post-mortem](docs/POSTMORTEM.md#60-the-central-mistake).

## Read this

* **[`docs/POSTMORTEM.md`](docs/POSTMORTEM.md)** — the historical record: what was attempted,
  what was measured, every failure and its cause, and where ambition derailed the project.
  Start here.
* **[`docs/evidence/README.md`](docs/evidence/README.md)** — the evidence chain. Every study in
  the order it was run, with what each established and what it ruled out.

Every study is a dispatchable workflow and every evidence directory records the GitHub Actions
run id it came from, so any published number can be reproduced.
