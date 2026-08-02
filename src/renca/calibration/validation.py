"""Independent-grid acceptance summaries for calibration evidence."""
from __future__ import annotations
import pandas as pd
from scipy.stats import beta
from renca.calibration.registry import CalibrationRecord

def validate_grid(results: pd.DataFrame, *, scenario_family: str, sample_size: int, inference_folds: int, vimp_fingerprint: str, critical_value: float, alpha: float = .05) -> CalibrationRecord:
    """Require 5,000 independent evaluations and a one-sided 95% binomial upper bound."""
    if set(results.columns) < {"replicate", "reject"}: raise ValueError("results require replicate and reject columns")
    if results.replicate.duplicated().any(): raise ValueError("replicates must be independent and unique")
    n=len(results); rejects=int(results.reject.sum()); upper=float(beta.ppf(.95,rejects+1,n-rejects))
    return CalibrationRecord(scenario_family=scenario_family,sample_size=sample_size,inference_folds=inference_folds,vimp_fingerprint=vimp_fingerprint,critical_value=critical_value,calibration_replications=n,evaluation_replications=n,empirical_rejection_rate=rejects/n,upper_rejection_bound=upper,status="validated" if n>=5000 and upper<=alpha else "rejected")
