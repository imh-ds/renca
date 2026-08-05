"""Train and independently validate a frozen grid-calibrated VIMP profile."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from renca.calibration import critical_value_from_training, REQUIRED_SCENARIO_FAMILIES, run_independent_grid, validate_grid, vimp_fingerprint
from renca.calibration.registry import file_sha256
from renca.calibration.scenarios import tune_boundary_signal
from renca.models import VimpSpec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile-id", default="v1-grid-n300-d005")
    parser.add_argument("--training-replications", type=int, default=20)
    parser.add_argument("--validation-replications", type=int, default=20)
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260801)
    parser.add_argument("--learner-library-version", choices=["v2_quadratic_ridge", "v3_nested_blend"], default="v2_quadratic_ridge")
    args = parser.parse_args()
    delta = .05; folds = 5; spec = VimpSpec(forest_trees=10, learner_library_version=args.learner_library_version)
    signals = {family: tune_boundary_signal(family, delta) for family in REQUIRED_SCENARIO_FAMILIES}
    signal_values = {family: item[0] for family, item in signals.items()}
    training = run_independent_grid(replications=args.training_replications, sample_size=args.sample_size, inference_folds=folds, delta=delta, critical_value=float("-inf"), vimp_spec=spec, seed=args.seed, boundary_signals=signal_values)
    eligible_training = training.loc[training.status == "success"].copy()
    critical_value = critical_value_from_training(eligible_training)
    validation = run_independent_grid(replications=args.validation_replications, sample_size=args.sample_size, inference_folds=folds, delta=delta, critical_value=float(critical_value), vimp_spec=spec, seed=args.seed + 1, boundary_signals=signal_values)
    args.output.mkdir(parents=True, exist_ok=True)
    distribution_path = args.output / "calibration_distribution.parquet"; eligible_training.to_parquet(distribution_path, index=False)
    validation.to_parquet(args.output / "independent_validation.parquet", index=False)
    successful = training.groupby("scenario_family").status.apply(lambda values: int((values == "success").sum())).to_dict()
    record = validate_grid(validation, profile_id=args.profile_id, scenario_family="continuous_linear_boundary_v1", delta_target=delta, inference_rows=args.sample_size, inference_folds=folds, vimp_fingerprint=vimp_fingerprint(spec), critical_value=float(critical_value), distribution_file=distribution_path.name, distribution_sha256=file_sha256(distribution_path), calibration_replications=args.training_replications, calibration_successful_replications_per_family=successful, alpha=.05)
    (args.output / "boundary_tuning.json").write_text(json.dumps({family: {"signal": signal, "oracle_theta": theta} for family, (signal, theta) in signals.items()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output / "calibration_summary.json").write_text(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
