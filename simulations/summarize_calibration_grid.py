"""Re-summarize immutable calibration ledgers under the current profile rule."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from renca.calibration.validation import validate_grid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    prior = json.loads((args.evidence / "calibration_summary.json").read_text(encoding="utf-8"))
    training = pd.read_parquet(args.evidence / "calibration_distribution.parquet")
    validation = pd.read_parquet(args.evidence / "independent_validation.parquet")
    successful = training.groupby("scenario_family").size().astype(int).to_dict()
    record = validate_grid(validation, profile_id=prior["profile_id"], scenario_family=prior["scenario_family"], delta_target=prior["delta_target"], inference_rows=prior["inference_rows"], inference_folds=prior["inference_folds"], vimp_fingerprint=prior["vimp_fingerprint"], critical_value=prior["critical_value"], distribution_file=prior["distribution_file"], distribution_sha256=prior["distribution_sha256"], calibration_replications=prior["calibration_replications"], calibration_successful_replications_per_family=successful)
    coverage = validation.groupby("scenario_family").status.agg(total="size", successful=lambda values: int((values == "success").sum())).reset_index()
    coverage["abstentions"] = coverage.total - coverage.successful
    coverage["abstention_rate"] = coverage.abstentions / coverage.total
    (args.evidence / "calibration_summary_abstention_aware.json").write_text(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    coverage.to_json(args.evidence / "abstention_report.json", orient="records", indent=2)


if __name__ == "__main__":
    main()
