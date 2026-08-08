"""One replication of the section 13.4 comparative gate, scored on a common axis.

Every method is reduced to the set of pairs it declares absent, and scored against the
generating DAG's adjacency:

* **false prune** -- an adjacent pair declared absent. For the baselines this is a Type II
  error of their test; for this method it is a violation of the certificate.
* **true prune** -- a non-adjacent pair declared absent. Pruning power.

The two rates trade off against each other, so neither is meaningful alone and the study
sweeps each baseline's tuning parameter to trace its curve rather than reporting one point.

Three scoring decisions are worth stating because they all cut against this method.

**Unscreened pairs count as not pruned.** Neighborhood screening is high-recall selection,
not inference, so a pair that never reaches a test has no certificate and no claim of
absence. Scoring it as pruned would credit the method for an edge it never examined.

**Unresolved counts as not pruned.** The three-state output exists precisely so that
"no evidence either way" is not reported as absence.

**Every arm is scored against two different truths**, because the methods do not share an
estimand and picking one would decide the result by definition.

* *graphical* -- adjacency in the generating DAG, which is what PC and FCI target. Harsh on
  this method: an edge too weak to matter is still an edge, so certifying it is charged as
  an error even though the certificate is about practical, not exact, absence.
* *practical at delta* -- adjacency, minus edges whose oracle ``Theta`` falls at or below
  ``delta`` in **both** directions. Generous to the baselines, which get the same relabel
  despite having no ``delta``.

Neither is the honest number on its own and the pilot showed why: at ``delta = 0.20`` this
method pruned nine adjacent pairs, and exactly those nine were the edges whose ``Theta`` sat
under 0.20 in both directions. Graphical scoring alone would have published a 43% false-prune
rate for a run that made no errors at all. Reporting the pair brackets the answer instead of
choosing the flattering half.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import numpy as np
import pandas as pd

from renca.benchmark.comparators import MAX_CONDITIONING_SIZE, ebicglasso_adjacency_by_gamma, structural_adjacency
from renca.benchmark.dgp import BenchmarkGraph, generate_sample, node_names, oracle_edge_theta, practical_nonedge_pairs, sample_graph
from renca.calibration.apply import apply_profile
from renca.calibration.registry import CalibrationRegistry
from renca.certification import PairState, certify_pairs
from renca.models import ProjectSpec, VimpSpec
from renca.screening import create_outer_split, rank_separators, screen_neighbors
from renca.vimp import fit_crossfitted_vimp

# The packaged profiles bind to exactly 300 inference rows, so a calibrated run needs
# 375 total at a 0.2 selection fraction. This is not a tuning choice.
CALIBRATED_SAMPLE_SIZE = 375
DELTA_PROFILES = {.05: "v4-cubic-blend-n300-d005-phase0", .10: "v4-cubic-blend-n300-d010-phase0", .20: "v4-cubic-blend-n300-d020-phase0"}


def _pair_key(pair_id: str) -> frozenset[str]:
    return frozenset(pair_id.split("--", 1))


def benchmark_project_spec(*, p: int, delta: float, seed: int, vimp_spec: VimpSpec, profile_id: str | None, max_separator_size: int, selection_fraction: float, inference_folds: int) -> ProjectSpec:
    return ProjectSpec.model_validate({
        "schema_version": "1.7.0",
        "analysis_id": str(UUID(int=seed % (1 << 128))),
        "preanalysis_reference": "docs/evidence/phase1/comparator-gate/README.md",
        "seed": seed,
        "missing_data_policy": "complete_case",
        "design": {"sampling_unit": "iid", "cluster_id_column": None},
        "split": {"selection_fraction": selection_fraction, "inference_folds": inference_folds},
        "audit": {"minimum_rows_per_inference_fold": 40},
        # Every pair reaches a test, so the comparison measures inference rather than
        # screening. `max_separator_size` matches the baselines' conditioning-size limit.
        "screening": {"max_neighbors": p - 1, "max_separator_size": max_separator_size, "separators_per_pair": 1},
        "vimp": vimp_spec.model_dump(mode="json"),
        "calibration": {"profile_id": profile_id},
        "nodes": [{"node_id": name, "outcome_type": "continuous", "loss": "squared", "delta": delta} for name in node_names(p)],
    })


def score_prunes(pruned: set[frozenset[str]], graph: BenchmarkGraph, practical_absent: set[frozenset[str]]) -> dict[str, object]:
    """Score one arm's declared-absent set against both truths at once."""
    adjacent, nonadjacent = graph.adjacent_pairs(), graph.nonadjacent_pairs()
    practical_present = graph.all_pairs() - practical_absent
    false_prunes = pruned & adjacent
    practical_false = pruned & practical_present
    return {
        "pruned": len(pruned),
        "false_prunes": len(false_prunes),
        "true_prunes": len(pruned & nonadjacent),
        "edges": len(adjacent),
        "nonedges": len(nonadjacent),
        "familywise_false_prune": bool(false_prunes),
        "practical_false_prunes": len(practical_false),
        "practical_true_prunes": len(pruned & practical_absent),
        "practical_present": len(practical_present),
        "practical_absent": len(practical_absent),
        "practical_familywise_false_prune": bool(practical_false),
    }


