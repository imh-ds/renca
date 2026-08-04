"""Multi-pair familywise error simulation for the practical-nonedge certificate.

The Phase-0 profile is calibrated on a single directional hypothesis with a fixed,
known separator. Specification section 44 falsification criterion 1 is about
*familywise* false pruning, so this module exercises the whole confirmatory path --
screening, separator ranking, cross-fitted estimation, the intersection-union test,
and the Holm adjustment -- with several boundary pairs present at once.

Each independent block contributes one boundary pair. Within a block ``z`` is a common
cause of ``x`` and ``y``, whose residuals carry exactly enough correlation that *both*
directional normalized VIMPs equal ``delta``. That symmetry matters: the pair-level
test takes the maximum of the two directional p-values, so a block with only one
direction at the boundary would be dominated by the other direction and would make the
familywise check vacuously conservative.

Conditioning on ``z`` is also necessary rather than incidental. Without it the pair
retains the confounded association, far above ``delta``, so a replication that fails to
recover ``z`` as the separator is conservative rather than anti-conservative -- and the
recovery rate is reported so that conservatism is visible instead of assumed.
"""

from __future__ import annotations

import math
from pathlib import Path
from uuid import UUID

import numpy as np
import pandas as pd

from renca.calibration.apply import apply_profile
from renca.calibration.registry import CalibrationRegistry
from renca.certification import PairState, certify_pairs
from renca.models import ProjectSpec, VimpSpec
from renca.screening import create_outer_split, rank_separators, screen_neighbors
from renca.vimp import fit_crossfitted_vimp


def block_correlation(delta: float, confounder_loading: float) -> float:
    """Residual correlation placing both directional oracle VIMPs exactly at ``delta``.

    With ``x = c*z + u`` and ``y = c*z + v`` where ``corr(u, v) = rho``, the reduced risk
    given ``z`` is ``1`` and the expanded risk is ``1 - rho**2``, while the target-fixed
    null risk is ``c**2 + 1``. Both directions therefore sit at ``rho**2 / (c**2 + 1)``.
    """
    squared = delta * (confounder_loading**2 + 1)
    if not 0 < squared < 1:
        raise ValueError(f"delta={delta} and loading={confounder_loading} imply an unattainable residual correlation")
    return math.sqrt(squared)


def block_columns(block: int) -> tuple[str, str, str]:
    return f"z{block}", f"x{block}", f"y{block}"


def _pair_id(first: str, second: str) -> str:
    return "--".join(sorted([first, second]))


def boundary_pairs(blocks: int) -> dict[str, str]:
    """Map each block's boundary pair to the separator that reaches the boundary."""
    pairs = {}
    for block in range(blocks):
        confounder, first, second = block_columns(block)
        pairs[_pair_id(first, second)] = confounder
    return pairs


def null_pairs(blocks: int) -> set[str]:
    """Within-block pairs, none of which is practically separable at ``delta``."""
    pairs: set[str] = set()
    for block in range(blocks):
        confounder, first, second = block_columns(block)
        pairs.update({_pair_id(first, second), _pair_id(confounder, first), _pair_id(confounder, second)})
    return pairs


def generate_multipair_scenario(*, blocks: int, n: int, seed: int, delta: float, confounder_loading: float = 1.0) -> pd.DataFrame:
    """Generate independent boundary blocks; cross-block pairs are exact nonedges."""
    if blocks < 1:
        raise ValueError("at least one block is required")
    if n < 30:
        raise ValueError("multi-pair scenarios require at least 30 rows")
    correlation = block_correlation(delta, confounder_loading)
    generator = np.random.default_rng(seed)
    columns: dict[str, np.ndarray] = {}
    for block in range(blocks):
        confounder_name, first_name, second_name = block_columns(block)
        confounder = generator.normal(size=n)
        residuals = generator.multivariate_normal([0.0, 0.0], [[1.0, correlation], [correlation, 1.0]], size=n)
        columns[confounder_name] = confounder
        columns[first_name] = confounder_loading * confounder + residuals[:, 0]
        columns[second_name] = confounder_loading * confounder + residuals[:, 1]
    return pd.DataFrame(columns)


def oracle_block_theta(delta: float, confounder_loading: float = 1.0, *, seed: int = 991, n: int = 400_000) -> tuple[float, float]:
    """Common-random-number Monte Carlo oracle for both directions of a boundary pair."""
    correlation = block_correlation(delta, confounder_loading)
    generator = np.random.default_rng(seed)
    confounder = generator.normal(size=n)
    residuals = generator.multivariate_normal([0.0, 0.0], [[1.0, correlation], [correlation, 1.0]], size=n)
    first = confounder_loading * confounder + residuals[:, 0]
    second = confounder_loading * confounder + residuals[:, 1]
    thetas = []
    for target, added in ((first, second), (second, first)):
        reduced = confounder_loading * confounder
        expanded = reduced + correlation * (added - confounder_loading * confounder)
        psi = float(np.mean((target - reduced) ** 2) - np.mean((target - expanded) ** 2))
        thetas.append(psi / float(np.mean((target - target.mean()) ** 2)))
    return thetas[0], thetas[1]


