"""Population diagnostic: does requiring k separators to agree remove the suppression?

Standalone and self-contained -- deliberately not added to `simulations/`, because it tests a
policy the package does not implement and is not on a path to implementing.

No new simulation is run. Each graph is rebuilt from the `replicate` seed recorded in the
comparator gate's own results, and everything below is exact oracle `Theta` for the
`linear_gaussian` family: no sampling, no estimator, no test. Every rate is therefore a
*ceiling* describing infinite data. The finite-sample rule must also clear the calibrated
equivalence test, which is strictly more conservative, so real rates fall on both sides.

The candidate pool is the empty set plus each of the other 13 variables. That is not a
widened search: `benchmark_project_spec` sets `max_neighbors = p - 1`, so this is exactly the
pool the gate itself ranked over.

Writes three CSVs beside this file.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from renca.benchmark.dgp import (
    node_names,
    oracle_edge_theta,
    population_covariance,
    practical_nonedge_pairs,
    sample_graph,
)

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parents[1] / "phase1" / "comparator-gate" / "comparator_gate_results.parquet"
DELTAS = [0.05, 0.10, 0.20]
KS = [1, 2, 3, 5]
P = 15
STRENGTH_BUCKETS = [(0.0, 0.20), (0.20, 0.30), (0.30, 0.40), (0.40, 0.60), (0.60, float("inf"))]


def conditional_variance(covariance: np.ndarray, target: int, conditioning: list[int]) -> float:
    if not conditioning:
        return float(covariance[target, target])
    block = covariance[np.ix_(conditioning, conditioning)]
    cross = covariance[target, conditioning]
    return float(covariance[target, target] - cross @ np.linalg.solve(block, cross))


def ranked_candidates(covariance: np.ndarray, i: int, j: int) -> list[tuple[float, float, tuple[int, ...]]]:
    """(bidirectional gain, worse direction, S), ordered as specification section 15.4 orders them."""
    scored = []
    for separator in [()] + [(other,) for other in range(P) if other not in (i, j)]:
        columns = list(separator)
        theta_i = (conditional_variance(covariance, i, columns) - conditional_variance(covariance, i, columns + [j])) / covariance[i, i]
        theta_j = (conditional_variance(covariance, j, columns) - conditional_variance(covariance, j, columns + [i])) / covariance[j, j]
        scored.append((theta_i + theta_j, max(theta_i, theta_j), separator))
    # Section 15.4 ranks by *minimising* the bidirectional gain; the tuple breaks ties determinstically.
    scored.sort(key=lambda item: (item[0], item[2]))
    return scored


def strength_label(theta: float) -> str:
    low, high = next(bounds for bounds in STRENGTH_BUCKETS if bounds[0] <= theta < bounds[1])
    return f">{low:.2f}" if high == float("inf") else f"{low:.2f}-{high:.2f}"


def replicate_keys(results: pd.DataFrame) -> list[tuple[str, int]]:
    linear = results[results.family == "linear_gaussian"]
    return sorted({(row.edge_strength, int(row.replicate)) for row in linear.itertuples()})


def main() -> None:
    results = pd.read_parquet(RESULTS)
    keys = replicate_keys(results)
    print(f"linear_gaussian replicates rebuilt from recorded seeds: {len(keys)}")

    agreement: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_pair: list[dict[str, object]] = []
    by_strength: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    names = node_names(P)

    for position, (edge_strength, seed) in enumerate(keys, start=1):
        graph = sample_graph(p=P, seed=seed, family="linear_gaussian", edge_strength=edge_strength)
        covariance = population_covariance(graph)
        index = {name: place for place, name in enumerate(names)}
        edge_theta = oracle_edge_theta(graph)
        practical = {delta: practical_nonedge_pairs(graph, delta, edge_theta=edge_theta) for delta in DELTAS}
        ranked = {(i, j): ranked_candidates(covariance, i, j) for i, j in itertools.combinations(range(P), 2)}

        for delta in DELTAS:
            absent = practical[delta]
            familywise = dict.fromkeys(KS, False)
            for (i, j), candidates in ranked.items():
                separates = [worse <= delta for _, worse, _ in candidates]
                practically_absent = frozenset((names[i], names[j])) in absent
                per_pair.append({
                    "edge_strength": edge_strength, "delta": delta, "replicate": seed,
                    "practically_absent": practically_absent,
                    "n_separating": int(sum(separates)), "n_candidates": len(separates),
                })
                for k in KS:
                    bucket = agreement[(edge_strength, delta, k)]
                    bucket["absent" if practically_absent else "present"] += 1
                    if all(separates[:k]):
                        bucket["true_prune" if practically_absent else "false_prune"] += 1
                        familywise[k] = familywise[k] or not practically_absent
            for k in KS:
                agreement[(edge_strength, delta, k)]["replications"] += 1
                agreement[(edge_strength, delta, k)]["familywise"] += int(familywise[k])

        # The strength cut answers a narrower question -- whether agreement protects the
        # edges the failure destroyed -- and is reported only for the gate's worst cell.
        if edge_strength == "strong":
            strongest = (
                edge_theta.assign(pair=[frozenset((row.target, row.added)) for row in edge_theta.itertuples()])
                .groupby("pair").theta.max()
            )
            for pair, true_theta in strongest.items():
                i, j = sorted(index[name] for name in pair)
                separates = [worse <= 0.20 for _, worse, _ in ranked[(i, j)]]
                row = by_strength[strength_label(float(true_theta))]
                row["edges"] += 1
                row["theta_sum"] += float(true_theta)
                for k in KS:
                    row[f"k{k}"] += int(all(separates[:k]))
        if position % 50 == 0:
            print(f"  {position}/{len(keys)}")

    pd.set_option("display.width", 200)
    fmt = lambda value: f"{value:.3f}"  # noqa: E731

    agreement_frame = pd.DataFrame([
        {
            "edge_strength": edge_strength, "delta": delta, "k": k,
            "true_prune_rate": bucket["true_prune"] / bucket["absent"],
            "false_prune_rate": bucket["false_prune"] / bucket["present"],
            "familywise_rate": bucket["familywise"] / bucket["replications"],
            "practical_present": bucket["present"], "practical_absent": bucket["absent"],
        }
        for (edge_strength, delta, k), bucket in sorted(agreement.items())
    ])
    print("\nagreement over the top k candidates (population ceiling)")
    print(agreement_frame.to_string(index=False, float_format=fmt))

    counts_frame = pd.DataFrame(per_pair).groupby(["edge_strength", "delta", "practically_absent"]).agg(
        pairs=("n_separating", "size"),
        mean_separating=("n_separating", "mean"),
        share_ge_1=("n_separating", lambda column: float((column >= 1).mean())),
        share_ge_3=("n_separating", lambda column: float((column >= 3).mean())),
        share_ge_5=("n_separating", lambda column: float((column >= 5).mean())),
    ).reset_index()
    print("\nhow many of the 14 candidate sets separate each pair")
    print(counts_frame.to_string(index=False, float_format=fmt))

    order = {strength_label(low): place for place, (low, _) in enumerate(STRENGTH_BUCKETS)}
    strength_frame = pd.DataFrame([
        {
            "true_strength": label, "edges": int(row["edges"]),
            "mean_true_theta": row["theta_sum"] / row["edges"],
            **{f"declared_nonedge_k{k}": row[f"k{k}"] / row["edges"] for k in KS},
        }
        for label, row in sorted(by_strength.items(), key=lambda item: order[item[0]])
    ])
    print("\nstrong / delta=0.20: share of real edges declared a nonedge, by true strength")
    print(strength_frame.to_string(index=False, float_format=fmt))

    agreement_frame.to_csv(HERE / "policy3_agreement.csv", index=False)
    counts_frame.to_csv(HERE / "policy3_separating_counts.csv", index=False)
    strength_frame.to_csv(HERE / "policy3_by_strength.csv", index=False)


if __name__ == "__main__":
    main()