def run_renca(data: pd.DataFrame, graph: BenchmarkGraph, *, seed: int, deltas: list[float], registry: CalibrationRegistry, registry_path: str | Path, vimp_spec: VimpSpec, max_separator_size: int, alpha: float, selection_fraction: float, inference_folds: int, practical: dict[float, set[frozenset[str]]]) -> list[dict[str, object]]:
    """Fit once, then certify at every requested resolution.

    `theta_hat` and `se_theta` do not depend on ``delta`` -- it enters only the test and the
    profile lookup -- so refitting per resolution would burn three times the compute to
    reproduce the same numbers.
    """
    template = benchmark_project_spec(p=graph.p, delta=deltas[0], seed=seed, vimp_spec=vimp_spec, profile_id=DELTA_PROFILES[deltas[0]], max_separator_size=max_separator_size, selection_fraction=selection_fraction, inference_folds=inference_folds)
    split = create_outer_split(data, template)
    selected = data.iloc[split.selection_row_positions]
    neighborhoods = screen_neighbors(selected, template.nodes, template.screening, seed=template.seed)
    candidates = rank_separators(selected, template.nodes, neighborhoods, template.screening, seed=template.seed)
    nodes = {node.node_id: node for node in template.nodes}
    estimates = []
    for candidate in candidates:
        estimates.append(fit_crossfitted_vimp(data, candidate.node_i, candidate.node_j, candidate.separator, nodes[candidate.node_i], split, template.vimp))
        estimates.append(fit_crossfitted_vimp(data, candidate.node_j, candidate.node_i, candidate.separator, nodes[candidate.node_j], split, template.vimp))

    tested = {_pair_key(candidate.pair_id) for candidate in candidates}
    separators = {candidate.pair_id: candidate.separator for candidate in candidates}
    valid_separator = sum(1 for candidate in candidates if _is_separating(graph, candidate.pair_id, separators[candidate.pair_id]))
    rows = []
    for delta in deltas:
        retargeted = [estimate.model_copy(update={"delta_target": delta}) for estimate in estimates]
        applied = apply_profile(retargeted, registry=registry, registry_path=registry_path, profile_id=DELTA_PROFILES[delta], inference_rows=len(split.inference_row_positions), inference_folds=split.inference_folds, vimp_spec=vimp_spec)
        certificates = certify_pairs(applied, alpha=alpha)
        pruned = {_pair_key(item.pair_id) for item in certificates if item.state is PairState.CERTIFIED_NONEDGE}
        rows.append({
            "method": "renca",
            "setting": delta,
            "reference_delta": delta,
            "profile_id": DELTA_PROFILES[delta],
            **score_prunes(pruned, graph, practical[delta]),
            "unresolved": sum(1 for item in certificates if item.state is PairState.UNRESOLVED),
            "candidate_adjacency": sum(1 for item in certificates if item.state is PairState.CANDIDATE_ADJACENCY),
            "untested_pairs": len(graph.all_pairs() - tested),
            "abstentions": sum(1 for estimate in applied if estimate.status != "success"),
            "calibrated_directions": sum(1 for estimate in applied if estimate.calibration_status == "calibrated_success"),
            "valid_separators": valid_separator,
            "separator_opportunities": len(candidates),
        })
    return rows


