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

CRITICAL_QUANTILE = .04
"""Training quantile setting the critical value; deliberately below `alpha`.

The family attaining the minimum quantile is later validated against that same value on
independent draws from its own distribution, so its rejection rate targets this quantile.
At `alpha` exactly, the observed rate sits on `alpha` and its 95% upper bound exceeds it
about half the time, which `validate_grid` rejects. The 2026-08-05 Phase-0 rerun failed
that way: the previous profile had only cleared the bar because abstention removed 14.3%
of that family's replications, and the section 16.4 materiality safeguard stopped
supplying that margin. Reducing the quantile buys the margin explicitly instead.
"""


def critical_value_from_training(eligible: "pd.DataFrame", quantile: float = CRITICAL_QUANTILE) -> float:
    """Most extreme per-family lower quantile of the studentized statistic."""
    return float(min(
        eligible.loc[eligible.scenario_family == family, "studentized_statistic"].dropna().quantile(quantile, interpolation="lower")
        for family in REQUIRED_SCENARIO_FAMILIES
    ))

def validate_grid(results: pd.DataFrame, *, profile_id: str, scenario_family: str, delta_target: float, inference_rows: int, inference_folds: int, vimp_fingerprint: str, critical_value: float, critical_quantile: float = CRITICAL_QUANTILE, distribution_file: str = "", distribution_sha256: str = "", calibration_replications: int | None = None, calibration_successful_replications_per_family: dict[str, int] | None = None, required_scenario_families: tuple[str, ...] = REQUIRED_SCENARIO_FAMILIES, alpha: float = .05) -> CalibrationRecord:
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
    counts: dict[str, int] = {}; rates: dict[str, float] = {}; uppers: dict[str, float] = {}; ineligible: dict[str, float] = {}
    for family in families:
        subset = frame.loc[frame.scenario_family == family]
        n = len(subset); rejects = int(subset.reject.sum())
        counts[family] = n; rates[family] = rejects / n
        uppers[family] = float(beta.ppf(.95, rejects + 1, n - rejects))
        ineligible[family] = float((subset.get("status", pd.Series("success", index=subset.index)) != "success").mean())
    primary_n = counts[scenario_family]
    calibrated_n = calibration_replications if calibration_replications is not None else primary_n
    successful = calibration_successful_replications_per_family or {family: calibrated_n for family in families}
    valid = calibrated_n >= 5000 and all(counts[f] >= 5000 and successful.get(f, 0) >= 5000 and uppers[f] <= alpha for f in families)
    return CalibrationRecord(profile_id=profile_id,scenario_family=scenario_family,delta_target=delta_target,inference_rows=inference_rows,inference_folds=inference_folds,vimp_fingerprint=vimp_fingerprint,alpha=alpha,critical_value=critical_value,critical_quantile=critical_quantile,distribution_file=distribution_file,distribution_sha256=distribution_sha256,calibration_replications=calibrated_n,calibration_successful_replications_per_family=successful,evaluation_replications=primary_n,empirical_rejection_rate=rates[scenario_family],upper_rejection_bound=uppers[scenario_family],validation_scenario_families=list(families),validation_replications_per_family=counts,grid_rejection_rates=rates,grid_upper_rejection_bounds=uppers,grid_ineligibility_rates=ineligible,status="validated" if valid else "rejected")
