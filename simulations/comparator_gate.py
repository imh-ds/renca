"""Sharded runner for the specification section 13.4 comparative gate.

Mirrors the other studies: independent seeded shards write Parquet, and a summarize step
assembles them into an auditable evidence directory. This one answers section 44
falsification criterion 3 -- whether the method can prune nearly as many true nonedges as
PC/FCI while reducing false prunes -- and produces the explicit GO / REDESIGN / STOP
decision that section 51 requires.
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from renca.benchmark.compare import CALIBRATED_SAMPLE_SIZE, DELTA_PROFILES, run_benchmark_replication, summarize_benchmark
from renca.benchmark.dgp import EDGE_STRENGTHS
from renca.benchmark.verdict import gate_verdict
from renca.calibration.registry import CalibrationRegistry
from renca.models import VimpSpec
from renca.runner import default_calibration_registry_path

# Each baseline's one knob, swept so the comparison is between curves rather than points.
# PC and FCI remove an edge when they fail to reject independence, so a *smaller* level
# prunes more; the sweep therefore runs from aggressive to conservative pruning.
COMPARATOR_SETTINGS: dict[str, list[float]] = {
    "pc": [.001, .005, .01, .05, .10, .20],
    "conservative_pc": [.05],
    "fci": [.001, .005, .01, .05, .10, .20],
    "ges": [.5, 1.0, 2.0, 4.0],
    "ebicglasso": [.0, .25, .5, 1.0],
}
DEFAULT_DELTAS = sorted(DELTA_PROFILES)

_WORKER: dict[str, object] = {}


def replicate_seed(seed: int, replicate: int) -> int:
    """Seed a replication from its index alone, so results never depend on scheduling."""
    return int(np.random.SeedSequence([seed, replicate]).generate_state(1)[0])


def _initialize_worker(registry_path: str, family: str, edge_strength: str, n: int, p: int, deltas: list[float], max_separator_size: int, alpha: float, version: str, indep_test: str, include_renca: bool) -> None:
    _WORKER.update(
        registry=CalibrationRegistry.load(registry_path), registry_path=registry_path, family=family, edge_strength=edge_strength, n=n, p=p,
        deltas=deltas, max_separator_size=max_separator_size, alpha=alpha, indep_test=indep_test,
        include_renca=include_renca, vimp_spec=VimpSpec(forest_trees=10, learner_library_version=version),
    )


def _run_replication(item: tuple[int, int]) -> list[dict[str, object]]:
    replicate, seed = item
    with threadpool_limits(limits=1):
        rows = run_benchmark_replication(
            seed=seed, n=_WORKER["n"], p=_WORKER["p"], family=_WORKER["family"], deltas=_WORKER["deltas"],
            comparator_settings=COMPARATOR_SETTINGS, registry=_WORKER["registry"], registry_path=_WORKER["registry_path"],
            vimp_spec=_WORKER["vimp_spec"], max_separator_size=_WORKER["max_separator_size"], alpha=_WORKER["alpha"],
            indep_test=_WORKER["indep_test"], include_renca=_WORKER["include_renca"], edge_strength=_WORKER["edge_strength"],
        )
    return [{**row, "replicate_index": replicate} for row in rows]


def shard(args: argparse.Namespace) -> None:
    """Run a contiguous block of replications, fanning out across the runner's cores."""
    registry_path = str(args.calibration_registry or default_calibration_registry_path())
    items = [(args.start + offset, replicate_seed(args.seed, args.start + offset)) for offset in range(args.count)]
    workers = args.workers if args.workers else (os.cpu_count() or 1)
    initializer_args = (registry_path, args.family, args.edge_strength, args.n, args.p, DEFAULT_DELTAS, args.max_separator_size, args.alpha, args.learner_library_version, args.indep_test, not args.skip_renca)
    # Pin thread pools: the assembled results are compared across runners, and threaded BLAS
    # reductions reorder floating-point summation.
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[variable] = "1"
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers, initializer=_initialize_worker, initargs=initializer_args) as pool:
            batches = list(pool.map(_run_replication, items, chunksize=1))
    else:
        _initialize_worker(*initializer_args)
        batches = [_run_replication(item) for item in items]
    rows = [row for batch in batches for row in batch]
    frame = pd.DataFrame(rows).sort_values(["replicate_index", "method", "setting"], ignore_index=True)
    frame = frame.assign(max_separator_size=args.max_separator_size, indep_test=args.indep_test)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)


