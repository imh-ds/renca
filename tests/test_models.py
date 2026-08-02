from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from renca.models import (
    ArtifactHeader,
    NodeSpec,
    ProjectSpec,
    load_project_spec,
    write_json_schemas,
)


def valid_project_payload() -> dict[str, object]:
    return {
        "schema_version": "1.7.0",
        "analysis_id": "dddb2c74-2a57-4561-8afc-2c56e086674b",
        "preanalysis_reference": "osf.io/example",
        "seed": 7,
        "missing_data_policy": "complete_case",
        "design": {"sampling_unit": "iid", "cluster_id_column": None},
        "split": {
            "selection_fraction": 0.2,
            "inference_folds": 5,
            "stratification_columns": [],
        },
        "audit": {"minimum_rows_per_inference_fold": 100, "minimum_clusters": 20},
        "screening": {"max_neighbors": 10, "max_separator_size": 1, "separators_per_pair": 1},
        "vimp": {"confidence_level": 0.95, "ridge_alpha": 1.0, "forest_trees": 100, "forest_max_depth": 5, "learner_library_version": "v2_quadratic_ridge"},
        "calibration": {"profile_id": None},
        "nodes": [
            {
                "node_id": "stress",
                "outcome_type": "continuous",
                "loss": "squared",
                "delta": 0.01,
                "minimum_standard_deviation": 1e-8,
                "measurement_level": "continuous",
                "scale_min": None,
                "scale_max": None,
                "continuous_approximation": False,
                "max_boundary_mass": 0.15,
                "minimum_distinct_values": 5,
            },
            {
                "node_id": "sleep_problem",
                "outcome_type": "binary",
                "loss": "brier",
                "delta": 0.02,
                "minimum_standard_deviation": 1e-8,
                "measurement_level": "continuous",
                "scale_min": None,
                "scale_max": None,
                "continuous_approximation": False,
                "max_boundary_mass": 0.15,
                "minimum_distinct_values": 5,
            },
        ],
    }


def test_valid_project_round_trips_and_validates_against_exported_schema(
    tmp_path: Path,
) -> None:
    payload = valid_project_payload()
    project = ProjectSpec.model_validate(payload)

    assert project.model_dump(mode="json") == payload
    assert project.nodes[0] == NodeSpec(**payload["nodes"][0])

    schema_paths = write_json_schemas(tmp_path)
    schema = json.loads(schema_paths["project"].read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(payload, schema)


@pytest.mark.parametrize(
    ("node_update", "expected_field"),
    [
        (None, "delta"),
        ({"delta": 0}, "delta"),
        ({"delta": -0.01}, "delta"),
        ({"delta": float("inf")}, "delta"),
        ({"outcome_type": "binary", "loss": "squared"}, "loss"),
        ({"outcome_type": "continuous", "loss": "brier"}, "loss"),
    ],
)
def test_node_contract_rejects_invalid_delta_or_loss_pairing(
    node_update: dict[str, object] | None, expected_field: str
) -> None:
    payload = valid_project_payload()["nodes"][0].copy()
    if node_update is None:
        payload.pop("delta")
    else:
        payload.update(node_update)

    with pytest.raises(ValidationError, match=expected_field):
        NodeSpec.model_validate(payload)


@pytest.mark.parametrize(
    ("project_update", "expected_field"),
    [
        ({"missing_data_policy": None}, "missing_data_policy"),
        ({"split": {"selection_fraction": 0, "inference_folds": 5}}, "selection_fraction"),
        ({"split": {"selection_fraction": 0.5, "inference_folds": 5}}, "selection_fraction"),
        ({"split": {"selection_fraction": 0.2, "inference_folds": 1}}, "inference_folds"),
    ],
)
def test_project_contract_rejects_invalid_analysis_settings(
    project_update: dict[str, object], expected_field: str
) -> None:
    payload = valid_project_payload()
    payload.update(project_update)

    with pytest.raises(ValidationError, match=expected_field):
        ProjectSpec.model_validate(payload)


def test_project_contract_rejects_duplicate_node_ids() -> None:
    payload = valid_project_payload()
    payload["nodes"].append(payload["nodes"][0].copy())

    with pytest.raises(ValidationError, match="node_id"):
        ProjectSpec.model_validate(payload)


def test_loader_reads_yaml_and_reports_yaml_parse_errors(tmp_path: Path) -> None:
    project_path = tmp_path / "project.yaml"
    project_path.write_text(
        "schema_version: 1.0.0\nanalysis_id: [not-valid\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Invalid YAML"):
        load_project_spec(project_path)


def test_loader_reads_a_valid_yaml_project(tmp_path: Path) -> None:
    project_path = tmp_path / "project.yaml"
    project_path.write_text(
        """\
schema_version: 1.7.0
analysis_id: dddb2c74-2a57-4561-8afc-2c56e086674b
preanalysis_reference: osf.io/example
seed: 7
missing_data_policy: complete_case
design:
  sampling_unit: iid
  cluster_id_column: null
nodes:
  - node_id: stress
    outcome_type: continuous
    loss: squared
    delta: 0.01
  - node_id: sleep_problem
    outcome_type: binary
    loss: brier
    delta: 0.02
""",
        encoding="utf-8",
    )

    project = load_project_spec(project_path)

    assert project.nodes[1].loss.value == "brier"


def test_schema_export_is_deterministic_and_artifact_headers_are_versioned(
    tmp_path: Path,
) -> None:
    first = write_json_schemas(tmp_path / "first")
    second = write_json_schemas(tmp_path / "second")

    assert first["project"].read_bytes() == second["project"].read_bytes()
    committed = Path(__file__).parents[1] / "schemas" / "project_spec.schema.json"
    assert first["project"].read_bytes() == committed.read_bytes()
    header = ArtifactHeader(
        schema_version="1.7.0",
        analysis_id="dddb2c74-2a57-4561-8afc-2c56e086674b",
        artifact_type="audit",
    )
    assert header.artifact_type == "audit"
