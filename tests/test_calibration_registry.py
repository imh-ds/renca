from pathlib import Path
import pandas as pd
import pytest

from renca.calibration import CalibrationRecord, CalibrationRegistry, REQUIRED_SCENARIO_FAMILIES, calibration_status, run_independent_grid, validate_grid, vimp_fingerprint
from renca.models import VimpSpec

def test_gate_requires_exact_binding_and_formal_evidence() -> None:
    spec=VimpSpec(); families=list(REQUIRED_SCENARIO_FAMILIES); record=CalibrationRecord(scenario_family="linear",sample_size=300,inference_folds=5,vimp_fingerprint=vimp_fingerprint(spec),critical_value=-2.,calibration_replications=5000,evaluation_replications=5000,empirical_rejection_rate=.04,upper_rejection_bound=.049,validation_scenario_families=families,validation_replications_per_family={family: 5000 for family in families},grid_upper_rejection_bounds={family: .049 for family in families},status="validated")
    registry=CalibrationRegistry(records=[record])
    assert calibration_status(registry,"linear",300,5,spec)=="calibrated_success"
    assert calibration_status(registry,"bounded",300,5,spec)=="uncalibrated"
    registry.records[0].upper_rejection_bound=.06
    assert calibration_status(registry,"linear",300,5,spec)=="calibration_failed"


def test_grid_requires_all_families_and_never_validates_a_smoke_run() -> None:
    rows = pd.DataFrame([{"scenario_family": family, "replicate": 0, "reject": False} for family in REQUIRED_SCENARIO_FAMILIES])
    record = validate_grid(rows, scenario_family="continuous_linear_boundary_v1", sample_size=60, inference_folds=5, vimp_fingerprint="fixture", critical_value=-2, calibration_replications=1000)
    assert record.status == "rejected"
    assert record.validation_replications_per_family == {family: 1 for family in REQUIRED_SCENARIO_FAMILIES}
    with pytest.raises(ValueError, match="missing required scenario families"):
        validate_grid(rows.iloc[:1], scenario_family="continuous_linear_boundary_v1", sample_size=60, inference_folds=5, vimp_fingerprint="fixture", critical_value=-2)


def test_small_grid_runner_is_deterministic_and_covers_bounded_nonlinear_and_misspecified_families() -> None:
    spec = VimpSpec(forest_trees=10)
    first = run_independent_grid(replications=1, sample_size=60, inference_folds=5, delta=.05, critical_value=-2.11, vimp_spec=spec, seed=4)
    second = run_independent_grid(replications=1, sample_size=60, inference_folds=5, delta=.05, critical_value=-2.11, vimp_spec=spec, seed=4)
    assert first.equals(second)
    assert set(first.scenario_family) == set(REQUIRED_SCENARIO_FAMILIES)
    assert {"theta_hat", "se_theta", "studentized_statistic", "reject"} <= set(first.columns)
