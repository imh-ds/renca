"""Data audit gate for predeclared analyses."""

from __future__ import annotations

from enum import StrEnum
from math import isfinite

import pandas as pd
from pydantic import Field

from renca.models import Model, MissingDataPolicy, ProjectSpec, SCHEMA_VERSION


class CheckStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class AuditCheck(Model):
    code: str
    status: CheckStatus
    message: str


class AuditReport(Model):
    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    eligible: bool
    analysis_row_count: int
    excluded_row_count: int
    checks: list[AuditCheck]
    disabled_modules: list[str] = Field(default_factory=list)


def audit_project(data: pd.DataFrame, project_spec: ProjectSpec) -> AuditReport:
    """Audit a DataFrame without mutating it."""
    checks: list[AuditCheck] = []
    expected = {node.node_id for node in project_spec.nodes}
    expected.update(project_spec.split.stratification_columns)
    if project_spec.design.cluster_id_column:
        expected.add(project_spec.design.cluster_id_column)
    columns = list(data.columns)
    missing = sorted(expected - set(columns))
    unknown = sorted(set(columns) - expected)
    if data.columns.duplicated().any():
        checks.append(AuditCheck(code="duplicate_columns", status="fail", message="DataFrame columns must be unique"))
    if missing:
        checks.append(AuditCheck(code="missing_columns", status="fail", message=f"Missing columns: {', '.join(missing)}"))
    if unknown:
        checks.append(AuditCheck(code="unknown_columns", status="fail", message=f"Unknown columns: {', '.join(unknown)}"))
    available_nodes = [node for node in project_spec.nodes if node.node_id in data.columns]
    nonfinite = False
    for node in available_nodes:
        values = pd.to_numeric(data[node.node_id], errors="coerce")
        finite_values = values.dropna().loc[values.dropna().map(lambda value: isfinite(float(value)))]
        if values.notna().any() and len(finite_values) != len(values.dropna()):
            nonfinite = True
        if node.outcome_type.value == "binary" and not values.dropna().isin([0, 1]).all():
            checks.append(AuditCheck(code="node_type", status="fail", message=f"{node.node_id} must contain binary 0/1 values"))
        if not finite_values.empty and finite_values.std(ddof=0) <= node.minimum_standard_deviation:
            checks.append(AuditCheck(code="near_zero_variance", status="fail", message=f"{node.node_id} is below its standard-deviation floor"))
    if nonfinite:
        checks.append(AuditCheck(code="nonfinite_values", status="fail", message="Node columns contain nonfinite values"))
    required = [node.node_id for node in available_nodes]
    complete_rows = data[required].notna().all(axis=1) if required else pd.Series(False, index=data.index)
    analysis_rows = int(complete_rows.sum())
    excluded = len(data) - analysis_rows
    if project_spec.missing_data_policy is not MissingDataPolicy.COMPLETE_CASE:
        checks.append(AuditCheck(code="missing_policy_unsupported", status="fail", message="Only complete_case is executable"))
    required_rows = project_spec.audit.minimum_rows_per_inference_fold * project_spec.split.inference_folds
    if analysis_rows < required_rows:
        checks.append(AuditCheck(code="insufficient_effective_sample_size", status="fail", message=f"Need at least {required_rows} complete rows"))
    for node in available_nodes:
        if node.outcome_type.value == "binary":
            values = data.loc[complete_rows, node.node_id]
            if values.value_counts().min() < project_spec.split.inference_folds:
                checks.append(AuditCheck(code="binary_class_feasibility", status="fail", message=f"{node.node_id} lacks observations for every fold"))
    disabled: list[str] = []
    if project_spec.design.sampling_unit.value == "clustered":
        clusters = data.loc[complete_rows, project_spec.design.cluster_id_column].nunique()
        if clusters < project_spec.audit.minimum_clusters:
            checks.append(AuditCheck(code="insufficient_clusters", status="fail", message="Too few clusters"))
        disabled.append("confirmatory_vimp")
        checks.append(AuditCheck(code="clustered_vimp_unsupported", status="warning", message="Cluster-robust VIMP is not implemented"))
    if not checks:
        checks.append(AuditCheck(code="audit_complete", status="pass", message="Audit passed"))
    return AuditReport(schema_version=SCHEMA_VERSION, analysis_id=str(project_spec.analysis_id), eligible=not any(check.status is CheckStatus.FAIL for check in checks), analysis_row_count=analysis_rows, excluded_row_count=excluded, checks=checks, disabled_modules=disabled)
