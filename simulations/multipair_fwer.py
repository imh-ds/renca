"""Deterministic shard and aggregation commands for the multi-pair FWER study.

Mirrors `simulations/phase0_calibration.py`: independent seeded shards write Parquet,
and a summarize step assembles them into an auditable evidence directory. The study
answers specification section 44 falsification criterion 1 -- familywise false pruning --
which the single-pair Phase-0 profile does not establish.
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from renca.calibration.multipair import run_multipair_replication, summarize_multipair_grid
from renca.calibration.registry import CalibrationRegistry
from renca.models import VimpSpec
from renca.runner import default_calibration_registry_path

PROFILE_ID = "v3-nested-blend-n300-d005-phase0"

_WORKER: dict[str, object] = {}


def _spec() -> VimpSpec:
    """The exact learner configuration fingerprinted by the validated profile."""
    return VimpSpec(forest_trees=10, learner_library_version="v3_nested_blend")


def replicate_seed(seed: int, replicate: int) -> int:
    """Seed a replication from its index alone, so results never depend on scheduling."""
    return int(np.random.SeedSequence([seed, replicate]).generate_state(1)[0])


def _initialize_worker(registry_path: str, blocks: int, sample_size: int, delta: float, alpha: float) -> None:
    _WORKER.update(registry=CalibrationRegistry.load(registry_path), registry_path=registry_path, blocks=blocks, sample_size=sample_size, delta=delta, alpha=alpha, vimp_spec=_spec())


def _run_replication(item: tuple[int, int]) -> dict[str, object]:
    replicate, seed = item
    result = run_multipair_replication(
        blocks=_WORKER["blocks"],
        sample_size=_WORKER["sample_size"],
        seed=seed,
        delta=_WORKER["delta"],
        vimp_spec=_WORKER["vimp_spec"],
        registry=_WORKER["registry"],
        registry_path=_WORKER["registry_path"],
        profile_id=PROFILE_ID,
        alpha=_WORKER["alpha"],
    )
    return {**result, "replicate": replicate, "seed": seed}


def shard(args: argparse.Namespace) -> None:
    """Run a contiguous block of replications, fanning out across the runner's cores.

    Each replication is seeded from its index, so worker count changes throughput but never
    results. Rows are sorted by replicate before writing to keep shard output byte-stable.
    """
    registry_path = str(args.calibration_registry or default_calibration_registry_path())
    items = [(args.start + offset, replicate_seed(args.seed, args.start + offset)) for offset in range(args.count)]
    workers = args.workers if args.workers else (os.cpu_count() or 1)
    initializer_args = (registry_path, args.blocks, args.sample_size, args.delta, args.alpha)
    # One BLAS/OpenMP thread per worker; the learners are tiny, so oversubscribed threads
    # cost far more than they return. Set before forking so workers inherit it.
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[variable] = "1"
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers, initializer=_initialize_worker, initargs=initializer_args) as pool:
            rows = list(pool.map(_run_replication, items, chunksize=1))
    else:
        _initialize_worker(*initializer_args)
        rows = [_run_replication(item) for item in items]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(sorted(rows, key=lambda row: row["replicate"])).to_parquet(args.output, index=False)


def summarize(args: argparse.Namespace) -> None:
    frames = [pd.read_parquet(path) for path in sorted(Path(args.shards).glob("*.parquet"))]
    if not frames:
        raise ValueError(f"no shard Parquet files found in {args.shards}")
    data = pd.concat(frames, ignore_index=True)
    if data.replicate.duplicated().any():
        raise ValueError("replicates must be unique across shards")
    summary = summarize_multipair_grid(data, alpha=args.alpha)
    summary["profile_id"] = PROFILE_ID
    summary["blocks"] = int(data.blocks.iloc[0])
    summary["sample_size"] = args.sample_size
    args.output.mkdir(parents=True, exist_ok=True)
    data.sort_values("replicate").to_parquet(args.output / "multipair_fwer_results.parquet", index=False)
    (args.output / "multipair_fwer_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    shard_parser = commands.add_parser("shard", help="run a contiguous block of replications")
    shard_parser.add_argument("--start", type=int, required=True)
    shard_parser.add_argument("--count", type=int, required=True)
    shard_parser.add_argument("--output", type=Path, required=True)
    shard_parser.add_argument("--blocks", type=int, default=2)
    shard_parser.add_argument("--sample-size", type=int, default=375)
    shard_parser.add_argument("--delta", type=float, default=.05)
    shard_parser.add_argument("--alpha", type=float, default=.05)
    shard_parser.add_argument("--seed", type=int, default=20260804)
    shard_parser.add_argument("--workers", type=int, help="parallel replications; defaults to the core count")
    shard_parser.add_argument("--calibration-registry", type=Path)
    shard_parser.set_defaults(func=shard)

    summarize_parser = commands.add_parser("summarize", help="assemble shards into evidence")
    summarize_parser.add_argument("--shards", type=Path, required=True)
    summarize_parser.add_argument("--output", type=Path, required=True)
    summarize_parser.add_argument("--alpha", type=float, default=.05)
    summarize_parser.add_argument("--sample-size", type=int, default=375)
    summarize_parser.set_defaults(func=summarize)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
