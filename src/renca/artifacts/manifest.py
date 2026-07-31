"""Canonical audit artifact and manifest generation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import pandas as pd
from pydantic import Field

from renca.audit import AuditReport
from renca.models import Model, ProjectSpec, SCHEMA_VERSION


class AnalysisManifest(Model):
    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    config_sha256: str
    data_sha256: str
    preanalysis_reference_sha256: str
    seed: int
    package_version: str
    audit_eligible: bool


class RunReceipt(Model):
    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    created_at: str


class AuditArtifactPaths(Model):
    audit_json: Path
    manifest_json: Path
    run_receipt_json: Path


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def build_analysis_manifest(data: pd.DataFrame, project_spec: ProjectSpec, audit_report: AuditReport) -> AnalysisManifest:
    metadata = {"columns": [str(column) for column in data.columns], "dtypes": [str(dtype) for dtype in data.dtypes]}
    data_bytes = pd.util.hash_pandas_object(data, index=True).values.tobytes() + _canonical_bytes(metadata)
    config = project_spec.model_dump(mode="json")
    return AnalysisManifest(schema_version=SCHEMA_VERSION, analysis_id=str(project_spec.analysis_id), config_sha256=hashlib.sha256(_canonical_bytes(config)).hexdigest(), data_sha256=hashlib.sha256(data_bytes).hexdigest(), preanalysis_reference_sha256=hashlib.sha256(project_spec.preanalysis_reference.encode()).hexdigest(), seed=project_spec.seed, package_version=version("renca"), audit_eligible=audit_report.eligible)


def write_audit_artifacts(report: AuditReport, manifest: AnalysisManifest, output_dir: str | Path) -> AuditArtifactPaths:
    if not report.eligible:
        raise ValueError("Cannot write artifacts for a failed audit")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = AuditArtifactPaths(audit_json=destination / "audit.json", manifest_json=destination / "analysis_manifest.json", run_receipt_json=destination / "run_receipt.json")
    for path, value in ((paths.audit_json, report), (paths.manifest_json, manifest), (paths.run_receipt_json, RunReceipt(schema_version=SCHEMA_VERSION, analysis_id=report.analysis_id, created_at=datetime.now(timezone.utc).isoformat()))):
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(_canonical_bytes(value.model_dump(mode="json")))
        temporary.replace(path)
    return paths
