"""Kill-test: does universal separator agreement retain any power at n = 375?

The small-network feasibility study established that requiring *every* candidate conditioning
set to separate a pair removes the population failure the comparator gate exposed, and that
its correct-pruning ceiling on small networks runs 0.53-0.92 in the `realistic` regime. Those
are population ceilings. This probe asks the only question that matters next: how much of that
survives a real sample.

**This is a kill-test, not a certification study, and nothing here is calibrated.** Under the
universal rule a pair's verdict is the maximum of `2(p-1)` dependent one-sided tests -- 6 at
`p=4`, 10 at `p=6` -- against the maximum of 2 the packaged profiles were validated for. No
existing profile transfers, and none is applied. Two deliberately unvalidated decision rules
are reported instead, chosen to bracket the truth from opposite sides:

`normal_holm`
    One-sided p from the normal approximation, `Phi((theta - delta) / se)`, per direction; the
    pair takes the maximum across all `2(p-1)` tests; Holm across pairs. Correct about
    multiplicity, **optimistic about the test** -- Phase 0 found the calibrated critical value
    at these sample sizes is near -3 to -4.8 rather than the normal -1.645, so this certifies
    far more readily than any real calibration would.

`critical_raw`
    Every one of the `2(p-1)` statistics must clear the shipped delta-matched critical value,
    with no multiplicity adjustment. Conservative about the test, **optimistic about
    multiplicity**. The critical value is read from the registry only as a plausible scale for
    that conservatism; this is not an application of the profile and carries no guarantee.

If power is already dead under `normal_holm`, it is dead: a real calibration is strictly more
conservative than the normal approximation, so no Phase-0 run can rescue it. That is the whole
point of running the optimistic rule first -- a negative result here closes the direction
without paying for a calibration.

The `strong` edge regime is excluded: its population ceiling is 0.12-0.47 correct pruning, so
finite-sample evidence cannot change its verdict.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests
from threadpoolctl import threadpool_limits

from renca.benchmark.compare import DELTA_PROFILES, benchmark_project_spec
from renca.benchmark.dgp import generate_sample, oracle_edge_theta, practical_nonedge_pairs, sample_graph
from renca.calibration.registry import CalibrationRegistry
from renca.models import VimpSpec
from renca.runner import default_calibration_registry_path
from renca.screening import create_outer_split
from renca.vimp import fit_crossfitted_vimp

SAMPLE_SIZE = 375
EDGE_STRENGTH = "realistic"
DELTAS = [0.05, 0.10, 0.20]
RULES = ("normal_holm", "critical_raw")

# Matching the small-network Phase A study: a graph with no nonedges cannot measure correct
# pruning and one with no real edges cannot measure wrongful pruning.
MIN_EDGES = 2
MIN_NONEDGES = 2
MAX_REJECTIONS = 500

_WORKER: dict[str, object] = {}


def replicate_seed(seed: int, replicate: int) -> int:
    """Seed a replication from its index alone, so results never depend on scheduling."""
    return int(np.random.SeedSequence([seed, replicate]).generate_state(1)[0])


def admissible_graph(p: int, family: str, seed: int):
    for attempt in range(MAX_REJECTIONS):
        graph = sample_graph(p=p, seed=int(np.random.SeedSequence([seed, attempt]).generate_state(1)[0]), family=family, edge_strength=EDGE_STRENGTH)
        edges = len(graph.adjacent_pairs())
        if edges >= MIN_EDGES and (p * (p - 1) // 2) - edges >= MIN_NONEDGES:
            return graph
    raise RuntimeError(f"no admissible graph for p={p}, {family}, seed {seed}")


def run_replication(*, seed: int, p: int, family: str, vimp_spec: VimpSpec, critical_values: dict[float, float], alpha: float) -> list[dict[str, object]]:
    """Fit every candidate for every pair, then score both decision rules at every delta."""
    graph = admissible_graph(p, family, seed)
    data = generate_sample(graph, n=SAMPLE_SIZE, seed=int(np.random.SeedSequence([seed, 7]).generate_state(1)[0]))
    template = benchmark_project_spec(
        p=p, delta=DELTAS[0], seed=seed, vimp_spec=vimp_spec, profile_id=None,
        max_separator_size=1, selection_fraction=.2, inference_folds=5,
    )
    split = create_outer_split(data, template)
    nodes = {node.node_id: node for node in template.nodes}
    names = graph.names

    # The universal rule: every candidate conditioning set, in both directions, with no
    # ranking and no selection. `rank_separators` is deliberately not called.
    fitted: dict[frozenset[str], list[tuple[object, object]]] = {}
    for i, j in itertools.combinations(range(p), 2):
        first, second = names[i], names[j]
        candidates = [[]] + [[names[other]] for other in range(p) if other not in (i, j)]
        fitted[frozenset((first, second))] = [
            (
                fit_crossfitted_vimp(data, first, second, separator, nodes[first], split, vimp_spec),
                fit_crossfitted_vimp(data, second, first, separator, nodes[second], split, vimp_spec),
            )
            for separator in candidates
        ]

    edge_theta = oracle_edge_theta(graph)
    rows: list[dict[str, object]] = []
    for delta in DELTAS:
        absent = practical_nonedge_pairs(graph, delta, edge_theta=edge_theta)
        statistics: dict[frozenset[str], list[float]] = {}
        adjacency: dict[frozenset[str], bool] = {}
        usable: dict[frozenset[str], bool] = {}
        for pair, directions in fitted.items():
            values: list[float] = []
            everywhere_adjacent = True
            complete = True
            for forward, reverse in directions:
                for estimate in (forward, reverse):
                    if estimate.status != "success" or estimate.theta_hat is None or estimate.se_theta is None or estimate.se_theta <= 0:
                        complete = False
                        continue
                    values.append((estimate.theta_hat - delta) / estimate.se_theta)
                    # Mirrors `certify_pairs`: adjacency evidence needs the lower bound of
                    # *both* directions above delta, for every candidate.
                    if estimate.lower_ci is None or estimate.lower_ci <= delta:
                        everywhere_adjacent = False
            statistics[pair] = values
            adjacency[pair] = everywhere_adjacent and complete
            usable[pair] = complete

        for rule in RULES:
            if rule == "normal_holm":
                raw = {pair: float(norm.cdf(max(values))) for pair, values in statistics.items() if usable[pair] and values}
                order = sorted(raw)
                adjusted = multipletests([raw[pair] for pair in order], alpha=alpha, method="holm")[1] if order else []
                certified = {pair for pair, value in zip(order, adjusted) if value <= alpha}
            else:
                threshold = critical_values[delta]
                certified = {pair for pair, values in statistics.items() if usable[pair] and values and max(values) <= threshold}

            present = graph.all_pairs() - absent
            false_prunes = certified & present
            unresolved = sum(1 for pair in fitted if pair not in certified and not adjacency[pair])
            rows.append({
                "replicate": seed, "p": p, "family": family, "edge_strength": EDGE_STRENGTH,
                "n": SAMPLE_SIZE, "delta": delta, "rule": rule,
                "edges": len(graph.adjacent_pairs()), "pairs": len(graph.all_pairs()),
                "checks_per_pair": p - 1, "directional_tests_per_pair": 2 * (p - 1),
                "correct_prunes": len(certified & absent), "wrongful_prunes": len(false_prunes),
                "practical_absent": len(absent), "practical_present": len(present),
                "wrongful_anywhere": int(bool(false_prunes)),
                "candidate_adjacency": sum(1 for pair in fitted if adjacency[pair] and pair not in certified),
                "unresolved": unresolved,
                "unusable_pairs": sum(1 for pair in fitted if not usable[pair]),
            })
    return rows


def _initialize_worker(p: int, family: str, version: str, forest_trees: int, alpha: float, critical_values: dict[float, float]) -> None:
    _WORKER.update(p=p, family=family, alpha=alpha, critical_values=critical_values, vimp_spec=VimpSpec(forest_trees=forest_trees, learner_library_version=version))


def _run(item: tuple[int, int]) -> list[dict[str, object]]:
    replicate, seed = item
    with threadpool_limits(limits=1):
        rows = run_replication(seed=seed, p=_WORKER["p"], family=_WORKER["family"], vimp_spec=_WORKER["vimp_spec"], critical_values=_WORKER["critical_values"], alpha=_WORKER["alpha"])
    return [{**row, "replicate_index": replicate} for row in rows]


def registry_critical_values(registry_path: str | Path) -> dict[float, float]:
    """Delta-matched critical values, read only as a scale for the conservatism bracket."""
    registry = CalibrationRegistry.load(registry_path)
    records = {record.profile_id: record for record in registry.records}
    return {delta: float(records[DELTA_PROFILES[delta]].critical_value) for delta in DELTAS}


def shard(args: argparse.Namespace) -> None:
    critical_values = registry_critical_values(args.calibration_registry or default_calibration_registry_path())
    items = [(args.start + offset, replicate_seed(args.seed, args.start + offset)) for offset in range(args.count)]
    workers = args.workers if args.workers else (os.cpu_count() or 1)
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[variable] = "1"
    initializer_args = (args.p, args.family, args.learner_library_version, args.forest_trees, args.alpha, critical_values)
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers, initializer=_initialize_worker, initargs=initializer_args) as pool:
            batches = list(pool.map(_run, items, chunksize=1))
    else:
        _initialize_worker(*initializer_args)
        batches = [_run(item) for item in items]
    frame = pd.DataFrame([row for batch in batches for row in batch]).sort_values(["replicate_index", "delta", "rule"], ignore_index=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)


def summarize_probe(results: pd.DataFrame) -> pd.DataFrame:
    grouped = results.groupby(["p", "family", "delta", "rule"], dropna=False)
    summary = grouped.agg(
        replications=("replicate", "nunique"),
        correct_prunes=("correct_prunes", "sum"),
        wrongful_prunes=("wrongful_prunes", "sum"),
        practical_absent=("practical_absent", "sum"),
        practical_present=("practical_present", "sum"),
        unresolved=("unresolved", "sum"),
        pairs=("pairs", "sum"),
        familywise=("wrongful_anywhere", "sum"),
        unusable=("unusable_pairs", "sum"),
        directional_tests_per_pair=("directional_tests_per_pair", "max"),
    ).reset_index()
    summary["correct_prune_rate"] = summary.correct_prunes / summary.practical_absent
    summary["wrongful_prune_rate"] = summary.wrongful_prunes / summary.practical_present
    summary["familywise_wrongful_rate"] = summary.familywise / summary.replications
    summary["unresolved_rate"] = summary.unresolved / summary.pairs
    return summary.sort_values(["rule", "family", "delta", "p"], ignore_index=True)


def summarize(args: argparse.Namespace) -> None:
    frames = [pd.read_parquet(path) for path in sorted(Path(args.shards).glob("*.parquet"))]
    if not frames:
        raise ValueError(f"no shard Parquet files found in {args.shards}")
    data = pd.concat(frames, ignore_index=True)
    key = ["p", "family", "replicate", "delta", "rule"]
    if int(data.duplicated(subset=key).sum()):
        raise ValueError(f"{int(data.duplicated(subset=key).sum())} duplicate ({', '.join(key)}) rows across shards")
    summary = summarize_probe(data)

    args.output.mkdir(parents=True, exist_ok=True)
    data.sort_values(key).to_parquet(args.output / "unanimity_power_results.parquet", index=False)
    summary.to_csv(args.output / "unanimity_power_summary.csv", index=False)
    columns = ["rule", "family", "delta", "p", "directional_tests_per_pair", "correct_prune_rate", "wrongful_prune_rate", "familywise_wrongful_rate", "unresolved_rate", "replications"]
    print(summary[columns].to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    optimistic = summary[summary.rule == "normal_holm"]
    verdict = {
        "best_correct_prune_rate_under_the_optimistic_rule": round(float(optimistic.correct_prune_rate.max()), 4),
        "worst_wrongful_prune_rate_under_the_optimistic_rule": round(float(optimistic.wrongful_prune_rate.max()), 4),
        "reading": "A real calibration is strictly more conservative than the normal approximation, so the optimistic column is an upper bound on achievable power. Nothing here is calibrated.",
    }
    (args.output / "unanimity_power_verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print()
    print(json.dumps(verdict, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    shard_parser = commands.add_parser("shard", help="run a contiguous block of replications")
    shard_parser.add_argument("--start", type=int, required=True)
    shard_parser.add_argument("--count", type=int, required=True)
    shard_parser.add_argument("--output", type=Path, required=True)
    shard_parser.add_argument("--p", type=int, required=True)
    shard_parser.add_argument("--family", default="linear_gaussian")
    shard_parser.add_argument("--alpha", type=float, default=.05)
    shard_parser.add_argument("--seed", type=int, default=20260809)
    shard_parser.add_argument("--workers", type=int, help="parallel replications; defaults to the core count")
    shard_parser.add_argument("--calibration-registry", type=Path)
    shard_parser.add_argument("--learner-library-version", default="v4_cubic_blend")
    shard_parser.add_argument("--forest-trees", type=int, default=10, help="matches the comparator gate's benchmark setting")
    shard_parser.set_defaults(func=shard)

    summarize_parser = commands.add_parser("summarize", help="assemble shards into evidence")
    summarize_parser.add_argument("--shards", type=Path, required=True)
    summarize_parser.add_argument("--output", type=Path, required=True)
    summarize_parser.set_defaults(func=summarize)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
