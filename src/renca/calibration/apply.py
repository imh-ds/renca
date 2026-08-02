"""Apply an exact validated calibration profile to VIMP evidence."""

from __future__ import annotations

from pathlib import Path

from renca.calibration.registry import CalibrationRegistry, calibrated_p_value, calibration_status, load_distribution
from renca.models import VimpSpec
from renca.vimp import VimpEstimate


def apply_profile(estimates: list[VimpEstimate], *, registry: CalibrationRegistry, registry_path: str | Path, profile_id: str | None, inference_rows: int, inference_folds: int, vimp_spec: VimpSpec) -> list[VimpEstimate]:
    """Return evidence with calibrated p-values only under an exact valid profile."""
    profiles = {record.profile_id: record for record in registry.records}
    record = profiles.get(profile_id) if profile_id else None
    distribution = None
    if record is not None:
        try:
            distribution = load_distribution(record, registry_path)
        except ValueError:
            distribution = None
    output: list[VimpEstimate] = []
    for estimate in estimates:
        status = calibration_status(registry, profile_id=profile_id, delta_target=estimate.delta_target, inference_rows=inference_rows, inference_folds=inference_folds, spec=vimp_spec)
        if status == "calibrated_success" and distribution is not None and estimate.theta_hat is not None and estimate.se_theta is not None and estimate.se_theta > 0 and estimate.status == "success":
            statistic = (estimate.theta_hat - estimate.delta_target) / estimate.se_theta
            output.append(estimate.model_copy(update={"calibration_status": status, "p_equivalence": calibrated_p_value(statistic, record, distribution)}))
        else:
            output.append(estimate.model_copy(update={"calibration_status": "calibration_failed" if profile_id and status != "uncalibrated" else status, "p_equivalence": None}))
    return output
