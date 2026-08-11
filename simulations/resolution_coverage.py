"""Can the per-pair upper limit be calibrated at psychology-scale sample sizes?

`renca.reporting.fit` reports `achieved_resolution` for every pair: `theta_hat + width`, an
upper limit on Theta. When a calibration profile matches, `width` is `|critical value| x se`.
When none matches -- which is every run below 300 inference rows -- it falls back to
`norm.ppf(confidence_level) x se`, which the module itself labels `normal_approximation` and
does not claim to validate.

The small-sample gate measured how far off that fallback is, at `Theta = delta = 0.20`: under
v4 the limit sits *below* the truth in 27% of replications at `n = 150`, against the 5% the
one-sided level asks for. That is a real defect, and it is in the dangerous direction, because
the limit exists to support "this relationship is too small to matter".

The obvious repair is to calibrate the multiplier at 100-200 rows instead of falling back. This
study asks whether that repair can work at all, and the obstacle is specific.

**Phase-0 tunes the multiplier at one point.** Every frozen family is boundary-tuned so the
oracle Theta lands exactly on `delta`, and the critical value is read there. That is the right
design for a *certificate*, which is only ever evaluated at the boundary. It is not obviously
right for an *upper limit*, which is read at whatever Theta the pair happens to have. A
multiplier calibrated at 0.20 is only useful at 0.05 or 0.35 if the studentized statistic
behaves roughly the same way there.

So this sweeps Theta and asks one question: does a single multiplier per sample size hold the
limit honest across the range, or does the required multiplier move with Theta? If it holds,
calibration is a matter of paying for replications. If it moves, the fallback cannot be
repaired by a constant and the limit needs a different construction.

**This is not a calibration and produces no profile.** Replication counts are far below the
5,000 per family the registry gate requires, and the per-cell quantiles are read from the same
draws they are evaluated on, so the miss rates under a per-cell multiplier are fitted rather
than validated. What survives that is the *comparison across Theta*, which is what is asked.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from renca.calibration.runner import run_independent_grid
from renca.calibration.scenarios import tune_boundary_signal
from renca.calibration.validation import CRITICAL_QUANTILE, REQUIRED_SCENARIO_FAMILIES
from renca.models import VimpSpec

SAMPLE_SIZES = (100, 150, 200)
THETA_VALUES = (0.05, 0.10, 0.20, 0.35)
INFERENCE_FOLDS = 5
TARGET_MISS_RATE = 0.05
"""One-sided level the upper limit is supposed to hold: the truth should sit above it this
rarely. `CRITICAL_QUANTILE` is deliberately finer, which is the margin Phase 0 buys itself."""


def shard(args: argparse.Namespace) -> None:
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[variable] = "1"
    spec = VimpSpec(forest_trees=args.forest_trees, learner_library_version=args.learner_library_version)
    # Tuning to `theta` and then passing it as `delta` is what makes the recorded statistic
    # exactly `(theta_hat - Theta) / se`, so its lower quantile is the multiplier this Theta
    # would demand on its own.
    signal, achieved = tune_boundary_signal(args.family, args.theta)
    frame = run_independent_grid(
        replications=args.replications, sample_size=args.sample_size, inference_folds=INFERENCE_FOLDS,
        delta=args.theta, critical_value=0.0, vimp_spec=spec, seed=args.seed,
        scenario_families=(args.family,), boundary_signals={args.family: signal},
        workers=args.workers or (os.cpu_count() or 1),
    )
    frame = frame.assign(sample_size=args.sample_size, theta=args.theta, boundary_signal=signal, achieved_theta=achieved, learner_library_version=args.learner_library_version, forest_trees=args.forest_trees)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)
    usable = frame.studentized_statistic.notna()
    print(f"{args.family} n={args.sample_size} Theta={args.theta}: {int(usable.sum())}/{len(frame)} usable, oracle {achieved:.4f}", flush=True)


def _miss_rate(subset: pd.DataFrame, multiplier: float) -> float:
    """Share of replications whose upper limit falls below the true Theta."""
    return float((subset.theta_hat + abs(multiplier) * subset.se_theta < subset.achieved_theta).mean())


def summarize(args: argparse.Namespace) -> None:
    frames = [pd.read_parquet(path) for path in sorted(Path(args.shards).glob("*.parquet"))]
    if not frames:
        raise ValueError(f"no shard Parquet files found in {args.shards}")
    data = pd.concat(frames, ignore_index=True)
    usable = data[data.studentized_statistic.notna()].copy()
    fallback = float(norm.ppf(1 - TARGET_MISS_RATE))

    # Step 1: what multiplier does each (n, Theta) cell demand on its own? Same rule Phase 0
    # uses -- the most extreme per-family lower quantile.
    demanded = (
        usable.groupby(["sample_size", "theta", "scenario_family"], as_index=False)
        .studentized_statistic.quantile(CRITICAL_QUANTILE, interpolation="lower")
        .rename(columns={"studentized_statistic": "family_quantile"})
    )
    per_cell = demanded.groupby(["sample_size", "theta"], as_index=False).family_quantile.min().rename(columns={"family_quantile": "demanded_multiplier"})

    # Step 2: could one multiplier per sample size serve every Theta? Take the most extreme
    # demand across the sweep and hold every cell to it.
    per_n = per_cell.groupby("sample_size", as_index=False).demanded_multiplier.min().rename(columns={"demanded_multiplier": "single_multiplier"})
    per_cell = per_cell.merge(per_n, on="sample_size")

    rows = []
    for record in per_cell.itertuples():
        cell = usable[(usable.sample_size == record.sample_size) & (usable.theta == record.theta)]
        for family in REQUIRED_SCENARIO_FAMILIES:
            subset = cell[cell.scenario_family == family]
            if subset.empty:
                raise ValueError(f"n={record.sample_size} Theta={record.theta} is missing family {family}")
            median_se = float(subset.se_theta.median())
            rows.append({
                "sample_size": int(record.sample_size), "theta": float(record.theta), "scenario_family": family,
                "replications": len(subset),
                "median_theta_hat": float(subset.theta_hat.median()),
                "bias": float(subset.theta_hat.median() - subset.achieved_theta.iloc[0]),
                "median_se": median_se,
                "demanded_multiplier": float(record.demanded_multiplier),
                "single_multiplier": float(record.single_multiplier),
                "miss_rate_fallback": _miss_rate(subset, fallback),
                "miss_rate_per_cell": _miss_rate(subset, record.demanded_multiplier),
                "miss_rate_single": _miss_rate(subset, record.single_multiplier),
                "resolution_floor_single": abs(record.single_multiplier) * median_se,
            })
    summary = pd.DataFrame(rows).sort_values(["sample_size", "theta", "scenario_family"], ignore_index=True)

    # The decision reads off the worst family in each cell: an upper limit is only as honest
    # as its least honest scenario.
    headline = summary.groupby(["sample_size", "theta"]).agg(
        demanded_multiplier=("demanded_multiplier", "first"),
        single_multiplier=("single_multiplier", "first"),
        worst_miss_fallback=("miss_rate_fallback", "max"),
        worst_miss_single=("miss_rate_single", "max"),
        worst_floor_single=("resolution_floor_single", "max"),
        worst_bias=("bias", "min"),
    ).reset_index()
    headline["single_multiplier_holds"] = headline.worst_miss_single <= TARGET_MISS_RATE

    args.output.mkdir(parents=True, exist_ok=True)
    data.to_parquet(args.output / "resolution_coverage_results.parquet", index=False)
    summary.to_csv(args.output / "resolution_coverage_by_family.csv", index=False)
    headline.to_csv(args.output / "resolution_coverage_headline.csv", index=False)
    _plot(headline, summary, args.output / "resolution_coverage.png")

    spread = per_cell.groupby("sample_size").demanded_multiplier.agg(["min", "max"])
    verdict = {
        "question": "Does one multiplier per sample size keep the per-pair upper limit honest across Theta, or does the requirement move with Theta?",
        "multiplier_spread_across_theta": {
            str(int(n)): {"most_extreme": round(float(row["min"]), 3), "least_extreme": round(float(row["max"]), 3), "ratio": round(float(row["min"] / row["max"]), 3)}
            for n, row in spread.iterrows()
        },
        "single_multiplier_holds_by_sample_size": {
            str(int(n)): bool(group.single_multiplier_holds.all()) for n, group in headline.groupby("sample_size")
        },
        "worst_fallback_miss_rate": round(float(headline.worst_miss_fallback.max()), 4),
        "fallback_multiplier": round(fallback, 4),
        "target_miss_rate": TARGET_MISS_RATE,
        "reading": (
            "Estimates, not a calibration; no profile is produced and none of these multipliers may be used. "
            "Per-cell quantiles are read from the same draws they are scored on, so `miss_rate_per_cell` is fitted "
            "by construction and carries no information. The evidence is in `miss_rate_single`, which holds every "
            "Theta to a multiplier chosen without reference to that cell alone, and in the spread of demanded "
            "multipliers across Theta. A ratio near 1 means the requirement is stable and calibration is a matter "
            "of paying for replications; a ratio far from 1 means a constant multiplier cannot serve the range."
        ),
    }
    (args.output / "resolution_coverage_verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    pd.set_option("display.width", 250)
    print(f"fallback multiplier in shipped code: {fallback:.4f}; target miss rate {TARGET_MISS_RATE}")
    print()
    print(headline.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print()
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print()
    print(json.dumps(verdict, indent=2, sort_keys=True))


def _plot(headline: pd.DataFrame, summary: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for sample_size, group in headline.groupby("sample_size"):
        group = group.sort_values("theta")
        axes[0].plot(group.theta, group.demanded_multiplier.abs(), marker="o", label=f"n = {sample_size}")
        axes[1].plot(group.theta, group.worst_miss_single, marker="o", label=f"n = {sample_size}")
        axes[2].plot(group.theta, group.worst_floor_single, marker="o", label=f"n = {sample_size}")
    axes[0].axhline(abs(norm.ppf(1 - TARGET_MISS_RATE)), color="grey", linestyle=":", label="shipped fallback")
    axes[0].set_ylabel("multiplier this Theta demands")
    axes[0].set_title("Is the requirement flat across Theta?")
    axes[1].axhline(TARGET_MISS_RATE, color="grey", linestyle=":", label="target")
    axes[1].set_ylabel("worst-family miss rate")
    axes[1].set_title("One multiplier per n, scored at every Theta")
    axes[2].set_ylabel("finest limit a null pair could reach")
    axes[2].set_title("What that honesty costs in resolution")
    for axis in axes:
        axis.set_xlabel("true Theta")
        axis.legend(fontsize=8)
        axis.grid(alpha=.3)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    shard_parser = commands.add_parser("shard", help="run one family at one sample size and one true Theta")
    shard_parser.add_argument("--family", choices=REQUIRED_SCENARIO_FAMILIES, required=True)
    shard_parser.add_argument("--sample-size", type=int, required=True, choices=SAMPLE_SIZES)
    shard_parser.add_argument("--theta", type=float, required=True, choices=THETA_VALUES)
    shard_parser.add_argument("--replications", type=int, default=600)
    shard_parser.add_argument("--output", type=Path, required=True)
    shard_parser.add_argument("--seed", type=int, default=20260810)
    shard_parser.add_argument("--workers", type=int)
    shard_parser.add_argument("--learner-library-version", default="v4_cubic_blend")
    shard_parser.add_argument("--forest-trees", type=int, default=100)
    shard_parser.set_defaults(func=shard)

    summarize_parser = commands.add_parser("summarize", help="assemble shards into the feasibility verdict")
    summarize_parser.add_argument("--shards", type=Path, required=True)
    summarize_parser.add_argument("--output", type=Path, required=True)
    summarize_parser.set_defaults(func=summarize)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
