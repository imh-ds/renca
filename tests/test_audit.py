from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from renca.artifacts.manifest import build_analysis_manifest, write_audit_artifacts
from renca.audit import audit_project
from renca.models import ProjectSpec


def project_spec(**updates: object) -> ProjectSpec:
    payload: dict[str, object] = {
        "schema_version": "1.4.0",
        "analysis_id": "dddb2c74-2a57-4561-8afc-2c56e086674b",
        "preanalysis_reference": "osf.io/example",
        "seed": 7,
        "missing_data_policy": "complete_case",
        "design": {"sampling_unit": "iid", "cluster_id_column": None},
        "split": {"selection_fraction": 0.2, "inference_folds": 2},
        "audit": {"minimum_rows_per_inference_fold": 2, "minimum_clusters": 2},
        "nodes": [
            {"node_id": "stress", "outcome_type": "continuous", "loss": "squared", "delta": 0.01},
            {"node_id": "sleep", "outcome_type": "binary", "loss": "brier", "delta": 0.01},
        ],
    }
    payload.update(updates)
    return ProjectSpec.model_validate(payload)


def valid_data() -> pd.DataFrame:
    return pd.DataFrame({"stress": [1.0, 2.0, 3.0, 4.0], "sleep": [0, 1, 0, 1]})


def test_audit_passes_valid_data_and_writes_deterministic_artifacts(tmp_path: Path) -> None:
    spec = project_spec()
    report = audit_project(valid_data(), spec)
    manifest = build_analysis_manifest(valid_data(), spec, report)

    assert report.eligible is True
    assert report.analysis_row_count == 4
    assert report.excluded_row_count == 0
    paths = write_audit_artifacts(report, manifest, tmp_path)
    assert json.loads(paths.audit_json.read_text())["eligible"] is True
    assert paths.manifest_json.read_bytes() == write_audit_artifacts(report, manifest, tmp_path).manifest_json.read_bytes()


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (pd.DataFrame({"stress": [1.0, 2.0, 3.0, 4.0]}), "missing_columns"),
        (pd.DataFrame({"stress": [1.0, 2.0, 3.0, 4.0], "sleep": [0, 1, 0, 1], "extra": [1, 2, 3, 4]}), "unknown_columns"),
        (pd.DataFrame({"stress": [1.0, 1.0, 1.0, 1.0], "sleep": [0, 1, 0, 1]}), "near_zero_variance"),
        (pd.DataFrame({"stress": [1.0, 2.0, float("inf"), 4.0], "sleep": [0, 1, 0, 1]}), "nonfinite_values"),
    ],
)
def test_audit_reports_data_failures(data: pd.DataFrame, reason: str) -> None:
    report = audit_project(data, project_spec())
    assert report.eligible is False
    assert any(check.code == reason and check.status == "fail" for check in report.checks)


def test_clustered_design_is_audited_but_vimp_is_disabled() -> None:
    spec = project_spec(design={"sampling_unit": "clustered", "cluster_id_column": "cluster"})
    data = valid_data().assign(cluster=["a", "a", "b", "b"])

    report = audit_project(data, spec)

    assert report.eligible is True
    assert "confirmatory_vimp" in report.disabled_modules


def test_manifest_hash_changes_when_data_or_provenance_changes() -> None:
    spec = project_spec()
    report = audit_project(valid_data(), spec)
    first = build_analysis_manifest(valid_data(), spec, report)
    changed_data = build_analysis_manifest(valid_data().assign(stress=[4.0, 3.0, 2.0, 1.0]), spec, report)
    changed_spec = project_spec(preanalysis_reference="doi:10.0000/example")
    changed_provenance = build_analysis_manifest(valid_data(), changed_spec, audit_project(valid_data(), changed_spec))

    assert first.data_sha256 != changed_data.data_sha256
    assert first.preanalysis_reference_sha256 != changed_provenance.preanalysis_reference_sha256


def test_artifact_writer_refuses_failed_audit(tmp_path: Path) -> None:
    spec = project_spec()
    report = audit_project(valid_data().assign(stress=[1.0] * 4), spec)

    with pytest.raises(ValueError, match="failed audit"):
        write_audit_artifacts(report, build_analysis_manifest(valid_data(), spec, report), tmp_path)
