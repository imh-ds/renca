# Phase 1 predictive release checklist

- Run the complete test suite and the bundled calibrated example.
- Confirm schema/artifact readers accept every emitted JSON and Parquet file.
- Replay fixed input, configuration, and seed; compare canonical artifacts.
- Check `calibration_eligibility.json`, registry hash, code/package version,
  input hash, and configuration hash in the evidence bundle.
- Confirm reports preserve predictive-only language and `not_yet_causal`.
- Archive the whole output directory and label uncalibrated analyses exploratory.
