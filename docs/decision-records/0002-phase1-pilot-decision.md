# Phase 1 pilot decision record

## Protocol and archived evidence

The first pilot is the authorized deterministic synthetic workflow specified in
`docs/pilots/phase1-synthetic-protocol.md`. Its reproducible generator and
configuration are bundled under `examples/phase1_calibrated`. A fresh run on
2026-08-03 wrote the complete local evidence bundle to
`build/phase1-pilot-review-20260803/`; that directory contains the audit,
split, separator candidates, directional estimates, certificates, report, and
evidence-bundle manifest.

## Results

- Audit: eligible; 375 complete cases and 0 exclusions.
- Calibration: exact `v3-nested-blend-n300-d005-phase0` match; all six
  directional estimates had `calibrated_success`.
- Pair conclusions: 1 `certified_nonedge`, 1 `candidate_adjacency`, and 1
  `unresolved`.
- Diagnostics: 6 successful directional estimates, 0 abstentions, and 0
  `full_worse_than_reduced` events.

The report retained predictive-only language and `not_yet_causal` for every
pair. In particular, the candidate adjacency was not described as a causal
edge and the certified practical nonedge was not promoted to a causal claim.

## Decision: Proceed (scoped)

Proceed with Phase 1 operational hardening: the calibrated route is
reproducible, its scope is visible, and the evidence ledger presents useful
mixed outcomes without suppressing uncertainty. This decision applies only to
the deterministic synthetic operational pilot. A public or authorized
representative tabular pilot is still required before a broader release or any
decision to extend calibration.
