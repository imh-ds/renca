from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from renca.models import ProjectSpec, ScreeningSpec, write_json_schemas
from renca.screening import (
    create_outer_split,
    rank_separators,
    screen_neighbors,
    write_separator_candidates,
)


def project_spec(**updates: object) -> ProjectSpec:
    payload: dict[str, object] = {
        "schema_version": "1.7.0",
        "analysis_id": "dddb2c74-2a57-4561-8afc-2c56e086674b",
        "preanalysis_reference": "osf.io/example",
        "seed": 23,
        "missing_data_policy": "complete_case",
        "design": {"sampling_unit": "iid", "cluster_id_column": None},
        "split": {"selection_fraction": 0.25, "inference_folds": 3},
        "screening": {"max_neighbors": 2, "max_separator_size": 1, "separators_per_pair": 1},
        "nodes": [
            {"node_id": "x", "outcome_type": "continuous", "loss": "squared", "delta": 0.01},
            {"node_id": "y", "outcome_type": "continuous", "loss": "squared", "delta": 0.01},
            {"node_id": "z", "outcome_type": "continuous", "loss": "squared", "delta": 0.01},
            {"node_id": "noise", "outcome_type": "continuous", "loss": "squared", "delta": 0.01},
        ],
    }
    payload.update(updates)
    return ProjectSpec.model_validate(payload)


def selection_data() -> pd.DataFrame:
    values = list(range(60))
    z = [(value % 11) / 10 for value in values]
    return pd.DataFrame(
        {
            "x": [value + ((index % 3) - 1) * 0.01 for index, value in enumerate(z)],
            "y": [value + ((index % 5) - 2) * 0.01 for index, value in enumerate(z)],
            "z": z,
            "noise": [((index * 7) % 13) / 13 for index in values],
        }
    )


def test_screening_is_deterministic_and_respects_neighbor_limit() -> None:
    spec = project_spec()
    neighborhoods = screen_neighbors(selection_data(), spec.nodes, spec.screening, seed=spec.seed)

    assert neighborhoods == screen_neighbors(selection_data(), spec.nodes, spec.screening, seed=spec.seed)
    assert set(neighborhoods) == {"x", "y", "z", "noise"}
    assert all(len(neighbors) <= 2 for neighbors in neighborhoods.values())
    assert "z" in neighborhoods["x"]


def test_ranked_separator_selection_uses_only_selection_rows_and_is_deterministic() -> None:
    spec = project_spec()
    data = selection_data()
    split = create_outer_split(data, spec)
    selected = data.iloc[split.selection_row_positions]
    neighborhoods = screen_neighbors(selected, spec.nodes, spec.screening, seed=spec.seed)
    first = rank_separators(selected, spec.nodes, neighborhoods, spec.screening, seed=spec.seed)
    changed_inference = data.copy()
    changed_inference.iloc[split.inference_row_positions] = -999.0
    second = rank_separators(
        changed_inference.iloc[split.selection_row_positions], spec.nodes, neighborhoods, spec.screening, seed=spec.seed
    )

    assert first == second
    assert all(candidate.rank == 1 for candidate in first)
    assert all(candidate.selection_method == "cross_fitted_bidirectional_loss" for candidate in first)


def test_separator_artifact_has_required_columns_and_schema(tmp_path: Path) -> None:
    spec = project_spec()
    data = selection_data()
    neighborhoods = screen_neighbors(data, spec.nodes, spec.screening, seed=spec.seed)
    candidates = rank_separators(data, spec.nodes, neighborhoods, spec.screening, seed=spec.seed)
    path = write_separator_candidates(candidates, tmp_path)
    artifact = pd.read_parquet(path)
    schema = json.loads(write_json_schemas(tmp_path / "schemas")["separator_candidate"].read_text())

    assert path.name == "separator_candidates.parquet"
    assert set(artifact.columns) == {
        "pair_id", "node_i", "node_j", "rank", "separator", "selection_score", "selection_method", "admissibility_flags"
    }
    assert len(artifact) == 6
    assert all(json.loads(value) == [] or isinstance(json.loads(value), list) for value in artifact["separator"])
    assert schema["title"] == "SeparatorCandidate"


def test_screening_contract_rejects_invalid_settings() -> None:
    with pytest.raises(ValueError, match="max_neighbors"):
        ScreeningSpec(max_neighbors=0)
    with pytest.raises(ValueError, match="separators_per_pair"):
        ScreeningSpec(max_separator_size=1, separators_per_pair=3)