def _project_spec(blocks: int, delta: float, seed: int, vimp_spec: VimpSpec, profile_id: str | None, selection_fraction: float, inference_folds: int) -> ProjectSpec:
    nodes = [
        {"node_id": name, "outcome_type": "continuous", "loss": "squared", "delta": delta}
        for block in range(blocks)
        for name in block_columns(block)
    ]
    return ProjectSpec.model_validate({
        "schema_version": "1.7.0",
        "analysis_id": str(UUID(int=seed % (1 << 128))),
        "preanalysis_reference": "docs/pilots/phase1-multipair-fwer-protocol.md",
        "seed": seed,
        "missing_data_policy": "complete_case",
        "design": {"sampling_unit": "iid", "cluster_id_column": None},
        "split": {"selection_fraction": selection_fraction, "inference_folds": inference_folds},
        "audit": {"minimum_rows_per_inference_fold": 60},
        "screening": {"max_neighbors": 3, "max_separator_size": 1, "separators_per_pair": 1},
        "vimp": vimp_spec.model_dump(mode="json"),
        "calibration": {"profile_id": profile_id},
        "nodes": nodes,
    })


def run_multipair_replication(*, blocks: int, sample_size: int, seed: int, delta: float, vimp_spec: VimpSpec, registry: CalibrationRegistry | None = None, registry_path: str | Path | None = None, profile_id: str | None = None, alpha: float = .05, selection_fraction: float = .2, inference_folds: int = 5, confounder_loading: float = 1.0) -> dict[str, object]:
    """Run one full confirmatory replication and score its familywise outcome."""
    data = generate_multipair_scenario(blocks=blocks, n=sample_size, seed=seed, delta=delta, confounder_loading=confounder_loading)
    spec = _project_spec(blocks, delta, seed, vimp_spec, profile_id, selection_fraction, inference_folds)
    split = create_outer_split(data, spec)
    selected = data.iloc[split.selection_row_positions]
    neighborhoods = screen_neighbors(selected, spec.nodes, spec.screening, seed=spec.seed)
    candidates = rank_separators(selected, spec.nodes, neighborhoods, spec.screening, seed=spec.seed)
    nodes = {node.node_id: node for node in spec.nodes}
    estimates = []
    for candidate in candidates:
        estimates.append(fit_crossfitted_vimp(data, candidate.node_i, candidate.node_j, candidate.separator, nodes[candidate.node_i], split, spec.vimp))
        estimates.append(fit_crossfitted_vimp(data, candidate.node_j, candidate.node_i, candidate.separator, nodes[candidate.node_j], split, spec.vimp))
    if registry is not None and registry_path is not None:
        estimates = apply_profile(estimates, registry=registry, registry_path=registry_path, profile_id=profile_id, inference_rows=len(split.inference_row_positions), inference_folds=split.inference_folds, vimp_spec=spec.vimp)
    certificates = certify_pairs(estimates, alpha=alpha)

    nulls, boundaries = null_pairs(blocks), boundary_pairs(blocks)
    separator_by_pair = {candidate.pair_id: candidate.separator for candidate in candidates}
    certified = {certificate.pair_id for certificate in certificates if certificate.state is PairState.CERTIFIED_NONEDGE}
    calibrated = sum(1 for estimate in estimates if estimate.calibration_status == "calibrated_success")
    return {
        "replicate": seed,
        "blocks": blocks,
        "pairs": len(certificates),
        "family_size": sum(1 for certificate in certificates if certificate.adjusted_p is not None),
        "calibrated_directions": calibrated,
        "abstentions": sum(1 for estimate in estimates if estimate.status != "success"),
        "false_certifications": len(certified & nulls),
        "boundary_false_certifications": len(certified & set(boundaries)),
        "familywise_error": bool(certified & nulls),
        "true_nonedge_certifications": len(certified - nulls),
        "true_nonedge_pairs": len(certificates) - len(nulls),
        "boundary_separator_recovered": sum(1 for pair, confounder in boundaries.items() if separator_by_pair.get(pair) == [confounder]),
        "boundary_pairs": len(boundaries),
    }


def summarize_multipair_grid(results: pd.DataFrame, *, alpha: float = .05) -> dict[str, object]:
    """Summarize familywise error, its exact upper bound, and pruning power."""
    from scipy.stats import beta

    replications = len(results)
    if not replications:
        raise ValueError("no replications to summarize")
    errors = int(results.familywise_error.sum())
    rate = errors / replications
    upper = float(beta.ppf(.95, errors + 1, replications - errors))
    nonedges, opportunities = int(results.true_nonedge_certifications.sum()), int(results.true_nonedge_pairs.sum())
    boundary_recovered, boundary_total = int(results.boundary_separator_recovered.sum()), int(results.boundary_pairs.sum())
    return {
        "replications": replications,
        "alpha": alpha,
        "familywise_error_rate": rate,
        "familywise_upper_bound": upper,
        "controlled": upper <= alpha,
        "false_certifications": int(results.false_certifications.sum()),
        "boundary_false_certifications": int(results.boundary_false_certifications.sum()),
        "true_nonedge_certification_rate": nonedges / opportunities if opportunities else 0.0,
        "separator_recovery_rate": boundary_recovered / boundary_total if boundary_total else 0.0,
        "mean_family_size": float(results.family_size.mean()),
        "abstention_rate": float(results.abstentions.sum()) / float((results.pairs * 2).sum()),
    }
