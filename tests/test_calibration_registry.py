from __future__ import annotations

import pandas as pd
import pytest

from renca.calibration import CalibrationRecord, CalibrationRegistry, REQUIRED_SCENARIO_FAMILIES, apply_profile, calibrated_p_value, calibration_status, run_independent_grid, validate_grid, vimp_fingerprint
from renca.calibration.registry import file_sha256
from renca.calibration.scenarios import generate_scenario, oracle_theta, tune_boundary_signal
from renca.models import VimpSpec
from renca.vimp import VimpEstimate


def valid_record(spec: VimpSpec) -> CalibrationRecord:
    families = list(REQUIRED_SCENARIO_FAMILIES)
    return CalibrationRecord(profile_id="fixture", scenario_family=families[0], delta_target=.05, inference_rows=300, inference_folds=5, vimp_fingerprint=vimp_fingerprint(spec), critical_value=-2, distribution_file="fixture.parquet", distribution_sha256="fixture", calibration_replications=5000, calibration_successful_replications_per_family={family: 5000 for family in families}, evaluation_replications=5000, empirical_rejection_rate=.04, upper_rejection_bound=.049, validation_scenario_families=families, validation_replications_per_family={family: 5000 for family in families}, grid_upper_rejection_bounds={family: .049 for family in families}, grid_ineligibility_rates={family: 1 for family in families}, status="validated")


def test_gate_requires_exact_binding_and_formal_evidence() -> None:
    spec = VimpSpec(); registry = CalibrationRegistry(records=[valid_record(spec)])
    assert calibration_status(registry, profile_id="fixture", delta_target=.05, inference_rows=300, inference_folds=5, spec=spec) == "calibrated_success"
    assert calibration_status(registry, profile_id="fixture", delta_target=.01, inference_rows=300, inference_folds=5, spec=spec) == "calibration_failed"
    assert calibration_status(registry, profile_id=None, delta_target=.05, inference_rows=300, inference_folds=5, spec=spec) == "uncalibrated"
    registry.records[0].upper_rejection_bound = .06
    assert calibration_status(registry, profile_id="fixture", delta_target=.05, inference_rows=300, inference_folds=5, spec=spec) == "calibration_failed"


@pytest.mark.parametrize("rows,folds,spec", [(299, 5, VimpSpec()), (300, 4, VimpSpec()), (300, 5, VimpSpec(ridge_alpha=2))])
def test_gate_rejects_every_nonexact_configuration(rows: int, folds: int, spec: VimpSpec) -> None:
    registry = CalibrationRegistry(records=[valid_record(VimpSpec())])
    assert calibration_status(registry, profile_id="fixture", delta_target=.05, inference_rows=rows, inference_folds=folds, spec=spec) == "calibration_failed"


def test_apply_profile_loads_hashed_distribution_and_populates_empirical_p(tmp_path) -> None:
    spec = VimpSpec(); distribution = pd.DataFrame({"scenario_family": REQUIRED_SCENARIO_FAMILIES, "studentized_statistic": [-3., -2., -1., -4., -2.5]})
    path = tmp_path / "distribution.parquet"; distribution.to_parquet(path, index=False)
    record = valid_record(spec).model_copy(update={"distribution_file": path.name, "distribution_sha256": file_sha256(path)})
    estimate = VimpEstimate(pair_id="x--y", target="y", added_variable="x", separator=["z"], theta_hat=.01, psi_hat=.01, se_theta=.01, delta_target=.05, status="success")
    applied = apply_profile([estimate], registry=CalibrationRegistry(records=[record]), registry_path=tmp_path / "registry.yml", profile_id="fixture", inference_rows=300, inference_folds=5, vimp_spec=spec)[0]
    assert applied.calibration_status == "calibrated_success" and applied.p_equivalence is not None


