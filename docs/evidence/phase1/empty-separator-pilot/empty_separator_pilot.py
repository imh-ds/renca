"""Step 0 pilot: is the studentized statistic well behaved with an empty conditioning set?

Every Phase-0 scenario conditions on exactly one variable, `["z"]`. The universal-agreement
rule checks every pair against `S = {}` as well, and that is a structurally different
estimation problem: the reduced model becomes the intercept, so `R(empty)` is at once the
numerator baseline and the denominator. In `fit_crossfitted_vimp` the influence function is

    (diff - psi - theta * (null - risk)) / risk

with `diff = reduced_loss - full_loss`. When `S = {}` the reduced and null models are the same
fit, so `diff` and `null` stop being distinct sources of variation and the two correction terms
become entangled. Whether that leaves a usable statistic is an open question, and it gates the
whole rule -- **every** pair must clear the empty-set check, so misbehaviour here is structural
rather than a loss of power in one corner.

The design isolates exactly that. Following `renca.calibration.thresholds`:

    y = sqrt(A) f(z) + sqrt(T) g(x) + sqrt(1 - A - T) e

with `f`, `g`, `z`, `x`, `e` independent and standardised gives `R(empty) = 1`,
`R({z}) = 1 - T` and `R({x}) = 1 - T`, so the target parameter is **`Theta = T` under either
conditioning set**. The same data can therefore be run through `S = {z}` and `S = {}` with the
identical estimand at the identical boundary, and any difference in the statistic is
attributable to the empty conditioning set alone rather than to a change of target.

`T` is set to the delta being calibrated, so every replication sits exactly on the boundary,
which is where a critical value is read.

Nothing here is a calibration. It reports the shape of the statistic and the critical value
each conditioning mode would imply, as a go/no-go before paying for a full Phase-0 run.
"""

from __future__ import annotations

import argparse
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from renca.calibration.thresholds import _standardised
from renca.calibration.validation import CRITICAL_QUANTILE
from renca.models import NodeSpec, VimpSpec
from renca.screening import SplitManifest
from renca.vimp import fit_crossfitted_vimp

HERE = Path(__file__).resolve().parent
SEED_ROOT = 20260810
INFERENCE_ROWS = 300
INFERENCE_FOLDS = 5
DELTA = 0.20
SEPARATOR_SIGNAL = 0.35  # what z explains; irrelevant to the estimand, central to the reduced fit

# Shapes spanning what the learner library covers and what it cannot, matching the range the
# existing scenario families sweep. `learner_misspecification_v1` -- an unlearnable added
# variable -- is the family that binds every shipped profile, so it is carried here too.
CELLS = (
    ("linear", "linear"),
    ("linear", "cubic"),
    ("cubic", "linear"),
    ("linear", "oscillatory"),
    ("oscillatory", "linear"),
)
MODES = ("empty_separator", "single_separator")

_WORKER: dict[str, object] = {}


def scenario(*, separator_form: str, added_form: str, n: int, seed: int, theta: float) -> pd.DataFrame:
    generator = np.random.default_rng(seed)
    z, x, error = generator.normal(size=(3, n))
    y = (
        math.sqrt(SEPARATOR_SIGNAL) * _standardised(z, separator_form)
        + math.sqrt(theta) * _standardised(x, added_form)
        + math.sqrt(1 - SEPARATOR_SIGNAL - theta) * error
    )
    return pd.DataFrame({"z": z, "x": x, "y": y})


def manifest(n: int, seed: int, folds: int) -> SplitManifest:
    rows = list(range(n))
    return SplitManifest(
        schema_version="1.7.0", analysis_id="00000000-0000-0000-0000-000000000003", seed=seed,
        selection_fraction=.2, inference_folds=folds, sampling_unit="iid", selection_row_positions=[],
        inference_row_positions=rows, inference_fold_by_row_position={row: row % folds for row in rows},
        stratification_columns=[], input_order_sha256="empty-separator-pilot",
    )


def one(item: tuple[str, str, int]) -> list[dict[str, object]]:
    separator_form, added_form, replicate = item
    seed = int(np.random.SeedSequence([SEED_ROOT, CELLS.index((separator_form, added_form)), replicate]).generate_state(1)[0])
    delta = _WORKER["delta"]
    spec: VimpSpec = _WORKER["vimp_spec"]
    node = NodeSpec(node_id="y", outcome_type="continuous", loss="squared", delta=delta)
    data = scenario(separator_form=separator_form, added_form=added_form, n=INFERENCE_ROWS, seed=seed, theta=delta)
    folds = manifest(INFERENCE_ROWS, seed, INFERENCE_FOLDS)
    rows = []
    # The same rows through both conditioning modes: the estimand is Theta = delta either way,
    # so the pair is a controlled comparison rather than two separate scenarios.
    for mode, separator in (("empty_separator", []), ("single_separator", ["z"])):
        estimate = fit_crossfitted_vimp(data, "y", "x", separator, node, folds, spec)
        usable = estimate.status == "success" and estimate.theta_hat is not None and estimate.se_theta is not None and estimate.se_theta > 0
        rows.append({
            "separator_form": separator_form, "added_form": added_form, "mode": mode,
            "replicate": replicate, "seed": seed, "status": estimate.status,
            "theta_hat": estimate.theta_hat, "se_theta": estimate.se_theta,
            "studentized_statistic": (estimate.theta_hat - delta) / estimate.se_theta if usable else None,
            "usable": usable,
        })
    return rows


