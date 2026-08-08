"""Specification section 27 resolution path.

For each candidate resolution, how many pairs the data could place below it. This is what
turns "most pairs came back unresolved" into an answerable question: was the requested
`delta` finer than anything this dataset supports, or is the structure genuinely there?

The path is derived from per-pair achieved resolution, which is already a one-sided upper
limit on `Theta`. A pair with an achieved resolution of 0.11 is one the data can place
below any `delta` above 0.11, so counting is enough and nothing is re-estimated.

Two things it deliberately does not do.

It is **not a second set of certificates**. Only a node's own `delta` has a matched
calibration profile; every other row on the grid describes what the data could support,
with no error guarantee attached. Section 27 is explicit that the primary result must not
be reselected after seeing the path, and `resolvable` is named to avoid suggesting
otherwise.

It ignores **multiplicity**. Certification adjusts pair-level p-values across the family,
so the resolvable count at a given `delta` is an upper bound on how many pairs would
actually certify there, not a prediction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from pydantic import Field

from renca.models import Model, ProjectSpec, SCHEMA_VERSION
from renca.reporting.fit import NetworkFit


class ResolutionPathRow(Model):
    delta: float
    is_primary: bool
    calibrated: bool
    resolvable_pairs: int
    measurable_pairs: int
    total_pairs: int


class ResolutionPath(Model):
    """How much of the network each candidate resolution could settle."""

    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    primary_deltas: list[float] = Field(default_factory=list)
    rows: list[ResolutionPathRow] = Field(default_factory=list)
    interpretation: str
    certificates_apply_only_at_primary_delta: bool = True


def _interpret(rows: list[ResolutionPathRow], primary: list[float]) -> str:
    at_primary = [row for row in rows if row.is_primary]
    if not at_primary or not at_primary[0].measurable_pairs:
        return "No pair had a measurable resolution, so the path is empty; inspect the estimator diagnostics."
    finest, coarsest = at_primary[0], at_primary[-1]
    measurable = finest.measurable_pairs
    parts = [f"At the primary delta of {finest.delta:.3f}, {finest.resolvable_pairs} of {measurable} measurable pairs could be placed below it."]
    reachable = [row for row in rows if row.resolvable_pairs > coarsest.resolvable_pairs and row.delta > coarsest.delta]
    if finest.resolvable_pairs < measurable and reachable:
        gain = reachable[0]
        parts.append(f"A coarser resolution of {gain.delta:.3f} would reach {gain.resolvable_pairs}, so some pairs are unresolved because the question is finer than the data can answer rather than because the variables are related.")
    parts.append("Only the primary delta carries a calibration profile; the other rows describe what the data could support and are not certificates. Choosing a primary result after reading this path invalidates the error control.")
    return " ".join(parts)


def build_resolution_path(fit: NetworkFit, project_spec: ProjectSpec) -> ResolutionPath:
    """Count, for each candidate resolution, the pairs the data could place below it."""
    primary = sorted({node.delta for node in project_spec.nodes})
    measurable = [pair.achieved_resolution for pair in fit.pairs if pair.achieved_resolution is not None]
    calibrated = fit.resolution_basis == "calibrated"
    rows = [
        ResolutionPathRow(
            delta=delta,
            is_primary=delta in primary,
            # A non-primary resolution has no matched profile, so it can never be calibrated
            # even when the primary one is.
            calibrated=calibrated and delta in primary,
            resolvable_pairs=sum(1 for value in measurable if value <= delta),
            measurable_pairs=len(measurable),
            total_pairs=len(fit.pairs),
        )
        for delta in sorted(set(project_spec.resolution_grid) | set(primary))
    ]
    return ResolutionPath(analysis_id=str(project_spec.analysis_id), primary_deltas=primary, rows=rows, interpretation=_interpret(rows, primary))


def write_resolution_path(path: ResolutionPath, output_dir: str | Path) -> tuple[Path, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    parquet = destination / "resolution_path.parquet"
    pd.DataFrame([row.model_dump() for row in path.rows]).to_parquet(parquet, index=False)
    json_path = destination / "resolution_path.json"
    json_path.write_text(json.dumps(path.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    return parquet, json_path
