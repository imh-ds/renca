"""Run and archive a deterministic independent VIMP calibration grid."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from renca.calibration import run_independent_grid, validate_grid, vimp_fingerprint
from renca.models import VimpSpec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replications", type=int, default=20)
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20260801)
    args = parser.parse_args()
    spec = VimpSpec(forest_trees=10)
    critical_value = -2.1099877626362535
    results = run_independent_grid(replications=args.replications, sample_size=args.sample_size, inference_folds=5, delta=.05, critical_value=critical_value, vimp_spec=spec, seed=args.seed)
    record = validate_grid(results, scenario_family="continuous_linear_boundary_v1", sample_size=args.sample_size, inference_folds=5, vimp_fingerprint=vimp_fingerprint(spec), critical_value=critical_value, calibration_replications=1000)
    args.output.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output / "independent_grid_results.csv", index=False)
    (args.output / "independent_grid_summary.json").write_text(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
