"""Apply an exact validated calibration profile to VIMP evidence."""

from __future__ import annotations

from pathlib import Path

from renca.calibration.registry import CalibrationEligibility, CalibrationRegistry, calibrated_p_value, calibration_eligibility, load_distribution
from renca.models import VimpSpec
from renca.vimp import VimpEstimate


def apply_profile(estimates: list[VimpEstimate], *, registry: CalibrationRegistry, registry_path: str | Path, profile_id: str | None, inference_rows: int, inference_folds: int, vimp_spec: VimpSpec, return_eligibility: bool = False) -> list[VimpEstimate] | tuple[list[VimpEstimate], list[CalibrationEligibility]]:
    """Return evidence with calibrated p-values only under an exact valid profile."""
    profiles = {record.profile_id: record for record in registry.records}
    record = profiles.get(profile_id) if profile_id else None
    distribution = None
    distribution_ok = True
    if record is not None:
        try:
            distribution = load_distribution(record, registry_path)
        except ValueError:
            distribution = None
            distribution_ok = False
    output: list[VimpEstimate] = []
    eligibility_by_delta: dict[float, CalibrationEligibility] = {}
    for estimate in estimates:
        eligibility = eligibility_by_delta.setdefault(estimate.delta_target, calibration_eligibility(registry, profile_id=profile_id, delta_target=estimate.delta_target, inference_rows=inference_rows, inference_folds=inference_folds, spec=vimp_spec, distribution_ok=distribution_ok))
        status = eligibility.status
        if status == "calibrated_success" and distribution is not None and estimate.theta_hat is not None and estimate.se_theta is not None and estimate.se_theta > 0 and estimate.status == "success":
            statistic = (estimate.theta_hat - estimate.delta_target) / estimate.se_theta
            output.append(estimate.model_copy(update={"calibration_status": status, "p_equivalence": calibrated_p_value(statistic, record, distribution)}))
        else:
            output.append(estimate.model_copy(update={"calibration_status": "calibration_failed" if profile_id and status != "uncalibrated" else status, "p_equivalence": None}))
    eligibility = list(eligibility_by_delta.values())
    return (output, eligibility) if return_eligibility else output
