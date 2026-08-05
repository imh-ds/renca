"""Versioned, exact-match simulation calibration profiles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import pandas as pd
import yaml
from pydantic import Field

from renca.models import Model, VimpSpec


class CalibrationRecord(Model):
    profile_id: str
    scenario_family: str
    delta_target: float
    inference_rows: int
    inference_folds: int
    vimp_fingerprint: str
    alpha: float = .05
    critical_value: float
    critical_quantile: float = .05  # legacy records predate the field and used alpha
    distribution_file: str = ""
    distribution_sha256: str = ""
    calibration_replications: int
    calibration_successful_replications_per_family: dict[str, int] = Field(default_factory=dict)
    evaluation_replications: int
    empirical_rejection_rate: float
    upper_rejection_bound: float
    validation_scenario_families: list[str] = Field(default_factory=list)
    validation_replications_per_family: dict[str, int] = Field(default_factory=dict)
    grid_rejection_rates: dict[str, float] = Field(default_factory=dict)
    grid_upper_rejection_bounds: dict[str, float] = Field(default_factory=dict)
    grid_ineligibility_rates: dict[str, float] = Field(default_factory=dict)
    status: Literal["validated", "rejected"]


class CalibrationRegistry(Model):
    schema_version: Literal["2.0"] = "2.0"
    records: list[CalibrationRecord] = Field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationRegistry":
        return cls.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


class CalibrationEligibility(Model):
    """Auditable result of binding an analysis to one calibration profile."""

    requested_profile_id: str | None = None
    matched_profile_id: str | None = None
    delta_target: float | None = None
    status: Literal["calibrated_success", "uncalibrated", "calibration_failed"]
    mismatch_fields: list[str] = Field(default_factory=list)
    message: str


def vimp_fingerprint(spec: VimpSpec) -> str:
    payload = json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def calibration_status(registry: CalibrationRegistry, *, profile_id: str | None, delta_target: float, inference_rows: int, inference_folds: int, spec: VimpSpec, alpha: float = .05) -> Literal["calibrated_success", "uncalibrated", "calibration_failed"]:
    return calibration_eligibility(registry, profile_id=profile_id, delta_target=delta_target, inference_rows=inference_rows, inference_folds=inference_folds, spec=spec, alpha=alpha).status


def calibration_eligibility(registry: CalibrationRegistry, *, profile_id: str | None, delta_target: float, inference_rows: int, inference_folds: int, spec: VimpSpec, alpha: float = .05, distribution_ok: bool = True) -> CalibrationEligibility:
    """Explain the strict gate without weakening it or accepting near-matches."""
    if profile_id is None:
        return CalibrationEligibility(delta_target=delta_target, status="uncalibrated", message="No calibration profile was requested; hard certification is unavailable.")
    matches = [record for record in registry.records if record.profile_id == profile_id]
    if len(matches) != 1:
        return CalibrationEligibility(requested_profile_id=profile_id, delta_target=delta_target, status="calibration_failed", mismatch_fields=["profile_id"], message="The requested calibration profile is absent or ambiguous in the registry.")
    record = matches[0]
    mismatch_fields: list[str] = []
    if record.delta_target != delta_target:
        mismatch_fields.append("delta_target")
    if record.inference_rows != inference_rows:
        mismatch_fields.append("inference_rows")
    if record.inference_folds != inference_folds:
        mismatch_fields.append("inference_folds")
    if record.vimp_fingerprint != vimp_fingerprint(spec):
        mismatch_fields.append("vimp_fingerprint")
    if record.alpha != alpha:
        mismatch_fields.append("alpha")
    required = set(record.validation_scenario_families)
    grid_is_sufficient = bool(required) and all(record.validation_replications_per_family.get(family, 0) >= 5000 and record.calibration_successful_replications_per_family.get(family, 0) >= 5000 and record.grid_upper_rejection_bounds.get(family, float("inf")) <= record.alpha for family in required)
    artifact_ok = bool(record.distribution_file and record.distribution_sha256) and distribution_ok
    if not artifact_ok:
        mismatch_fields.append("distribution_artifact")
    if record.status != "validated":
        mismatch_fields.append("profile_status")
    if record.calibration_replications < 5000 or record.evaluation_replications < 5000 or record.upper_rejection_bound > record.alpha or not grid_is_sufficient:
        mismatch_fields.append("validation_evidence")
    if not mismatch_fields:
        return CalibrationEligibility(requested_profile_id=profile_id, matched_profile_id=record.profile_id, delta_target=delta_target, status="calibrated_success", message="The requested profile exactly matches this analysis; calibrated certification is permitted.")
    return CalibrationEligibility(requested_profile_id=profile_id, matched_profile_id=record.profile_id, delta_target=delta_target, status="calibration_failed", mismatch_fields=mismatch_fields, message="Calibrated certification is unavailable because: " + ", ".join(mismatch_fields) + ".")


def calibrated_p_value(statistic: float, record: CalibrationRecord, distribution: pd.DataFrame) -> float:
    """Conservative worst-family left-tail p-value with plus-one smoothing."""
    if not record.validation_scenario_families:
        raise ValueError("calibration profile has no validation scenario families")
    required = {"scenario_family", "studentized_statistic"}
    if not required <= set(distribution.columns):
        raise ValueError("calibration distribution is missing required columns")
    values: list[float] = []
    for family in record.validation_scenario_families:
        tail = distribution.loc[distribution.scenario_family == family, "studentized_statistic"].dropna()
        if len(tail) == 0:
            raise ValueError(f"calibration distribution has no values for {family}")
        values.append((int((tail <= statistic).sum()) + 1) / (len(tail) + 1))
    return float(max(values))


def load_distribution(record: CalibrationRecord, registry_path: str | Path) -> pd.DataFrame:
    path = Path(registry_path).parent / record.distribution_file
    if not path.is_file() or file_sha256(path) != record.distribution_sha256:
        raise ValueError("calibration distribution artifact is missing or has an unexpected SHA-256")
    return pd.read_parquet(path)
