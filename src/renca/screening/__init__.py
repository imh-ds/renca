"""Deterministic selection and inference splitting."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
from pydantic import Field

from renca.models import Model, ProjectSpec, SCHEMA_VERSION


class SplitManifest(Model):
    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    seed: int
    selection_fraction: float
    inference_folds: int
    selection_row_positions: list[int]
    inference_row_positions: list[int]
    inference_fold_by_row_position: dict[int, int]
    stratification_columns: list[str] = Field(default_factory=list)
    input_order_sha256: str


def create_outer_split(data: pd.DataFrame, project_spec: ProjectSpec) -> SplitManifest:
    columns = project_spec.split.stratification_columns
    missing = sorted(set(columns) - set(data.columns))
    if missing:
        raise ValueError(f"Missing stratification columns: {', '.join(missing)}")
    n = len(data)
    if n < project_spec.split.inference_folds + 1:
        raise ValueError("Not enough rows for selection and inference folds")
    rng = np.random.default_rng(project_spec.seed)
    groups = [np.arange(n)]
    if columns:
        labels = data[columns].astype(str).agg("|".join, axis=1)
        groups = [np.flatnonzero(labels.to_numpy() == value) for value in sorted(labels.unique())]
        if any(len(group) < project_spec.split.inference_folds + 1 for group in groups):
            raise ValueError("A stratum is too small for selection and inference folds")
    selection: list[int] = []
    for group in groups:
        shuffled = rng.permutation(group)
        count = max(1, round(len(group) * project_spec.split.selection_fraction))
        selection.extend(shuffled[:count].tolist())
    selection_set = set(selection)
    inference = [position for position in range(n) if position not in selection_set]
    shuffled_inference = rng.permutation(inference)
    folds = {int(position): int(index % project_spec.split.inference_folds) for index, position in enumerate(shuffled_inference)}
    order = json.dumps({"index": data.index.tolist(), "columns": data.columns.tolist()}, sort_keys=True, default=str).encode()
    return SplitManifest(schema_version=SCHEMA_VERSION, analysis_id=str(project_spec.analysis_id), seed=project_spec.seed, selection_fraction=project_spec.split.selection_fraction, inference_folds=project_spec.split.inference_folds, selection_row_positions=sorted(selection), inference_row_positions=inference, inference_fold_by_row_position=folds, stratification_columns=columns, input_order_sha256=hashlib.sha256(order).hexdigest())