def summarize(args: argparse.Namespace) -> None:
    frames = [pd.read_parquet(path) for path in sorted(Path(args.shards).glob("*.parquet"))]
    if not frames:
        raise ValueError(f"no shard Parquet files found in {args.shards}")
    data = pd.concat(frames, ignore_index=True)
    if failures := int(data.get("failed", pd.Series(dtype=object)).notna().sum()):
        print(f"warning: {failures} baseline invocations failed and are excluded from their arm")
    # A baseline is scored once per reference delta, so that column is part of the key;
    # leaving it out would flag every legitimate comparator row as a duplicate.
    key = ["family", "edge_strength", "n", "replicate", "method", "setting", "reference_delta"]
    duplicated = data.duplicated(subset=key)
    if duplicated.any():
        raise ValueError(f"{int(duplicated.sum())} duplicate ({', '.join(key)}) rows across shards")
    scored = data[data.get("failed", pd.Series([None] * len(data))).isna()] if "failed" in data else data
    summary = summarize_benchmark(scored)
    verdict = gate_verdict(summary, alpha=args.alpha)

    args.output.mkdir(parents=True, exist_ok=True)
    scored.sort_values(["family", "n", "replicate", "method", "setting"]).to_parquet(args.output / "comparator_gate_results.parquet", index=False)
    summary.to_parquet(args.output / "comparator_gate_summary.parquet", index=False)
    summary.to_csv(args.output / "comparator_gate_summary.csv", index=False)
    (args.output / "comparator_gate_verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(summary.to_string(index=False))
    print()
    print(json.dumps(verdict, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    shard_parser = commands.add_parser("shard", help="run a contiguous block of replications")
    shard_parser.add_argument("--start", type=int, required=True)
    shard_parser.add_argument("--count", type=int, required=True)
    shard_parser.add_argument("--output", type=Path, required=True)
    shard_parser.add_argument("--family", default="linear_gaussian")
    shard_parser.add_argument("--edge-strength", default="realistic", choices=sorted(EDGE_STRENGTHS))
    shard_parser.add_argument("--n", type=int, default=CALIBRATED_SAMPLE_SIZE, help="375 keeps inference rows at the 300 the profiles bind to")
    shard_parser.add_argument("--p", type=int, default=15)
    shard_parser.add_argument("--max-separator-size", type=int, default=1)
    shard_parser.add_argument("--alpha", type=float, default=.05)
    shard_parser.add_argument("--seed", type=int, default=20260808)
    shard_parser.add_argument("--workers", type=int, help="parallel replications; defaults to the core count")
    shard_parser.add_argument("--calibration-registry", type=Path)
    shard_parser.add_argument("--learner-library-version", default="v4_cubic_blend")
    shard_parser.add_argument("--indep-test", default="fisherz", help="conditional-independence test for PC and FCI")
    shard_parser.add_argument("--skip-renca", action="store_true", help="baselines only; used to sweep n where no profile binds")
    shard_parser.set_defaults(func=shard)

    summarize_parser = commands.add_parser("summarize", help="assemble shards into evidence and a verdict")
    summarize_parser.add_argument("--shards", type=Path, required=True)
    summarize_parser.add_argument("--output", type=Path, required=True)
    summarize_parser.add_argument("--alpha", type=float, default=.05)
    summarize_parser.set_defaults(func=summarize)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
