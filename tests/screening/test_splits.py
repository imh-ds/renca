from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pandas as pd
import pytest

from renca.models import ProjectSpec, write_json_schemas
from renca.screening import create_outer_split, write_split_manifest


def project_spec(**updates: object) -> ProjectSpec:
    payload: dict[str, object] = {
        "schema_version": "1.6.0",
        "analysis_id": "dddb2c74-2a57-4561-8afc-2c56e086674b",
        "preanalysis_reference": "osf.io/example",
        "seed": 7,
        "missing_data_policy": "complete_case",
        "design": {"sampling_unit": "iid", "cluster_id_column": None},
        "split": {
            "selection_fraction": 0.2,
            "inference_folds": 5,
            "stratification_columns": ["site"],
        },
        "nodes": [
            {"node_id": "stress", "outcome_type": "continuous", "loss": "squared", "delta": 0.01},
            {"node_id": "sleep", "outcome_type": "binary", "loss": "brier", "delta": 0.01},
        ],
    }
    payload.update(updates)
    return ProjectSpec.model_validate(payload)


def iid_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "stress": list(range(24)),
            "sleep": [0] * 12 + [1] * 12,
            "site": ["north"] * 24,
        },
        index=[99] * 24,
    )


def test_iid_split_is_deterministic_disjoint_and_stratified() -> None:
    data = iid_data()
    manifest = create_outer_split(data, project_spec())

    assert manifest == create_outer_split(data, project_spec())
    assert set(manifest.selection_row_positions).isdisjoint(manifest.inference_row_positions)
    assert set(manifest.selection_row_positions) | set(manifest.inference_row_positions) == set(range(len(data)))
    assert set(manifest.inference_fold_by_row_position) == set(manifest.inference_row_positions)
    assert manifest.stratification_columns == ["site", "sleep"]
    for value in [0, 1]:
        rows = [position for position, outcome in enumerate(data.sleep) if outcome == value]
        selected = set(rows) & set(manifest.selection_row_positions)
        assert len(selected) == 2
        fold_counts = [
            sum(manifest.inference_fold_by_row_position.get(position) == fold for position in rows)
            for fold in range(5)
        ]
        assert fold_counts == [2] * 5


def test_clustered_split_keeps_clusters_within_one_partition_and_fold() -> None:
    clusters = [f"c{number}" for number in range(12) for _ in range(2)]
    data = pd.DataFrame(
        {"stress": list(range(24)), "sleep": [number % 2 for number in range(12) for _ in range(2)], "site": ["north"] * 24, "cluster": clusters}
    )
    spec = project_spec(design={"sampling_unit": "clustered", "cluster_id_column": "cluster"})

    manifest = create_outer_split(data, spec)

    selection = set(manifest.selection_row_positions)
    for _, positions in data.groupby("cluster", sort=False).indices.items():
        rows = set(positions.tolist())
        assert rows <= selection or rows.isdisjoint(selection)
        folds = {manifest.inference_fold_by_row_position[position] for position in rows if position not in selection}
        assert len(folds) <= 1


@pytest.mark.parametrize(
    ("data", "spec", "message"),
    [
        (iid_data().drop(columns="site"), project_spec(), "Missing stratification columns"),
        (iid_data().iloc[:5], project_spec(), "too small"),
        (iid_data().assign(cluster=[None] * 24), project_spec(design={"sampling_unit": "clustered", "cluster_id_column": "cluster"}), "missing values"),
    ],
)
def test_split_rejects_invalid_sampling_inputs(data: pd.DataFrame, spec: ProjectSpec, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        create_outer_split(data, spec)


def test_clustered_split_rejects_cluster_that_crosses_a_stratum() -> None:
    data = iid_data().assign(cluster=["mixed"] * 2 + [f"c{number}" for number in range(2, 24)])
    data.iloc[0, data.columns.get_loc("sleep")] = 0
    data.iloc[1, data.columns.get_loc("sleep")] = 1
    spec = project_spec(design={"sampling_unit": "clustered", "cluster_id_column": "cluster"})

    with pytest.raises(ValueError, match="multiple strata"):
        create_outer_split(data, spec)


def test_manifest_json_is_canonical_and_matches_exported_schema(tmp_path: Path) -> None:
    manifest = create_outer_split(iid_data(), project_spec())
    first = write_split_manifest(manifest, tmp_path / "first")
    second = write_split_manifest(manifest, tmp_path / "second")
    schema = json.loads(write_json_schemas(tmp_path / "schemas")["split_manifest"].read_text())

    assert first.name == "split_manifest.json"
    assert first.read_bytes() == second.read_bytes()
    jsonschema.validate(json.loads(first.read_text()), schema)
    changed_seed = project_spec(seed=8)
    assert create_outer_split(iid_data(), changed_seed) != manifest
