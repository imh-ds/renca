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


class EvidenceBundleManifest(Model):
    """Stable provenance for a reviewable Phase-1 evidence bundle."""

    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    profile_id: str | None = None
    registry_sha256: str | None = None
    package_version: str
    input_sha256: str
    config_sha256: str


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


def write_evidence_bundle_manifest(analysis_manifest: AnalysisManifest, output_dir: str | Path, *, profile_id: str | None, registry_path: str | Path | None) -> Path:
    registry_hash = hashlib.sha256(Path(registry_path).read_bytes()).hexdigest() if registry_path is not None and Path(registry_path).is_file() else None
    bundle = EvidenceBundleManifest(analysis_id=analysis_manifest.analysis_id, profile_id=profile_id, registry_sha256=registry_hash, package_version=analysis_manifest.package_version, input_sha256=analysis_manifest.data_sha256, config_sha256=analysis_manifest.config_sha256)
    path = Path(output_dir) / "evidence_bundle_manifest.json"
    path.write_bytes(_canonical_bytes(bundle.model_dump(mode="json")))
    return path


def read_evidence_bundle_manifest(path: str | Path) -> EvidenceBundleManifest:
    """Read and validate a portable evidence-bundle provenance record."""
    return EvidenceBundleManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))
