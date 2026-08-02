"""Independent-grid acceptance summaries for calibration evidence."""
from __future__ import annotations
import pandas as pd
from scipy.stats import beta
from renca.calibration.registry import CalibrationRecord

REQUIRED_SCENARIO_FAMILIES = (
    "continuous_linear_boundary_v1",
    "bounded_composite_unsaturated_v1",
    "bounded_composite_saturated_v1",
    "nonlinear_continuous_v1",
    "learner_misspecification_v1",
)

def validate_grid(results: pd.DataFrame, *, scenario_family: str, sample_size: int, inference_folds: int, vimp_fingerprint: str, critical_value: float, calibration_replications: int | None = None, required_scenario_families: tuple[str, ...] = REQUIRED_SCENARIO_FAMILIES, alpha: float = .05) -> CalibrationRecord:
    """Summarize an independent scenario grid; only 5,000-per-family evidence can validate it."""
    if set(results.columns) < {"replicate", "reject"}: raise ValueError("results require replicate and reject columns")
    frame = results.copy()
    if "scenario_family" not in frame:
        frame["scenario_family"] = scenario_family
    if frame.duplicated(["scenario_family", "replicate"]).any():
        raise ValueError("replicates must be independent and unique within each scenario family")
    families = tuple(required_scenario_families)
    missing = set(families) - set(frame.scenario_family)
    if missing:
        raise ValueError(f"missing required scenario families: {', '.join(sorted(missing))}")
    counts: dict[str, int] = {}; rates: dict[str, float] = {}; uppers: dict[str, float] = {}
    for family in families:
        subset = frame.loc[frame.scenario_family == family]
        n = len(subset); rejects = int(subset.reject.sum())
        counts[family] = n; rates[family] = rejects / n
        uppers[family] = float(beta.ppf(.95, rejects + 1, n - rejects))
    primary_n = counts[scenario_family]
    calibrated_n = calibration_replications if calibration_replications is not None else primary_n
    valid = calibrated_n >= 5000 and all(counts[f] >= 5000 and uppers[f] <= alpha for f in families)
    return CalibrationRecord(scenario_family=scenario_family,sample_size=sample_size,inference_folds=inference_folds,vimp_fingerprint=vimp_fingerprint,critical_value=critical_value,calibration_replications=calibrated_n,evaluation_replications=primary_n,empirical_rejection_rate=rates[scenario_family],upper_rejection_bound=uppers[scenario_family],validation_scenario_families=list(families),validation_replications_per_family=counts,grid_rejection_rates=rates,grid_upper_rejection_bounds=uppers,status="validated" if valid else "rejected")
