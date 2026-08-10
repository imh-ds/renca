"""Feasibility sweep: agreement over the top k separator candidates, k = 1 .. 14.

Oracle only. Each graph is rebuilt from the `replicate` seed already recorded in the
comparator gate's results and every quantity is exact population `Theta` for the
`linear_gaussian` family -- no sampling, no estimator, no test. Rates are therefore ceilings
describing infinite data; a finite-sample rule must also clear a calibrated test, which is
strictly more conservative, so real rates fall on both sides. Levels are not comparable to
the gate's observed rates. Only the movement across `k` is informative.

`k` runs to 14, the whole candidate pool: the empty set plus each of the other 13 variables.
That is the pool the gate itself ranked over (`benchmark_project_spec` sets
`max_neighbors = p - 1`), so `k = 14` is unanimity, not a widened search.

Three states, mirroring `certify_pairs`, which needs *both* directions to agree before it
returns any verdict. For one candidate separator S:

    separating          max(theta_i, theta_j) <= delta
    adjacency evidence  min(theta_i, theta_j) >  delta

and for the rule at a given `k`:

    certified nonedge    all of the top k are separating
    candidate adjacency  all of the top k carry adjacency evidence
    unresolved           anything else

Writes one table and one figure beside this file.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
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
RESULTS = HERE.parent / "comparator-gate" / "comparator_gate_results.parquet"
DELTAS = [0.05, 0.10, 0.20]
P = 15
POOL = P - 1  # the empty set plus each of the other 13 variables
KS = list(range(1, POOL + 1))
# "Strong real pair": true Theta given its own parents, worse direction. Two thresholds,
# because the `realistic` generator puts no edge above 0.60 -- a degree-3 node splitting
# 30-60% of its variance cannot -- so that column would be empty in half the design.
STRONG_THRESHOLDS = {"060": 0.60, "040": 0.40}


def conditional_variance(covariance: np.ndarray, target: int, conditioning: list[int]) -> float:
    if not conditioning:
        return float(covariance[target, target])
    block = covariance[np.ix_(conditioning, conditioning)]
    cross = covariance[target, conditioning]
    return float(covariance[target, target] - cross @ np.linalg.solve(block, cross))


def ranked_candidates(covariance: np.ndarray, i: int, j: int) -> list[tuple[float, float, float, tuple[int, ...]]]:
    """(bidirectional gain, worse direction, better direction, S), ordered as section 15.4 orders them."""
    scored = []
    for separator in [()] + [(other,) for other in range(P) if other not in (i, j)]:
        columns = list(separator)
        theta_i = (conditional_variance(covariance, i, columns) - conditional_variance(covariance, i, columns + [j])) / covariance[i, i]
        theta_j = (conditional_variance(covariance, j, columns) - conditional_variance(covariance, j, columns + [i])) / covariance[j, j]
        scored.append((theta_i + theta_j, max(theta_i, theta_j), min(theta_i, theta_j), separator))
    # Section 15.4 ranks by *minimising* the bidirectional gain; the tuple breaks ties deterministically.
    scored.sort(key=lambda item: (item[0], item[3]))
    return scored


def sweep() -> tuple[pd.DataFrame, pd.DataFrame]:
    results = pd.read_parquet(RESULTS)
    linear = results[results.family == "linear_gaussian"]
    keys = sorted({(row.edge_strength, int(row.replicate)) for row in linear.itertuples()})
    print(f"linear_gaussian replicates rebuilt from recorded seeds: {len(keys)}")

    tally: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # `k = 14` is unanimity, and the empty set is always one of the 14. Requiring it to
    # separate is a *marginal* condition, so the top of the sweep could be the separator
    # search doing nothing and a marginal screen doing everything. These three rules
    # decompose it: all 14, the 13 singletons alone, and the empty set alone.
    decomposition: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    names = node_names(P)

    for position, (edge_strength, seed) in enumerate(keys, start=1):
        graph = sample_graph(p=P, seed=seed, family="linear_gaussian", edge_strength=edge_strength)
        covariance = population_covariance(graph)
        index = {name: place for place, name in enumerate(names)}
        edge_theta = oracle_edge_theta(graph)
        strongest = (
            edge_theta.assign(pair=[frozenset((row.target, row.added)) for row in edge_theta.itertuples()])
            .groupby("pair").theta.max()
        )
        strong_pairs = {
            label: {pair for pair, theta in strongest.items() if theta > threshold}
            for label, threshold in STRONG_THRESHOLDS.items()
        }
        practical = {delta: practical_nonedge_pairs(graph, delta, edge_theta=edge_theta) for delta in DELTAS}
        ranked = {(i, j): ranked_candidates(covariance, i, j) for i, j in itertools.combinations(range(P), 2)}

        for delta in DELTAS:
            absent = practical[delta]
            wrongful = dict.fromkeys(KS, False)
            for (i, j), candidates in ranked.items():
                pair = frozenset((names[i], names[j]))
                separating = [worse <= delta for _, worse, _, _ in candidates]
                adjacency = [better > delta for _, _, better, _ in candidates]
                practically_absent = pair in absent
                # A strong real pair must still be a real pair at this resolution.
                strong = {label: pair in group and not practically_absent for label, group in strong_pairs.items()}
                for k in KS:
                    bucket = tally[(edge_strength, delta, k)]
                    bucket["pairs"] += 1
                    bucket["absent" if practically_absent else "present"] += 1
                    for label in STRONG_THRESHOLDS:
                        bucket[f"strong_{label}"] += int(strong[label])
                    if all(separating[:k]):
                        bucket["true_prune" if practically_absent else "false_prune"] += 1
                        for label in STRONG_THRESHOLDS:
                            bucket[f"strong_false_prune_{label}"] += int(strong[label])
                        wrongful[k] = wrongful[k] or not practically_absent
                    elif all(adjacency[:k]):
                        bucket["candidate_adjacency"] += 1
                    else:
                        bucket["unresolved"] += 1

                singleton = [flag for flag, (_, _, _, separator) in zip(separating, candidates) if separator]
                marginal = next(flag for flag, (_, _, _, separator) in zip(separating, candidates) if not separator)
                row = decomposition[(edge_strength, delta)]
                row["absent" if practically_absent else "present"] += 1
                for rule, declared in (("all_14", all(separating)), ("singletons_13", all(singleton)), ("empty_set_only", marginal)):
                    if declared:
                        row[f"{rule}_{'true' if practically_absent else 'false'}_prune"] += 1
            for k in KS:
                tally[(edge_strength, delta, k)]["replications"] += 1
                tally[(edge_strength, delta, k)]["familywise"] += int(wrongful[k])
        if position % 50 == 0:
            print(f"  {position}/{len(keys)}")

    def rate(bucket: dict[str, int], numerator: str, denominator: str) -> float:
        return bucket[numerator] / bucket[denominator] if bucket[denominator] else float("nan")

    table = pd.DataFrame([
        {
            "edge_strength": edge_strength, "delta": delta, "k": k,
            "correct_prune_rate": rate(bucket, "true_prune", "absent"),
            "wrongful_prune_rate": rate(bucket, "false_prune", "present"),
            "strong_wrongful_prune_rate_040": rate(bucket, "strong_false_prune_040", "strong_040"),
            "strong_wrongful_prune_rate_060": rate(bucket, "strong_false_prune_060", "strong_060"),
            "familywise_wrongful_rate": rate(bucket, "familywise", "replications"),
            "unresolved_rate": rate(bucket, "unresolved", "pairs"),
            "candidate_adjacency_rate": rate(bucket, "candidate_adjacency", "pairs"),
            "practical_absent": bucket["absent"], "practical_present": bucket["present"],
            "strong_present_040": bucket["strong_040"], "strong_present_060": bucket["strong_060"],
            "replications": bucket["replications"],
        }
        for (edge_strength, delta, k), bucket in sorted(tally.items())
    ])
    decomposed = pd.DataFrame([
        {
            "edge_strength": edge_strength, "delta": delta, "rule": rule,
            "correct_prune_rate": rate(row, f"{rule}_true_prune", "absent"),
            "wrongful_prune_rate": rate(row, f"{rule}_false_prune", "present"),
        }
        for (edge_strength, delta), row in sorted(decomposition.items())
        for rule in ("all_14", "singletons_13", "empty_set_only")
    ])
    return table, decomposed


def draw(table: pd.DataFrame, destination: Path) -> None:
    strengths = ["realistic", "strong"]
    series = [
        ("correct_prune_rate", "correct pruning (absent pairs)", "#1a7f5a", "-"),
        ("wrongful_prune_rate", "wrongful pruning (real pairs)", "#c2410c", "-"),
        ("strong_wrongful_prune_rate_040", "wrongful pruning (strong real pairs, true Theta > 0.40)", "#7c2d12", "--"),
        ("familywise_wrongful_rate", "graph with >= 1 wrongful pruning", "#b91c1c", "-"),
        ("unresolved_rate", "unresolved pairs", "#64748b", ":"),
    ]
    canvas, axes = plt.subplots(2, 3, figsize=(14.5, 8), sharex=True, sharey=True)
    for row, edge_strength in enumerate(strengths):
        for column, delta in enumerate(DELTAS):
            axis = axes[row][column]
            cell = table[(table.edge_strength == edge_strength) & (table.delta == delta)].sort_values("k")
            for name, label, colour, style in series:
                axis.plot(cell.k, cell[name], color=colour, linestyle=style, marker="o", markersize=3, linewidth=1.6, label=label)
            axis.axhline(0.05, color="#0f172a", linewidth=1, linestyle="-.", alpha=.55)
            axis.set_title(f"{edge_strength}   delta = {delta:.2f}", fontsize=11)
            axis.set_ylim(-.03, 1.03)
            axis.set_xticks([1, 3, 5, 7, 9, 11, 13, 14])
            axis.grid(alpha=.25, linewidth=.6)
            if row == 1:
                axis.set_xlabel("k  (top-k candidate separators must all agree)")
            if column == 0:
                axis.set_ylabel("rate")
    handles, labels = axes[0][0].get_legend_handles_labels()
    handles.append(plt.Line2D([], [], color="#0f172a", linestyle="-.", linewidth=1, alpha=.55))
    labels.append("alpha = 0.05")
    canvas.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=10, bbox_to_anchor=(.5, -.015))
    canvas.suptitle(
        "Separator agreement, k = 1 to 14 — population ceilings from the comparator-gate graphs\n"
        "linear_gaussian, p=15, 200 replications per edge strength; oracle Theta, no sampling and no test",
        fontsize=12,
    )
    canvas.tight_layout(rect=(0, .07, 1, .95))
    canvas.savefig(destination, dpi=170, bbox_inches="tight")


def main() -> None:
    table, decomposed = sweep()
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    columns = ["edge_strength", "delta", "k", "correct_prune_rate", "wrongful_prune_rate", "strong_wrongful_prune_rate_040", "strong_wrongful_prune_rate_060", "familywise_wrongful_rate", "unresolved_rate"]
    print()
    print(table[columns].to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print("\nunanimity decomposition: is k=14 the separator search, or just a marginal screen?")
    print(decomposed.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    table.to_csv(HERE / "agreement_k_sweep.csv", index=False)
    decomposed.to_csv(HERE / "unanimity_decomposition.csv", index=False)
    draw(table, HERE / "agreement_k_sweep.png")
    print(f"\nwrote agreement_k_sweep.csv, unanimity_decomposition.csv and agreement_k_sweep.png in {HERE}")


if __name__ == "__main__":
    main()