def _initialize(delta: float, version: str, forest_trees: int) -> None:
    _WORKER.update(delta=delta, vimp_spec=VimpSpec(forest_trees=forest_trees, learner_library_version=version))


def _task(item: tuple[str, str, int]) -> list[dict[str, object]]:
    with threadpool_limits(limits=1):
        return one(item)


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (separator_form, added_form, mode), group in results.groupby(["separator_form", "added_form", "mode"]):
        usable = group[group.usable]
        statistics = usable.studentized_statistic.dropna()
        rows.append({
            "separator_form": separator_form, "added_form": added_form, "mode": mode,
            "replications": len(group), "usable_rate": float(group.usable.mean()),
            "median_theta_bias": float(usable.theta_hat.median() - DELTA) if len(usable) else float("nan"),
            "median_se": float(usable.se_theta.median()) if len(usable) else float("nan"),
            "median_statistic": float(statistics.median()) if len(statistics) else float("nan"),
            # The quantile Phase 0 reads its critical value from, deliberately below alpha.
            "implied_critical_value": float(np.quantile(statistics, CRITICAL_QUANTILE)) if len(statistics) else float("nan"),
            "statistic_p01": float(np.quantile(statistics, .01)) if len(statistics) else float("nan"),
            "nonfinite_statistics": int((~np.isfinite(statistics)).sum()) if len(statistics) else 0,
        })
    return pd.DataFrame(rows).sort_values(["mode", "separator_form", "added_form"], ignore_index=True)


def pooled(results: pd.DataFrame) -> pd.DataFrame:
    """The headline comparison: both modes pooled across shapes, which is where the 4% quantile
    has enough support to be read as a critical value rather than a noisy order statistic."""
    rows = []
    for mode, group in results.groupby("mode"):
        usable = group[group.usable]
        statistics = usable.studentized_statistic.dropna()
        rows.append({
            "mode": mode, "replications": len(group), "usable_rate": float(group.usable.mean()),
            "median_theta_bias": float(usable.theta_hat.median() - DELTA),
            "median_se": float(usable.se_theta.median()),
            "median_statistic": float(statistics.median()),
            "implied_critical_value": float(np.quantile(statistics, CRITICAL_QUANTILE)),
            "statistic_p01": float(np.quantile(statistics, .01)),
            "statistic_min": float(statistics.min()),
        })
    return pd.DataFrame(rows)


def shard(args: argparse.Namespace) -> None:
    cell = CELLS[args.cell]
    items = [(cell[0], cell[1], replicate) for replicate in range(args.replications)]
    workers = args.workers if args.workers else (os.cpu_count() or 1)
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[variable] = "1"
    print(f"cell {cell}: {len(items)} replications x 2 conditioning modes, {workers} workers", flush=True)
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers, initializer=_initialize, initargs=(args.delta, args.learner_library_version, args.forest_trees)) as pool:
        batches = list(pool.map(_task, items, chunksize=2))
    print(f"finished in {time.perf_counter() - started:.0f}s", flush=True)
    frame = pd.DataFrame([row for batch in batches for row in batch])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)


def assemble(args: argparse.Namespace) -> None:
    frames = [pd.read_parquet(path) for path in sorted(Path(args.shards).glob("*.parquet"))]
    if not frames:
        raise ValueError(f"no shard Parquet files found in {args.shards}")
    results = pd.concat(frames, ignore_index=True)
    by_cell, headline = summarize(results), pooled(results)
    args.output.mkdir(parents=True, exist_ok=True)
    results.to_parquet(args.output / "empty_separator_results.parquet", index=False)
    by_cell.to_csv(args.output / "empty_separator_by_cell.csv", index=False)
    headline.to_csv(args.output / "empty_separator_pooled.csv", index=False)
    pd.set_option("display.width", 250)
    print(headline.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print()
    print(by_cell.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    shard_parser = commands.add_parser("shard", help="run one shape cell")
    shard_parser.add_argument("--cell", type=int, required=True, choices=range(len(CELLS)))
    shard_parser.add_argument("--replications", type=int, default=300)
    shard_parser.add_argument("--output", type=Path, required=True)
    shard_parser.add_argument("--delta", type=float, default=DELTA)
    shard_parser.add_argument("--workers", type=int)
    shard_parser.add_argument("--learner-library-version", default="v4_cubic_blend")
    shard_parser.add_argument("--forest-trees", type=int, default=100, help="the packaged profiles' setting, not the benchmark's 10")
    shard_parser.set_defaults(func=shard)

    assemble_parser = commands.add_parser("assemble", help="pool shards into the comparison")
    assemble_parser.add_argument("--shards", type=Path, required=True)
    assemble_parser.add_argument("--output", type=Path, required=True)
    assemble_parser.set_defaults(func=assemble)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
