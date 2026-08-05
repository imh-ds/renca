"""Post-hoc network fit indices.

These answer a question the pair states cannot: whether the analysis had any information
to work with. A dataset of pure noise resolves *every* pair as a certified nonedge, because
the conditioning models explain nothing and so every incremental contribution is near zero.
That output is not a false certification -- in pure noise there really are no edges -- but
it is indistinguishable from a discovery, and the same signature appears when learners fail
to fit structure that is genuinely present.

Two indices are reported, in the spirit of SEM fit statistics: computed automatically after
the run, requiring no user configuration.

`predictive_adequacy`
    `1 - R(S) / R(empty)`, the share of the target's baseline predictive uncertainty the
    conditioning model actually removes. Near zero means the contrast that every pair state
    rests on was uninformative, so nothing else in the report should be interpreted.

`achieved_resolution`
    The smallest delta at which a pair would have been certified, which is a one-sided upper
    limit on Theta. It says how fine a claim the data can support, and it remains meaningful
    when a pair is unresolved -- "Theta is at most this" is informative even when it does not
    clear a prespecified threshold. It is driven by the standard error, which combines sample
    size, data quality, and learner performance, so a small clean sample can resolve more
    finely than a large noisy one.

No validated cut-offs exist for either index. SEM's conventional thresholds came from
simulation studies mapping index values to error rates, and the equivalent work has not been
done here, so this module reports values and states the one conclusion that follows
logically rather than empirically: a model explaining none of the variance supports no
structural conclusion.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import Field
from scipy.stats import norm

from renca.models import Model, ProjectSpec, SCHEMA_VERSION
from renca.vimp import VimpEstimate

ResolutionBasis = Literal["calibrated", "normal_approximation", "unavailable"]


class PairFit(Model):
    pair_id: str
    achieved_resolution: float | None = None
    resolution_floor: float | None = None
    resolution_basis: ResolutionBasis
    predictive_adequacy: float | None = None


class NetworkFit(Model):
    """Automatically computed indices describing how much the analysis could resolve."""

    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    predictive_adequacy_median: float | None = None
    predictive_adequacy_minimum: float | None = None
    achieved_resolution_median: float | None = None
    achieved_resolution_p90: float | None = None
    resolution_floor_median: float | None = None
    resolution_floor_p90: float | None = None
    resolution_basis: ResolutionBasis
    primary_delta_range: list[float] = Field(default_factory=list)
    interpretation: str
    thresholds_are_validated: Literal[False] = False
    pairs: list[PairFit] = Field(default_factory=list)


def _adequacy(estimate: VimpEstimate) -> float | None:
    """Share of baseline predictive uncertainty removed by the conditioning model."""
    diagnostic = estimate.nuisance_diagnostic
    null_risk, reduced = diagnostic.get("null_risk"), diagnostic.get("mean_reduced_loss")
    if not isinstance(null_risk, (int, float)) or not isinstance(reduced, (int, float)) or null_risk <= 0:
        return None
    return 1 - reduced / null_risk


def _directional_resolution(estimate: VimpEstimate, critical_value: float | None, confidence_level: float) -> tuple[float | None, float | None, ResolutionBasis]:
    """Achieved resolution and resolution floor for one direction.

    The achieved resolution `theta + width` is the smallest delta at which this direction
    would clear its equivalence test, so it answers "how large might Theta be". The floor is
    `width` alone: the finest delta the analysis could ever certify, for a pair whose
    estimate is exactly zero. Only the floor is a precision measure. A network of genuinely
    strong relationships has large achieved resolutions because its effects are large, which
    says nothing about how well the analysis was powered.
    """
    if estimate.theta_hat is None or estimate.se_theta is None or estimate.se_theta <= 0:
        return None, None, "unavailable"
    if critical_value is not None:
        width = abs(critical_value) * estimate.se_theta
        return estimate.theta_hat + width, width, "calibrated"
    width = norm.ppf(confidence_level) * estimate.se_theta
    return estimate.theta_hat + width, width, "normal_approximation"


def _interpret(adequacy_median: float | None, adequacy_minimum: float | None, floor_median: float | None, deltas: list[float], basis: ResolutionBasis) -> str:
    if adequacy_median is None:
        return "Predictive adequacy could not be computed; inspect the estimator diagnostics before reading any pair state."
    if adequacy_median <= 0:
        return f"Predictive adequacy is {adequacy_median:.3f}: the conditioning models explained none of the outcome variance, so these results do not support conclusions about network structure, including apparent nonedges."
    parts = [f"Predictive adequacy is {adequacy_median:.3f} (minimum {adequacy_minimum:.3f} across directions)."]
    if floor_median is not None:
        qualifier = "under the matched calibration profile" if basis == "calibrated" else "under an unvalidated normal approximation"
        parts.append(f"The finest delta this analysis could certify for a typical pair is {floor_median:.3f} {qualifier}.")
        # The configuration is internally inconsistent when the requested resolution is
        # finer than anything the data can deliver, which otherwise shows up only as an
        # unexplained wall of unresolved pairs.
        if deltas and floor_median > max(deltas):
            parts.append(f"That is coarser than every requested delta (up to {max(deltas):.3f}), so most pairs cannot certify at the resolution asked of them regardless of their true values.")
    parts.append("No validated thresholds exist for these indices; read them alongside the estimator diagnostics rather than as pass or fail.")
    return " ".join(parts)


def build_network_fit(estimates: list[VimpEstimate], project_spec: ProjectSpec, critical_value: float | None = None) -> NetworkFit:
    """Summarize how much information the analysis had, independent of its pair states."""
    confidence_level = project_spec.vimp.confidence_level
    grouped: dict[str, list[VimpEstimate]] = {}
    for estimate in estimates:
        grouped.setdefault(estimate.pair_id, []).append(estimate)

    pairs: list[PairFit] = []
    for pair_id in sorted(grouped):
        directions = grouped[pair_id]
        resolutions, floors, bases = zip(*(_directional_resolution(estimate, critical_value, confidence_level) for estimate in directions))
        adequacies = [value for value in (_adequacy(estimate) for estimate in directions) if value is not None]
        # A pair certifies only when both directions clear, so it takes the worse of the two
        # on each index, and its adequacy is the weaker of the two conditioning models.
        complete = all(value is not None for value in resolutions)
        basis: ResolutionBasis = "unavailable" if not complete else ("calibrated" if "calibrated" in bases else "normal_approximation")
        pairs.append(PairFit(pair_id=pair_id, achieved_resolution=max(resolutions) if complete else None, resolution_floor=max(floors) if complete else None, resolution_basis=basis, predictive_adequacy=min(adequacies) if adequacies else None))

    all_adequacies = [value for value in (_adequacy(estimate) for estimate in estimates) if value is not None]
    resolved = sorted(pair.achieved_resolution for pair in pairs if pair.achieved_resolution is not None)
    floors = sorted(pair.resolution_floor for pair in pairs if pair.resolution_floor is not None)
    adequacy_median = statistics.median(all_adequacies) if all_adequacies else None
    floor_median = statistics.median(floors) if floors else None
    basis: ResolutionBasis = "calibrated" if critical_value is not None else ("normal_approximation" if resolved else "unavailable")
    return NetworkFit(
        analysis_id=str(project_spec.analysis_id),
        predictive_adequacy_median=adequacy_median,
        predictive_adequacy_minimum=min(all_adequacies) if all_adequacies else None,
        achieved_resolution_median=statistics.median(resolved) if resolved else None,
        achieved_resolution_p90=float(np.quantile(resolved, .9)) if resolved else None,
        resolution_floor_median=floor_median,
        resolution_floor_p90=float(np.quantile(floors, .9)) if floors else None,
        resolution_basis=basis,
        primary_delta_range=sorted({node.delta for node in project_spec.nodes}),
        interpretation=_interpret(adequacy_median, min(all_adequacies) if all_adequacies else None, floor_median, sorted({node.delta for node in project_spec.nodes}), basis),
        pairs=pairs,
    )


def write_network_fit(fit: NetworkFit, output_dir: str | Path) -> Path:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "network_fit.json"
    path.write_text(json.dumps(fit.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return path