def _is_separating(graph: BenchmarkGraph, pair_id: str, separator: list[str]) -> bool:
    """Whether the chosen conditioning set d-separates a non-adjacent pair.

    Reported as a diagnostic: a pair conditioned on a non-separating set (a collider, say)
    retains association and comes back unresolved, which is conservative rather than an
    error, but it caps pruning power and should be visible if it does.
    """
    first, second = sorted(pair_id.split("--", 1))
    if frozenset((first, second)) in graph.adjacent_pairs():
        return False
    return _d_separated(graph, first, second, set(separator))


def _d_separated(graph: BenchmarkGraph, first: str, second: str, conditioning: set[str]) -> bool:
    """Standard reachability d-separation test over the DAG."""
    names = graph.names
    index = {name: position for position, name in enumerate(names)}
    parents = {position: set(group) for position, group in enumerate(graph.parents)}
    children: dict[int, set[int]] = {position: set() for position in range(graph.p)}
    for child, group in enumerate(graph.parents):
        for parent in group:
            children[parent].add(child)
    blocked = {index[name] for name in conditioning}
    # Ancestors of the conditioning set decide whether a collider opens a path.
    ancestors, frontier = set(blocked), list(blocked)
    while frontier:
        node = frontier.pop()
        for parent in parents[node]:
            if parent not in ancestors:
                ancestors.add(parent)
                frontier.append(parent)
    start, goal = index[first], index[second]
    visited: set[tuple[int, str]] = set()
    stack = [(start, "up")]
    while stack:
        node, direction = stack.pop()
        if (node, direction) in visited:
            continue
        visited.add((node, direction))
        if node == goal:
            return False
        if direction == "up" and node not in blocked:
            stack.extend([(parent, "up") for parent in parents[node]] + [(child, "down") for child in children[node]])
        elif direction == "down":
            if node not in blocked:
                stack.extend([(child, "down") for child in children[node]])
            if node in ancestors:  # collider open only when it or a descendant is conditioned on
                stack.extend([(parent, "up") for parent in parents[node]])
    return True


