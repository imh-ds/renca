from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Literal
import yaml
from pydantic import Field
from renca.models import Model, VimpSpec

class CalibrationRecord(Model):
    scenario_family: str
    sample_size: int
    inference_folds: int
    vimp_fingerprint: str
    critical_value: float
    calibration_replications: int
    evaluation_replications: int
    empirical_rejection_rate: float
    upper_rejection_bound: float
    status: Literal["validated", "rejected"]

class CalibrationRegistry(Model):
    schema_version: Literal["1.0"] = "1.0"
    records: list[CalibrationRecord] = Field(default_factory=list)
    @classmethod
    def load(cls, path: str | Path) -> "CalibrationRegistry":
        return cls.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))

def vimp_fingerprint(spec: VimpSpec) -> str:
    return hashlib.sha256(json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def calibration_status(registry: CalibrationRegistry, scenario_family: str, sample_size: int, inference_folds: int, spec: VimpSpec, alpha: float = .05) -> Literal["calibrated_success", "uncalibrated", "calibration_failed"]:
    matches=[r for r in registry.records if r.scenario_family==scenario_family and r.sample_size==sample_size and r.inference_folds==inference_folds and r.vimp_fingerprint==vimp_fingerprint(spec)]
    if not matches: return "uncalibrated"
    record=matches[-1]
    if record.status=="validated" and record.calibration_replications>=5000 and record.evaluation_replications>=5000 and record.upper_rejection_bound<=alpha: return "calibrated_success"
    return "calibration_failed"
