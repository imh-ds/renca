"""Deterministic shard and aggregation commands for the fit-index threshold study.

Maps observed predictive adequacy and resolution floor onto false-prune and correct-prune
rates, so cut-offs for `renca.reporting.fit` can be stated with evidence instead of
invented. Mirrors the sharding layout of `phase0_calibration.py` and `multipair_fwer.py`.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from renca.calibration.registry import CalibrationRegistry
from renca.calibration.thresholds import run_threshold_replication, summarize_learnability, summarize_threshold_grid
from renca.models import VimpSpec
from renca.runner import default_calibration_registry_path

PROFILE_ID = "v3-nested-blend-n300-d005-phase0"
TRUE_ADEQUACY = (0.0, 0.05, 0.15, 0.35, 0.60)
TRUE_THETA = (0.0, 0.02, 0.15)          # delta is 0.05, so only 0.15 is a true edge
FORMS = (("linear", "linear"), ("linear", "oscillatory"))

_WORKER: dict[str, object] = {}


def _spec() -> VimpSpec:
    return VimpSpec(forest_trees=10, learner_library_version="v3_nested_blend")


def cells() -> list[tuple[float, float, str, str]]:
    return [(a, t, sf, af) for a, t in itertools.product(TRUE_ADEQUACY, TRUE_THETA) for sf, af in FORMS]


def _initialize(critical_value: float, delta: float, n: int) -> None:
    _WORKER.update(critical_value=critical_value, delta=delta, n=n, vimp_spec=_spec())


def _run(item: tuple[float, float, str, str, int, int]) -> dict[str, object]:
    adequacy, theta, separator_form, added_form, replicate, seed = item
    result = run_threshold_replication(
        adequacy=adequacy, theta=theta, separator_form=separator_form, added_form=added_form,
        n=_WORKER["n"], seed=seed, delta=_WORKER["delta"],
        critical_value=_WORKER["critical_value"], vimp_spec=_WORKER["vimp_spec"],
    )
    return {**result, "replicate": replicate}


def shard(args: argparse.Namespace) -> None:
    registry = CalibrationRegistry.load(args.calibration_registry or default_calibration_registry_path())
    record = next(item for item in registry.records if item.profile_id == PROFILE_ID)
    if record.inference_rows != args.n or record.delta_target != args.delta:
        raise ValueError(f"profile {PROFILE_ID} is calibrated at n={record.inference_rows}, delta={record.delta_target}")
    items = [
        (a, t, sf, af, args.start + offset, int(np.random.SeedSequence([args.seed, index, args.start + offset]).generate_state(1)[0]))
        for index, (a, t, sf, af) in enumerate(cells())
        for offset in range(args.count)
    ]
    workers = args.workers if args.workers else (os.cpu_count() or 1)
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[variable] = "1"
    with threadpool_limits(limits=1):
        if workers > 1:
            with ProcessPoolExecutor(max_workers=workers, initializer=_initialize, initargs=(record.critical_value, args.delta, args.n)) as pool:
                rows = list(pool.map(_run, items, chunksize=1))
        else:
            _initialize(record.critical_value, args.delta, args.n)
            rows = [_run(item) for item in items]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(args.output, index=False)


def summarize(args: argparse.Namespace) -> None:
    frames = [pd.read_parquet(path) for path in sorted(Path(args.shards).glob("*.parquet"))]
    if not frames:
        raise ValueError(f"no shard Parquet files found in {args.shards}")
    data = pd.concat(frames, ignore_index=True)
    if data.duplicated(["true_adequacy", "true_theta", "separator_form", "added_form", "replicate"]).any():
        raise ValueError("replicates must be unique within each cell")
    by_adequacy = summarize_threshold_grid(data)
    by_learnability = summarize_learnability(data)
    args.output.mkdir(parents=True, exist_ok=True)
    data.to_parquet(args.output / "threshold_results.parquet", index=False)
    by_adequacy.to_csv(args.output / "threshold_by_adequacy.csv", index=False)
    by_learnability.to_csv(args.output / "threshold_by_learnability.csv", index=False)
    summary = {
        "profile_id": PROFILE_ID,
        "replications": int(len(data)),
        "cells": int(len(cells())),
        "overall_false_prune_rate": float(data[data.true_edge].false_prune.mean()),
        "overall_correct_prune_rate": float(data[~data.true_edge].correct_prune.mean()),
        "by_adequacy": json.loads(by_adequacy.to_json(orient="records")),
        "by_learnability": json.loads(by_learnability.to_json(orient="records")),
    }
    (args.output / "threshold_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("replications", "cells", "overall_false_prune_rate", "overall_correct_prune_rate")}, indent=2))
    print(by_adequacy.to_string(index=False))
    print(by_learnability.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    shard_parser = commands.add_parser("shard", help="run a contiguous block of replications in every cell")
    shard_parser.add_argument("--start", type=int, required=True)
    shard_parser.add_argument("--count", type=int, required=True)
    shard_parser.add_argument("--output", type=Path, required=True)
    shard_parser.add_argument("--n", type=int, default=300)
    shard_parser.add_argument("--delta", type=float, default=.05)
    shard_parser.add_argument("--seed", type=int, default=20260806)
    shard_parser.add_argument("--workers", type=int)
    shard_parser.add_argument("--calibration-registry", type=Path)
    shard_parser.set_defaults(func=shard)
    summarize_parser = commands.add_parser("summarize", help="assemble shards into evidence")
    summarize_parser.add_argument("--shards", type=Path, required=True)
    summarize_parser.add_argument("--output", type=Path, required=True)
    summarize_parser.set_defaults(func=summarize)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