def run_benchmark_replication(*, seed: int, n: int, p: int, family: str, deltas: list[float], comparator_settings: dict[str, list[float]], registry: CalibrationRegistry, registry_path: str | Path, vimp_spec: VimpSpec, max_separator_size: int = MAX_CONDITIONING_SIZE, alpha: float = .05, selection_fraction: float = .2, inference_folds: int = 5, indep_test: str = "fisherz", include_renca: bool = True, edge_strength: str = "realistic") -> list[dict[str, object]]:
    """Generate one dataset and score every method and setting on it.

    All methods see the same rows, so differences are not sampling noise between arms.
    """
    graph = sample_graph(p=p, seed=seed, family=family, edge_strength=edge_strength)
    data = generate_sample(graph, n=n, seed=int(np.random.SeedSequence([seed, 7]).generate_state(1)[0]))
    # One oracle pass per graph, reused for every arm and every resolution.
    edge_theta = oracle_edge_theta(graph)
    practical = {delta: practical_nonedge_pairs(graph, delta, edge_theta=edge_theta) for delta in deltas}
    # `moral_only` caps what any Gaussian graphical model can prune: co-parents carry a
    # nonzero partial correlation, so EBICglasso can never declare them absent.
    common = {"replicate": seed, "n": n, "p": p, "family": family, "edge_strength": edge_strength, "edges": len(graph.adjacent_pairs()), "moral_only": len(graph.moral_only_pairs())}
    rows: list[dict[str, object]] = []
    if include_renca:
        rows.extend(run_renca(data, graph, seed=seed, deltas=deltas, registry=registry, registry_path=registry_path, vimp_spec=vimp_spec, max_separator_size=max_separator_size, alpha=alpha, selection_fraction=selection_fraction, inference_folds=inference_folds, practical=practical))
    # Every EBIC gamma reads off one penalty path, which is the only expensive part.
    glasso = ebicglasso_adjacency_by_gamma(data, comparator_settings["ebicglasso"]) if comparator_settings.get("ebicglasso") else {}
    for method, settings in comparator_settings.items():
        for setting in settings:
            try:
                adjacency = glasso[setting] if method == "ebicglasso" else structural_adjacency(method, data, setting=setting, indep_test=indep_test, max_k=max_separator_size)
            except Exception as error:  # a baseline that fails must be visible, not silently absent
                rows.append({"method": method, "setting": setting, "reference_delta": deltas[0], "failed": str(error)[:200]})
                continue
            pruned = graph.all_pairs() - adjacency
            # A baseline has no delta, so it is scored once against each resolution the
            # method is tested at; only then are the two comparable within a cell.
            rows.extend({"method": method, "setting": setting, "reference_delta": delta, **score_prunes(pruned, graph, practical[delta])} for delta in deltas)
    return [{**common, **row} for row in rows]


def summarize_benchmark(results: pd.DataFrame) -> pd.DataFrame:
    """Pool pair-level counts into the false-prune/true-prune trade-off per arm.

    Counts are pooled before dividing rather than averaged across replications: graphs
    differ in edge count, and averaging per-replication rates would let a sparse graph's
    few edges weigh as much as a dense one's many.
    """
    from scipy.stats import beta

    grouped = results.groupby(["family", "edge_strength", "n", "reference_delta", "method", "setting"], dropna=False)
    summary = grouped.agg(
        replications=("replicate", "count"),
        false_prunes=("false_prunes", "sum"),
        true_prunes=("true_prunes", "sum"),
        edges=("edges", "sum"),
        nonedges=("nonedges", "sum"),
        moral_only=("moral_only", "sum"),
        familywise_errors=("familywise_false_prune", "sum"),
        practical_false_prunes=("practical_false_prunes", "sum"),
        practical_true_prunes=("practical_true_prunes", "sum"),
        practical_present=("practical_present", "sum"),
        practical_absent=("practical_absent", "sum"),
        practical_familywise_errors=("practical_familywise_false_prune", "sum"),
    ).reset_index()
    summary["false_prune_rate"] = summary.false_prunes / summary.edges
    summary["true_prune_rate"] = summary.true_prunes / summary.nonedges
    # What a Gaussian graphical model could reach even with unlimited data.
    summary["moral_graph_prune_ceiling"] = 1 - summary.moral_only / summary.nonedges
    summary["practical_false_prune_rate"] = summary.practical_false_prunes / summary.practical_present
    summary["practical_true_prune_rate"] = summary.practical_true_prunes / summary.practical_absent
    summary["familywise_error_rate"] = summary.familywise_errors / summary.replications
    summary["practical_familywise_error_rate"] = summary.practical_familywise_errors / summary.replications
    for source, target in (("practical_familywise_errors", "practical_familywise_upper_bound"), ("familywise_errors", "familywise_upper_bound")):
        summary[target] = [
            float(beta.ppf(.95, errors + 1, max(reps - errors, 0) + 1))
            for errors, reps in zip(summary[source].astype(int), summary.replications.astype(int))
        ]
    return summary.sort_values(["family", "edge_strength", "n", "reference_delta", "method", "setting"], ignore_index=True)
