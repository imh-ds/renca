"""Deterministic, stratified selection and inference splits."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from renca.models import Model, OutcomeType, ProjectSpec, SCHEMA_VERSION, SamplingUnit


class SplitManifest(Model):
    """Versioned record of the data partition used by downstream stages."""

    schema_version: Literal[SCHEMA_VERSION]
    analysis_id: str
    seed: int
    selection_fraction: float
    inference_folds: int
    sampling_unit: SamplingUnit
    selection_row_positions: list[int]
    inference_row_positions: list[int]
    inference_fold_by_row_position: dict[int, int]
    stratification_columns: list[str]
    input_order_sha256: str


def _effective_stratification_columns(project_spec: ProjectSpec) -> list[str]:
    columns = list(project_spec.split.stratification_columns)
    for node in project_spec.nodes:
        if node.outcome_type is OutcomeType.BINARY and node.node_id not in columns:
            columns.append(node.node_id)
    return columns


def _stratum_keys(data: pd.DataFrame, columns: list[str]) -> list[str]:
    if not columns:
        return ["__all__"] * len(data)
    if data[columns].isna().any().any():
        raise ValueError("Stratification columns contain missing values")
    return [
        json.dumps(tuple(row), ensure_ascii=False, default=str, separators=(",", ":"))
        for row in data[columns].itertuples(index=False, name=None)
    ]


def _units_by_stratum(
    data: pd.DataFrame, project_spec: ProjectSpec, stratum_keys: list[str]
) -> dict[str, list[list[int]]]:
    if project_spec.design.sampling_unit is SamplingUnit.IID:
        units: dict[str, list[list[int]]] = {}
        for position, stratum in enumerate(stratum_keys):
            units.setdefault(stratum, []).append([position])
        return units

    cluster_column = project_spec.design.cluster_id_column
    assert cluster_column is not None
    if data[cluster_column].isna().any():
        raise ValueError(f"Cluster identifier column '{cluster_column}' contains missing values")
    clusters: dict[str, list[int]] = {}
    for position, value in enumerate(data[cluster_column]):
        key = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
        clusters.setdefault(key, []).append(position)
    units = {}
    for cluster, positions in sorted(clusters.items()):
        cluster_strata = {stratum_keys[position] for position in positions}
        if len(cluster_strata) != 1:
            raise ValueError(f"Cluster {cluster} spans multiple strata and cannot be split safely")
        units.setdefault(cluster_strata.pop(), []).append(positions)
    return units


def _input_order_hash(data: pd.DataFrame) -> str:
    payload = {"index": data.index.tolist(), "columns": [str(column) for column in data.columns]}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def create_outer_split(data: pd.DataFrame, project_spec: ProjectSpec) -> SplitManifest:
    """Partition rows or clusters into a selection set and stratified inference folds."""

    columns = _effective_stratification_columns(project_spec)
    missing = sorted(set(columns) - set(data.columns))
    if missing:
        raise ValueError(f"Missing stratification columns: {', '.join(missing)}")
    if project_spec.design.cluster_id_column and project_spec.design.cluster_id_column not in data.columns:
        raise ValueError(f"Missing cluster identifier column: {project_spec.design.cluster_id_column}")

    units_by_stratum = _units_by_stratum(data, project_spec, _stratum_keys(data, columns))
    fold_count = project_spec.split.inference_folds
    if not units_by_stratum:
        raise ValueError("Cannot split an empty dataset")
    for stratum, units in units_by_stratum.items():
        if len(units) < fold_count + 1:
            raise ValueError(
                f"Stratum {stratum} is too small: need at least {fold_count + 1} sampling units"
            )

    rng = np.random.default_rng(project_spec.seed)
    selection_rows: list[int] = []
    fold_by_row: dict[int, int] = {}
    for units in units_by_stratum.values():
        shuffled = [units[index] for index in rng.permutation(len(units))]
        selection_count = max(1, round(len(units) * project_spec.split.selection_fraction))
        for unit in shuffled[:selection_count]:
            selection_rows.extend(unit)
        for index, unit in enumerate(shuffled[selection_count:]):
            for position in unit:
                fold_by_row[position] = index % fold_count

    selection = sorted(selection_rows)
    inference = sorted(fold_by_row)
    return SplitManifest(
        schema_version=SCHEMA_VERSION,
        analysis_id=str(project_spec.analysis_id),
        seed=project_spec.seed,
        selection_fraction=project_spec.split.selection_fraction,
        inference_folds=fold_count,
        sampling_unit=project_spec.design.sampling_unit,
        selection_row_positions=selection,
        inference_row_positions=inference,
        inference_fold_by_row_position=fold_by_row,
        stratification_columns=columns,
        input_order_sha256=_input_order_hash(data),
    )


def write_split_manifest(manifest: SplitManifest, output_dir: str | Path) -> Path:
    """Write a byte-stable split manifest using an atomic replacement."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / "split_manifest.json"
    payload = json.dumps(
        manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode() + b"\n"
    temporary = output_path.with_suffix(".json.tmp")
    temporary.write_bytes(payload)
    temporary.replace(output_path)
    return output_path