def test_profile_p_value_is_worst_family_plus_one_left_tail() -> None:
    record = valid_record(VimpSpec())
    distribution = pd.DataFrame({"scenario_family": [REQUIRED_SCENARIO_FAMILIES[0]] * 3 + [REQUIRED_SCENARIO_FAMILIES[1]] * 3, "studentized_statistic": [-3, -2, -1, -4, -3, 0]})
    record.validation_scenario_families = list(REQUIRED_SCENARIO_FAMILIES[:2])
    assert calibrated_p_value(-2.5, record, distribution) == pytest.approx(.75)
    assert calibrated_p_value(-4, record, distribution) < calibrated_p_value(-2.5, record, distribution)


def test_grid_requires_all_families_and_never_validates_a_smoke_run() -> None:
    rows = pd.DataFrame([{"scenario_family": family, "replicate": 0, "reject": False} for family in REQUIRED_SCENARIO_FAMILIES])
    record = validate_grid(rows, profile_id="fixture", scenario_family="continuous_linear_boundary_v1", delta_target=.05, inference_rows=60, inference_folds=5, vimp_fingerprint="fixture", critical_value=-2, calibration_replications=1000)
    assert record.status == "rejected"
    with pytest.raises(ValueError, match="missing required scenario families"):
        validate_grid(rows.iloc[:1], profile_id="fixture", scenario_family="continuous_linear_boundary_v1", delta_target=.05, inference_rows=60, inference_folds=5, vimp_fingerprint="fixture", critical_value=-2)


def test_grid_records_ineligible_rate_as_a_power_diagnostic() -> None:
    rows = pd.DataFrame([{"scenario_family": family, "replicate": index, "reject": False, "status": "full_worse_than_reduced" if family == "learner_misspecification_v1" else "success"} for family in REQUIRED_SCENARIO_FAMILIES for index in range(2)])
    record = validate_grid(rows, profile_id="fixture", scenario_family="continuous_linear_boundary_v1", delta_target=.05, inference_rows=60, inference_folds=5, vimp_fingerprint="fixture", critical_value=-2, calibration_replications=5000, calibration_successful_replications_per_family={family: 5000 for family in REQUIRED_SCENARIO_FAMILIES})
    assert record.grid_ineligibility_rates["learner_misspecification_v1"] == 1 and record.status == "rejected"


def test_boundary_tuning_is_deterministic_and_bounded_families_have_required_shape() -> None:
    for family in REQUIRED_SCENARIO_FAMILIES:
        signal, theta = tune_boundary_signal(family, .05, n=20_000)
        assert abs(theta - .05) <= .002
        assert oracle_theta(family, signal, n=20_000) == pytest.approx(theta)
    unsaturated = generate_scenario("bounded_composite_unsaturated_v1", 1000, 3, .05, signal=.3)
    saturated = generate_scenario("bounded_composite_saturated_v1", 1000, 3, .05, signal=.3)
    assert unsaturated.y.between(0, 10).all() and (unsaturated.y == 0).mean() == 0
    assert saturated.y.between(0, 10).all() and .05 < (saturated.y == 0).mean() < .2


def test_small_grid_runner_is_deterministic_and_covers_every_family() -> None:
    spec = VimpSpec(forest_trees=10); signals = {family: tune_boundary_signal(family, .05, n=20_000)[0] for family in REQUIRED_SCENARIO_FAMILIES}
    first = run_independent_grid(replications=1, sample_size=60, inference_folds=5, delta=.05, critical_value=-2.11, vimp_spec=spec, seed=4, boundary_signals=signals)
    second = run_independent_grid(replications=1, sample_size=60, inference_folds=5, delta=.05, critical_value=-2.11, vimp_spec=spec, seed=4, boundary_signals=signals)
    assert first.equals(second) and set(first.scenario_family) == set(REQUIRED_SCENARIO_FAMILIES)


def test_quadratic_ridge_produces_eligible_interaction_fixture_estimates() -> None:
    family = "learner_misspecification_v1"
    signal = tune_boundary_signal(family, .05, n=20_000)[0]
    results = run_independent_grid(replications=5, sample_size=300, inference_folds=5, delta=.05, critical_value=-99, vimp_spec=VimpSpec(forest_trees=10), seed=20260804, scenario_families=(family,), boundary_signals={family: signal})
    assert (results.status == "success").any()
