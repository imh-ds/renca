"""Deterministic shard and aggregation commands for the formal Phase-0 study."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import pandas as pd

from renca.calibration import CRITICAL_QUANTILE, REQUIRED_SCENARIO_FAMILIES, critical_value_from_training, run_independent_grid, validate_grid, vimp_fingerprint
from renca.calibration.registry import file_sha256
from renca.calibration.scenarios import tune_boundary_signal
from renca.models import VimpSpec


def _spec(version: str) -> VimpSpec:
    return VimpSpec(forest_trees=10, learner_library_version=version)


def shard(args: argparse.Namespace) -> None:
    spec = _spec(args.learner_library_version); family = args.family; signal = tune_boundary_signal(family, .05)[0]
    critical = float("-inf") if args.phase == "training" else json.loads(Path(args.training_manifest).read_text(encoding="utf-8"))["critical_value"]
    workers = args.workers if args.workers else (os.cpu_count() or 1)
    frame = run_independent_grid(replications=args.count, replicate_start=args.start, sample_size=300, inference_folds=5, delta=.05, critical_value=critical, vimp_spec=spec, seed=args.seed, scenario_families=(family,), boundary_signals={family: signal}, workers=workers)
    args.output.parent.mkdir(parents=True, exist_ok=True); frame.to_parquet(args.output, index=False)


def training_manifest(args: argparse.Namespace) -> None:
    frames = [pd.read_parquet(path) for path in Path(args.shards).glob("*.parquet")]; data = pd.concat(frames, ignore_index=True)
    _validate(data, args.training_replications); eligible = data.loc[data.status == "success"].copy()
    critical = critical_value_from_training(eligible)
    args.output.mkdir(parents=True, exist_ok=True); distribution = args.output / "calibration_distribution.parquet"; eligible.to_parquet(distribution, index=False)
    payload = {"critical_value": float(critical), "critical_quantile": CRITICAL_QUANTILE, "distribution_file": distribution.name, "distribution_sha256": file_sha256(distribution), "successful_training": eligible.groupby("scenario_family").size().astype(int).to_dict(), "vimp_fingerprint": vimp_fingerprint(_spec(args.learner_library_version))}
    (args.output / "training_manifest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def final(args: argparse.Namespace) -> None:
    output = Path(args.output); manifest = json.loads((Path(args.training) / "training_manifest.json").read_text(encoding="utf-8")); validation = pd.concat([pd.read_parquet(path) for path in Path(args.validation).glob("*.parquet")], ignore_index=True)
    _validate(validation, args.validation_replications)
    record = validate_grid(validation, profile_id="v3-nested-blend-n300-d005-phase0", scenario_family="continuous_linear_boundary_v1", delta_target=.05, inference_rows=300, inference_folds=5, vimp_fingerprint=manifest["vimp_fingerprint"], critical_value=manifest["critical_value"], critical_quantile=manifest.get("critical_quantile", .05), distribution_file="calibration_distribution.parquet", distribution_sha256=manifest["distribution_sha256"], calibration_replications=args.training_replications, calibration_successful_replications_per_family=manifest["successful_training"])
    output.mkdir(parents=True, exist_ok=True); shutil.copy2(Path(args.training) / manifest["distribution_file"], output / "calibration_distribution.parquet"); validation.to_parquet(output / "independent_validation.parquet", index=False); (output / "calibration_summary.json").write_text(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validate(data: pd.DataFrame, expected: int) -> None:
    if set(data.scenario_family) != set(REQUIRED_SCENARIO_FAMILIES) or data.duplicated(["scenario_family", "replicate"]).any() or any(len(data.loc[data.scenario_family == family]) != expected for family in REQUIRED_SCENARIO_FAMILIES):
        raise ValueError("Phase-0 shard set is incomplete, duplicated, or has an unexpected replicate count")


def main() -> None:
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(dest="command", required=True)
    shard_parser = commands.add_parser("shard"); shard_parser.add_argument("--phase", choices=["training", "validation"], required=True); shard_parser.add_argument("--family", choices=REQUIRED_SCENARIO_FAMILIES, required=True); shard_parser.add_argument("--start", type=int, required=True); shard_parser.add_argument("--count", type=int, required=True); shard_parser.add_argument("--output", type=Path, required=True); shard_parser.add_argument("--seed", type=int, default=20260809); shard_parser.add_argument("--learner-library-version", default="v3_nested_blend"); shard_parser.add_argument("--workers", type=int, help="parallel replications; defaults to the core count"); shard_parser.add_argument("--training-manifest"); shard_parser.set_defaults(func=shard)
    train_parser = commands.add_parser("training-manifest"); train_parser.add_argument("--shards", type=Path, required=True); train_parser.add_argument("--output", type=Path, required=True); train_parser.add_argument("--training-replications", type=int, default=6000); train_parser.add_argument("--learner-library-version", default="v3_nested_blend"); train_parser.set_defaults(func=training_manifest)
    final_parser = commands.add_parser("final"); final_parser.add_argument("--training", type=Path, required=True); final_parser.add_argument("--validation", type=Path, required=True); final_parser.add_argument("--output", type=Path, required=True); final_parser.add_argument("--training-replications", type=int, default=6000); final_parser.add_argument("--validation-replications", type=int, default=5000); final_parser.set_defaults(func=final)
    args = parser.parse_args(); args.func(args)


if __name__ == "__main__":
    main()
