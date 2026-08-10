"""Step A: is `delta = 0.20` reachable at psychology-scale sample sizes?

A miniature calibration, run as a gate before committing to full Phase-0 cycles. It uses the
production calibration path -- `run_independent_grid` with the frozen scenario families, the
same boundary tuning, and the same studentized statistic -- at a fraction of the replications,
purely to estimate two numbers per sample size:

* the **critical value**, reproduced exactly as `critical_value_from_training` derives it: the
  most extreme per-family lower quantile at `CRITICAL_QUANTILE`;
* the typical **standard error**, per family.

Those give the quantity that actually decides usability. A pair can be certified only when

    standard error <= delta / |critical value|

so the *resolution floor* `|critical value| x se` is the finest `delta` a pair whose estimate is
exactly zero could reach. A floor above `delta` means certification is impossible at that
resolution whatever the truth is, and no amount of correct behaviour rescues it.

**This is not a calibration and produces no profile.** Its replication counts are far below the
5,000 per family the registry gate requires, so its critical values are estimates with real
sampling error -- the quantile at 600 replications is the 24th smallest observation. It exists
to answer one question cheaply: whether a full Phase-0 run at these sample sizes is worth
paying for.

`n = 300` is included as a control. A shipped profile already exists at 300 inference rows for
`delta = 0.20` with a critical value of `-3.084`, so the miniature's own estimate at that rung
says how much to trust its estimates at the others.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from renca.calibration.runner import run_independent_grid
from renca.calibration.scenarios import tune_boundary_signal
from renca.calibration.validation import CRITICAL_QUANTILE, REQUIRED_SCENARIO_FAMILIES
from renca.models import VimpSpec

SAMPLE_SIZES = (100, 150, 200, 300)
INFERENCE_FOLDS = 5
SHIPPED_CRITICAL_VALUE_AT_300 = -3.0840871297004298  # v4-cubic-blend-n300-d020-phase0


def shard(args: argparse.Namespace) -> None:
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[variable] = "1"
    spec = VimpSpec(forest_trees=args.forest_trees, learner_library_version=args.learner_library_version)
    # Tuned once per shard rather than per replication; the frozen DGP puts the oracle Theta
    # exactly on delta, which is where a critical value has to be read.
    signal, achieved = tune_boundary_signal(args.family, args.delta)
    frame = run_independent_grid(
        replications=args.replications, sample_size=args.sample_size, inference_folds=INFERENCE_FOLDS,
        delta=args.delta, critical_value=0.0, vimp_spec=spec, seed=args.seed,
        scenario_families=(args.family,), boundary_signals={args.family: signal},
        workers=args.workers or (os.cpu_count() or 1),
    )
    frame = frame.assign(sample_size=args.sample_size, delta=args.delta, boundary_signal=signal, achieved_theta=achieved)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)
    usable = frame.studentized_statistic.notna()
    print(f"{args.family} n={args.sample_size}: {int(usable.sum())}/{len(frame)} usable, oracle Theta {achieved:.4f}", flush=True)


def critical_value(frame: pd.DataFrame, quantile: float = CRITICAL_QUANTILE) -> float:
    """The most extreme per-family lower quantile, exactly as Phase 0 derives it."""
    return float(min(
        frame.loc[frame.scenario_family == family, "studentized_statistic"].dropna().quantile(quantile, interpolation="lower")
        for family in REQUIRED_SCENARIO_FAMILIES
    ))


def summarize(args: argparse.Namespace) -> None:
    frames = [pd.read_parquet(path) for path in sorted(Path(args.shards).glob("*.parquet"))]
    if not frames:
        raise ValueError(f"no shard Parquet files found in {args.shards}")
    data = pd.concat(frames, ignore_index=True)
    delta = float(data.delta.iloc[0])

    rows = []
    for sample_size, group in data.groupby("sample_size"):
        missing = set(REQUIRED_SCENARIO_FAMILIES) - set(group.scenario_family)
        if missing:
            raise ValueError(f"n={sample_size} is missing families: {', '.join(sorted(missing))}")
        critical = critical_value(group)
        tolerated = delta / abs(critical)
        for family in REQUIRED_SCENARIO_FAMILIES:
            subset = group[group.scenario_family == family]
            usable = subset[subset.studentized_statistic.notna()]
            median_se = float(usable.se_theta.median())
            rows.append({
                "sample_size": int(sample_size), "scenario_family": family,
                "replications": len(subset), "abstention_rate": float((subset.status != "success").mean()),
                "median_theta_hat": float(usable.theta_hat.median()),
                "median_se": median_se,
                "family_quantile": float(usable.studentized_statistic.quantile(CRITICAL_QUANTILE, interpolation="lower")),
                "critical_value": critical,
                "tolerated_se": tolerated,
                "resolution_floor": abs(critical) * median_se,
                "reachable": bool(abs(critical) * median_se <= delta),
            })
    summary = pd.DataFrame(rows).sort_values(["sample_size", "scenario_family"], ignore_index=True)

    headline = summary.groupby("sample_size").agg(
        critical_value=("critical_value", "first"),
        tolerated_se=("tolerated_se", "first"),
        worst_family_se=("median_se", "max"),
        worst_resolution_floor=("resolution_floor", "max"),
        families_reachable=("reachable", "sum"),
        max_abstention=("abstention_rate", "max"),
    ).reset_index()
    headline["delta_reachable_everywhere"] = headline.worst_resolution_floor <= delta

    args.output.mkdir(parents=True, exist_ok=True)
    data.to_parquet(args.output / "small_sample_gate_results.parquet", index=False)
    summary.to_csv(args.output / "small_sample_gate_by_family.csv", index=False)
    headline.to_csv(args.output / "small_sample_gate_headline.csv", index=False)

    pd.set_option("display.width", 250)
    print(f"delta = {delta}; a pair certifies only when its standard error is at or below delta / |critical value|")
    print()
    print(headline.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print()
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))

    control = headline[headline.sample_size == 300]
    verdict = {
        "smallest_reachable_sample_size": (
            int(headline[headline.delta_reachable_everywhere].sample_size.min())
            if bool(headline.delta_reachable_everywhere.any()) else None
        ),
        "control_check_at_n300": {
            "miniature_critical_value": round(float(control.critical_value.iloc[0]), 4) if len(control) else None,
            "shipped_profile_critical_value": SHIPPED_CRITICAL_VALUE_AT_300,
            "note": "Agreement here is what licenses reading the other rungs; disagreement means the miniature's replication count is too low to estimate the quantile.",
        },
        "reading": "Estimates, not a calibration. Replication counts are far below the 5,000 per family the registry gate requires, and no profile is produced.",
    }
    (args.output / "small_sample_gate_verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print()
    print(json.dumps(verdict, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    shard_parser = commands.add_parser("shard", help="run one family at one sample size")
    shard_parser.add_argument("--family", choices=REQUIRED_SCENARIO_FAMILIES, required=True)
    shard_parser.add_argument("--sample-size", type=int, required=True, choices=SAMPLE_SIZES)
    shard_parser.add_argument("--replications", type=int, default=600)
    shard_parser.add_argument("--output", type=Path, required=True)
    shard_parser.add_argument("--delta", type=float, default=.20)
    shard_parser.add_argument("--seed", type=int, default=20260810)
    shard_parser.add_argument("--workers", type=int)
    shard_parser.add_argument("--learner-library-version", default="v4_cubic_blend")
    shard_parser.add_argument("--forest-trees", type=int, default=100)
    shard_parser.set_defaults(func=shard)

    summarize_parser = commands.add_parser("summarize", help="assemble shards into the gate decision")
    summarize_parser.add_argument("--shards", type=Path, required=True)
    summarize_parser.add_argument("--output", type=Path, required=True)
    summarize_parser.set_defaults(func=summarize)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
