"""Phase A: does the universal-agreement rule hold up on small networks?

The p=15 feasibility sweep is not representative of the intended use, which is small
psychological networks. This runs the same rule at p = 4 .. 10.

**Universal rule only.** For each pair, every candidate conditioning set is checked -- the
empty set plus each of the other p-2 variables, so `p - 1` checks per pair. There is no
ranking and no top-k: the section 15.4 selection step does not exist here.

Oracle only. `linear_gaussian` uses the exact population covariance. `additive_nonlinear` has
no closed form, so its population values come from one large auxiliary sample per graph
(`MONTE_CARLO_ROWS`) with a degree-3 polynomial basis, which contains every edge transform the
generator produces. Both are population quantities; neither is a finite-sample estimate. The
`--validate` mode quantifies the Monte Carlo error by running it on `linear_gaussian` graphs,
where the exact answer is also available.

Rates are therefore ceilings describing infinite data. A finite-sample rule must also clear a
calibrated test, which is strictly more conservative. **No existing calibration transfers.**

Three states, mirroring `certify_pairs`, which needs both directions to agree before it
returns any verdict. For one candidate S, `separating` means `max(theta_i, theta_j) <= delta`
and `adjacency evidence` means `min(theta_i, theta_j) > delta`. A pair is a certified nonedge
when *every* candidate is separating, a candidate adjacency when *every* candidate carries
adjacency evidence, and unresolved otherwise.
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import cho_factor, cho_solve
from sklearn.preprocessing import PolynomialFeatures
from threadpoolctl import threadpool_limits

from renca.benchmark.dgp import (
    BenchmarkGraph,
    generate_sample,
    population_covariance,
    sample_graph,
)

HERE = Path(__file__).resolve().parent
SEED_ROOT = 20260809
P_VALUES = [4, 5, 6, 7, 8, 9, 10]
FAMILIES = ["linear_gaussian", "additive_nonlinear"]
STRENGTHS = ["realistic", "strong"]
DELTAS = [0.05, 0.10, 0.20]
REPLICATIONS = 200
MONTE_CARLO_ROWS = 400_000
POLYNOMIAL_DEGREE = 3

# A graph with no nonedges cannot measure correct pruning and a graph with no edges cannot
# measure wrongful pruning. At p=4 the degree cap alone permits a complete graph, so the
# constraint has to be enforced by rejection rather than assumed.
MIN_EDGES = 2
MIN_NONEDGES = 2
MAX_REJECTIONS = 500

STRONG_THRESHOLDS = {"040": 0.40, "060": 0.60}


class ExactRisk:
    """Population risk for the linear Gaussian family, in closed form."""

    def __init__(self, graph: BenchmarkGraph) -> None:
        self.covariance = population_covariance(graph)

    def risk(self, target: int, features: tuple[int, ...]) -> float:
        if not features:
            return float(self.covariance[target, target])
        conditioning = list(features)
        block = self.covariance[np.ix_(conditioning, conditioning)]
        cross = self.covariance[target, conditioning]
        return float(self.covariance[target, target] - cross @ np.linalg.solve(block, cross))


class SampleRisk:
    """Large-sample population risk for families with no closed form.

    One auxiliary sample per graph, then every risk is a least-squares fit on a subset of its
    columns. Two things make that affordable, and both matter at this scale.

    The work is organised **by conditioning set rather than by target**. The polynomial design
    for a given set of columns does not depend on which variable is being predicted, so it is
    built once and reused for every target that conditions on it -- otherwise it is rebuilt `p`
    times over. Designs are discarded as soon as their group is finished, which keeps peak
    memory to one design instead of all of them.

    Each fit solves the **normal equations** through a Cholesky factor of the Gram matrix
    rather than an SVD. The polynomial bases here are small and well conditioned, so the two
    agree to floating-point noise, and `validate` measures that against the exact answer. A
    faint ridge guards the factorisation, since a degree-3 basis in two variables can become
    near-collinear on a bounded sample.
    """

    def __init__(self, graph: BenchmarkGraph, *, rows: int, seed: int) -> None:
        self.values = generate_sample(graph, n=rows, seed=seed).to_numpy()
        self.cache: dict[tuple[int, tuple[int, ...]], float] = {}

    def prepare(self, requests: set[tuple[int, tuple[int, ...]]]) -> None:
        """Resolve every risk the sweep will ask for, one conditioning set at a time."""
        by_features: dict[tuple[int, ...], list[int]] = defaultdict(list)
        for target, features in requests:
            by_features[tuple(sorted(features))].append(target)
        for features, targets in by_features.items():
            if not features:
                for target in targets:
                    self.cache[(target, ())] = float(np.var(self.values[:, target]))
                continue
            design = PolynomialFeatures(degree=POLYNOMIAL_DEGREE, include_bias=True).fit_transform(self.values[:, list(features)])
            gram = design.T @ design
            gram[np.diag_indices_from(gram)] += 1e-9 * float(np.trace(gram)) / gram.shape[0]
            try:
                factor = cho_factor(gram)
                solve = lambda vector: cho_solve(factor, vector)  # noqa: E731
            except np.linalg.LinAlgError:  # pragma: no cover - guarded, not expected
                solve = lambda vector: np.linalg.lstsq(gram, vector, rcond=None)[0]  # noqa: E731
            for target in targets:
                outcome = self.values[:, target]
                residual = outcome - design @ solve(design.T @ outcome)
                self.cache[(target, features)] = float(np.mean(residual**2))

    def risk(self, target: int, features: tuple[int, ...]) -> float:
        key = (target, tuple(sorted(features)))
        if key not in self.cache:  # `prepare` covers the sweep; this is the validation path
            self.prepare({key})
        return self.cache[key]


def theta(oracle: ExactRisk | SampleRisk, target: int, added: int, separator: tuple[int, ...]) -> float:
    reduced = oracle.risk(target, separator)
    expanded = oracle.risk(target, tuple(separator) + (added,))
    return (reduced - expanded) / oracle.risk(target, ())


def graph_for(p: int, family: str, edge_strength: str, replicate: int) -> tuple[BenchmarkGraph, int]:
    """Draw a graph that can actually measure both error types, seeded by identity."""
    for attempt in range(MAX_REJECTIONS):
        entropy = [SEED_ROOT, p, FAMILIES.index(family), STRENGTHS.index(edge_strength), replicate, attempt]
        seed = int(np.random.SeedSequence(entropy).generate_state(1)[0])
        graph = sample_graph(p=p, seed=seed, family=family, edge_strength=edge_strength)
        edges = len(graph.adjacent_pairs())
        if edges >= MIN_EDGES and (p * (p - 1) // 2) - edges >= MIN_NONEDGES:
            return graph, attempt
    raise RuntimeError(f"no admissible graph for p={p}, {family}, {edge_strength}, replicate {replicate}")


def required_risks(graph: BenchmarkGraph) -> set[tuple[int, tuple[int, ...]]]:
    """Every (target, conditioning set) the sweep will ask for, enumerated up front.

    Knowing the whole set in advance is what lets the sample oracle group its work by
    conditioning set instead of rebuilding the same design once per target.
    """
    requests: set[tuple[int, tuple[int, ...]]] = {(target, ()) for target in range(graph.p)}
    for child, group in enumerate(graph.parents):
        for parent in group:
            for target, added in ((child, parent), (parent, child)):
                separator = tuple(sorted(set(graph.parents[target]) - {added}))
                requests.add((target, separator))
                requests.add((target, tuple(sorted(separator + (added,)))))
    for i, j in itertools.combinations(range(graph.p), 2):
        for separator in [()] + [(other,) for other in range(graph.p) if other not in (i, j)]:
            for target, added in ((i, j), (j, i)):
                requests.add((target, separator))
                requests.add((target, tuple(sorted(separator + (added,)))))
    return requests


def edge_strength_given_parents(graph: BenchmarkGraph, oracle: ExactRisk | SampleRisk) -> dict[frozenset[str], float]:
    """Each real edge's true Theta given its target's own parents, worse direction kept."""
    names = graph.names
    strength: dict[frozenset[str], float] = {}
    for child, group in enumerate(graph.parents):
        for parent in group:
            values = []
            for target, added in ((child, parent), (parent, child)):
                separator = tuple(sorted(set(graph.parents[target]) - {added}))
                values.append(theta(oracle, target, added, separator))
            strength[frozenset((names[child], names[parent]))] = max(values)
    return strength


def evaluate(p: int, family: str, edge_strength: str, replicate: int) -> list[dict[str, object]]:
    started = time.perf_counter()
    graph, rejections = graph_for(p, family, edge_strength, replicate)
    if family == "linear_gaussian":
        oracle: ExactRisk | SampleRisk = ExactRisk(graph)
    else:
        oracle = SampleRisk(graph, rows=MONTE_CARLO_ROWS, seed=int(np.random.SeedSequence([SEED_ROOT, p, replicate, 7]).generate_state(1)[0]))
        oracle.prepare(required_risks(graph))

    names = graph.names
    adjacent = graph.adjacent_pairs()
    strength = edge_strength_given_parents(graph, oracle)

    # Every candidate for every pair: the empty set plus each remaining single variable.
    worse: dict[tuple[int, int], list[float]] = {}
    better: dict[tuple[int, int], list[float]] = {}
    for i, j in itertools.combinations(range(p), 2):
        pair_worse, pair_better = [], []
        for separator in [()] + [(other,) for other in range(p) if other not in (i, j)]:
            theta_i = theta(oracle, i, j, separator)
            theta_j = theta(oracle, j, i, separator)
            pair_worse.append(max(theta_i, theta_j))
            pair_better.append(min(theta_i, theta_j))
        worse[(i, j)] = pair_worse
        better[(i, j)] = pair_better

    elapsed = time.perf_counter() - started
    rows = []
    for delta in DELTAS:
        absent = {pair for pair in graph.nonadjacent_pairs()} | {pair for pair, value in strength.items() if value <= delta}
        counts: dict[str, int] = defaultdict(int)
        wrongful_anywhere = False
        for (i, j), pair_worse in worse.items():
            pair = frozenset((names[i], names[j]))
            practically_absent = pair in absent
            counts["absent" if practically_absent else "present"] += 1
            for label, threshold in STRONG_THRESHOLDS.items():
                if not practically_absent and strength.get(pair, 0.0) > threshold:
                    counts[f"strong_{label}"] += 1
            if all(value <= delta for value in pair_worse):
                counts["true_prune" if practically_absent else "false_prune"] += 1
                if not practically_absent:
                    wrongful_anywhere = True
                    for label, threshold in STRONG_THRESHOLDS.items():
                        if strength.get(pair, 0.0) > threshold:
                            counts[f"strong_false_prune_{label}"] += 1
            elif all(value > delta for value in better[(i, j)]):
                counts["candidate_adjacency"] += 1
            else:
                counts["unresolved"] += 1
        rows.append({
            "p": p, "family": family, "edge_strength": edge_strength, "delta": delta,
            "replicate": replicate, "edges": len(adjacent), "pairs": p * (p - 1) // 2,
            "checks_per_pair": p - 1, "rejections": rejections, "seconds": elapsed / len(DELTAS),
            "wrongful_anywhere": int(wrongful_anywhere), **counts,
        })
    return rows


def _task(item: tuple[int, str, str, int]) -> list[dict[str, object]]:
    with threadpool_limits(limits=1):
        return evaluate(*item)


def run(workers: int) -> pd.DataFrame:
    """Run the sweep one network size at a time, so progress is visible while it works."""
    total = len(P_VALUES) * len(FAMILIES) * len(STRENGTHS) * REPLICATIONS
    print(f"{total} graphs across {len(P_VALUES)} network sizes, {workers} workers", flush=True)
    started = time.perf_counter()
    rows: list[dict[str, object]] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for p in P_VALUES:
            stage = time.perf_counter()
            items = [
                (p, family, edge_strength, replicate)
                for family in FAMILIES for edge_strength in STRENGTHS for replicate in range(REPLICATIONS)
            ]
            for batch in pool.map(_task, items, chunksize=2):
                rows.extend(batch)
            print(f"  p={p:>2}  {len(items)} graphs in {time.perf_counter() - stage:5.0f}s   (elapsed {time.perf_counter() - started:.0f}s)", flush=True)
    print(f"finished in {time.perf_counter() - started:.0f}s", flush=True)
    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    def rate(frame: pd.DataFrame, numerator: str, denominator: str) -> float:
        total = frame[denominator].sum() if denominator in frame else 0
        if not total:
            return float("nan")
        # A cell can produce the denominator but never the numerator -- no such error occurred.
        return float(frame[numerator].sum() / total) if numerator in frame else 0.0

    rows = []
    for (p, family, edge_strength, delta), group in results.groupby(["p", "family", "edge_strength", "delta"]):
        filled = group.fillna(0)
        rows.append({
            "p": p, "family": family, "edge_strength": edge_strength, "delta": delta,
            "checks_per_pair": p - 1,
            "correct_prune_rate": rate(filled, "true_prune", "absent"),
            "wrongful_prune_rate": rate(filled, "false_prune", "present"),
            "strong_wrongful_prune_rate_040": rate(filled, "strong_false_prune_040", "strong_040"),
            "strong_wrongful_prune_rate_060": rate(filled, "strong_false_prune_060", "strong_060"),
            "familywise_wrongful_rate": float(filled.wrongful_anywhere.mean()),
            "unresolved_rate": rate(filled, "unresolved", "pairs"),
            "candidate_adjacency_rate": rate(filled, "candidate_adjacency", "pairs"),
            "mean_edges": float(filled.edges.mean()),
            "edge_density": float(filled.edges.sum() / filled.pairs.sum()),
            "practical_absent": int(filled.get("absent", pd.Series(dtype=float)).sum()),
            "practical_present": int(filled.get("present", pd.Series(dtype=float)).sum()),
            "strong_present_040": int(filled.get("strong_040", pd.Series(dtype=float)).sum()),
            "strong_present_060": int(filled.get("strong_060", pd.Series(dtype=float)).sum()),
            "replications": int(filled.replicate.nunique()),
            "seconds_per_graph": float(filled.seconds.mean() * len(DELTAS)),
            "mean_rejections": float(filled.rejections.mean()),
        })
    return pd.DataFrame(rows).sort_values(["family", "edge_strength", "delta", "p"], ignore_index=True)


def validate() -> pd.DataFrame:
    """Monte Carlo error, measured where the exact answer is also available."""
    rows = []
    for p in (4, 7, 10):
        for replicate in range(20):
            graph, _ = graph_for(p, "linear_gaussian", "strong", replicate)
            exact = ExactRisk(graph)
            approximate = SampleRisk(graph, rows=MONTE_CARLO_ROWS, seed=int(np.random.SeedSequence([SEED_ROOT, p, replicate, 7]).generate_state(1)[0]))
            for i, j in itertools.combinations(range(p), 2):
                for separator in [()] + [(other,) for other in range(p) if other not in (i, j)]:
                    for target, added in ((i, j), (j, i)):
                        rows.append({
                            "p": p,
                            "exact": theta(exact, target, added, separator),
                            "monte_carlo": theta(approximate, target, added, separator),
                        })
    frame = pd.DataFrame(rows)
    frame["error"] = (frame.monte_carlo - frame.exact).abs()
    return frame.groupby("p").agg(
        comparisons=("error", "size"), mean_absolute_error=("error", "mean"),
        p95_absolute_error=("error", lambda column: float(np.quantile(column, .95))),
        max_absolute_error=("error", "max"),
    ).reset_index()


def draw(summary: pd.DataFrame, destination: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    series = [
        ("correct_prune_rate", "correct pruning (absent pairs)", "#1a7f5a", "-"),
        ("wrongful_prune_rate", "wrongful pruning (real pairs)", "#c2410c", "-"),
        ("strong_wrongful_prune_rate_040", "wrongful pruning (strong real pairs)", "#7c2d12", "--"),
        ("familywise_wrongful_rate", "network with >= 1 wrongful pruning", "#b91c1c", "-"),
        ("unresolved_rate", "unresolved pairs", "#64748b", ":"),
    ]
    panels = [(family, edge_strength) for family in FAMILIES for edge_strength in STRENGTHS]
    canvas, axes = plt.subplots(len(panels), len(DELTAS), figsize=(14, 15), sharex=True, sharey=True)
    for row, (family, edge_strength) in enumerate(panels):
        for column, delta in enumerate(DELTAS):
            axis = axes[row][column]
            cell = summary[(summary.family == family) & (summary.edge_strength == edge_strength) & (summary.delta == delta)].sort_values("p")
            for name, label, colour, style in series:
                axis.plot(cell.p, cell[name], color=colour, linestyle=style, marker="o", markersize=4, linewidth=1.7, label=label)
            axis.axhline(0.05, color="#0f172a", linewidth=1, linestyle="-.", alpha=.55)
            axis.set_title(f"{family}   {edge_strength}   delta = {delta:.2f}", fontsize=10)
            axis.set_ylim(-.03, 1.03)
            axis.set_xticks(P_VALUES)
            axis.grid(alpha=.25, linewidth=.6)
            if row == len(panels) - 1:
                axis.set_xlabel("p  (number of variables)")
            if column == 0:
                axis.set_ylabel("rate")
    handles, labels = axes[0][0].get_legend_handles_labels()
    handles.append(plt.Line2D([], [], color="#0f172a", linestyle="-.", linewidth=1, alpha=.55))
    labels.append("alpha = 0.05")
    canvas.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=10, bbox_to_anchor=(.5, -.01))
    canvas.suptitle(
        "Universal separator agreement on small networks — population ceilings\n"
        f"every candidate checked (p-1 per pair), max_separator_size = 1, {REPLICATIONS} replications per cell; no sampling and no test",
        fontsize=12,
    )
    canvas.tight_layout(rect=(0, .05, 1, .96))
    canvas.savefig(destination, dpi=160, bbox_inches="tight")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=max(1, (__import__("os").cpu_count() or 2) - 2))
    parser.add_argument("--validate-only", action="store_true")
    arguments = parser.parse_args()

    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 300)

    if arguments.validate_only:
        print(validate().to_string(index=False))
        return

    results = run(arguments.workers)
    summary = summarize(results)
    accuracy = validate()

    results.to_parquet(HERE / "small_network_results.parquet", index=False)
    summary.to_csv(HERE / "small_network_summary.csv", index=False)
    accuracy.to_csv(HERE / "monte_carlo_accuracy.csv", index=False)
    draw(summary, HERE / "small_network_sweep.png")

    columns = ["p", "family", "edge_strength", "delta", "checks_per_pair", "correct_prune_rate", "wrongful_prune_rate", "strong_wrongful_prune_rate_040", "familywise_wrongful_rate", "unresolved_rate", "edge_density", "seconds_per_graph"]
    print(summary[columns].to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print("\nMonte Carlo accuracy, measured against the exact answer on linear_gaussian graphs")
    print(accuracy.to_string(index=False))
    print("\n" + json.dumps({
        "graphs": int(len(results) / len(DELTAS)),
        "mean_rejections": round(float(results.rejections.mean()), 3),
        "max_rejections": int(results.rejections.max()),
    }, indent=2))


if __name__ == "__main__":
    main()
