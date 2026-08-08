from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from renca.calibration import CRITICAL_QUANTILE, CalibrationRecord, critical_value_from_training, CalibrationRegistry, REQUIRED_SCENARIO_FAMILIES, apply_profile, calibrated_p_value, calibration_eligibility, calibration_status, run_independent_grid, validate_grid, vimp_fingerprint
from renca.calibration.registry import file_sha256
from renca.calibration.scenarios import generate_scenario, oracle_theta, tune_boundary_signal
from renca.models import VimpSpec
from renca.runner import default_calibration_registry_path
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


@pytest.mark.parametrize(
    ("update", "expected_field"),
    [
        ({"delta_target": .04}, "delta_target"),
        ({"inference_rows": 299}, "inference_rows"),
        ({"inference_folds": 4}, "inference_folds"),
        ({"spec": VimpSpec(ridge_alpha=2)}, "vimp_fingerprint"),
        ({"alpha": .01}, "alpha"),
    ],
)
def test_eligibility_names_every_exact_match_failure(update: dict[str, object], expected_field: str) -> None:
    spec = VimpSpec()
    arguments: dict[str, object] = {"profile_id": "fixture", "delta_target": .05, "inference_rows": 300, "inference_folds": 5, "spec": spec}
    arguments.update(update)
    result = calibration_eligibility(CalibrationRegistry(records=[valid_record(spec)]), **arguments)
    assert result.status == "calibration_failed"
    assert result.matched_profile_id == "fixture"
    assert result.mismatch_fields == [expected_field]


def test_eligibility_reports_profile_and_distribution_failures() -> None:
    spec = VimpSpec()
    registry = CalibrationRegistry(records=[valid_record(spec)])
    assert calibration_eligibility(registry, profile_id="unknown", delta_target=.05, inference_rows=300, inference_folds=5, spec=spec).mismatch_fields == ["profile_id"]
    assert calibration_eligibility(registry, profile_id="fixture", delta_target=.05, inference_rows=300, inference_folds=5, spec=spec, distribution_ok=False).mismatch_fields == ["distribution_artifact"]


PACKAGED_PROFILES = [
    ("v3-nested-blend-n300-d005-phase0", "v3_nested_blend", .05),
    ("v4-cubic-blend-n300-d005-phase0", "v4_cubic_blend", .05),
    ("v4-cubic-blend-n300-d010-phase0", "v4_cubic_blend", .10),
    ("v4-cubic-blend-n300-d020-phase0", "v4_cubic_blend", .20),
]


@pytest.mark.parametrize(("profile_id", "library", "delta"), PACKAGED_PROFILES)
def test_every_packaged_profile_is_an_exact_validated_match(profile_id: str, library: str, delta: float) -> None:
    """Four profiles ship: v4 at three resolutions, plus v3 for analyses bound to it.

    Each must describe the estimator it is paired with, cover every required scenario
    family, and clear alpha on its own rather than through abstention.
    """
    registry = CalibrationRegistry.load(default_calibration_registry_path())
    eligibility = calibration_eligibility(registry, profile_id=profile_id, delta_target=delta, inference_rows=300, inference_folds=5, spec=VimpSpec(forest_trees=10, learner_library_version=library))
    assert eligibility.status == "calibrated_success"
    assert eligibility.mismatch_fields == []
    record = next(item for item in registry.records if item.profile_id == profile_id)
    assert record.critical_quantile == CRITICAL_QUANTILE
    assert max(record.grid_upper_rejection_bounds.values()) <= record.alpha
    assert max(record.grid_ineligibility_rates.values()) < .01


@pytest.mark.parametrize(("profile_id", "library", "delta"), PACKAGED_PROFILES)
def test_a_profile_is_bound_to_the_delta_it_was_calibrated_at(profile_id: str, library: str, delta: float) -> None:
    """The delta profiles differ only in resolution, so nothing else stops them crossing.

    A critical value calibrated at 0.20 used to test a 0.05 hypothesis would certify at a
    left tail that was never validated there, and every other exact-match field would agree.
    """
    registry = CalibrationRegistry.load(default_calibration_registry_path())
    other = next(value for _, _, value in PACKAGED_PROFILES if value != delta)
    crossed = calibration_eligibility(registry, profile_id=profile_id, delta_target=other, inference_rows=300, inference_folds=5, spec=VimpSpec(forest_trees=10, learner_library_version=library))
    assert crossed.mismatch_fields == ["delta_target"]


def test_a_coarser_resolution_tolerates_a_larger_standard_error() -> None:
    """Why the delta profiles exist: certifying needs `se < delta / |critical|`.

    The critical value shrinks with delta as well, so the tolerated standard error rises
    faster than delta does. That is the whole payoff for a dataset whose resolution floor
    sits above 0.05, and it would be silently lost if a future recalibration inverted it.
    """
    registry = CalibrationRegistry.load(default_calibration_registry_path())
    tolerated = {
        record.delta_target: record.delta_target / abs(record.critical_value)
        for record in registry.records
        if record.profile_id.startswith("v4-cubic-blend")
    }
    assert tolerated[.05] < tolerated[.10] < tolerated[.20]
    assert tolerated[.10] / tolerated[.05] > 2


def test_a_profile_cannot_be_paired_with_a_different_library() -> None:
    """The fingerprint is what stops v4's critical value being used with v3's estimator."""
    registry = CalibrationRegistry.load(default_calibration_registry_path())
    crossed = calibration_eligibility(registry, profile_id="v4-cubic-blend-n300-d005-phase0", delta_target=.05, inference_rows=300, inference_folds=5, spec=VimpSpec(forest_trees=10, learner_library_version="v3_nested_blend"))
    assert crossed.mismatch_fields == ["vimp_fingerprint"]


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


def test_grid_results_do_not_depend_on_the_worker_count() -> None:
    """Worker count must change throughput only.

    The assembled distribution's SHA-256 is recorded in the registry and checked on every
    load, so a grid whose output shifted with the host's core count would produce a profile
    that could not be revalidated elsewhere. Threaded BLAS reductions reorder floating-point
    summation, which is why the runner pins thread pools rather than only setting the
    environment variables that worker processes read at start-up.
    """
    spec = VimpSpec(forest_trees=10); signals = {family: tune_boundary_signal(family, .05, n=20_000)[0] for family in REQUIRED_SCENARIO_FAMILIES}
    arguments = {"replications": 2, "sample_size": 60, "inference_folds": 5, "delta": .05, "critical_value": -2.11, "vimp_spec": spec, "seed": 4, "boundary_signals": signals}
    serial = run_independent_grid(**arguments, workers=1)
    parallel = run_independent_grid(**arguments, workers=4)
    assert serial.equals(parallel)


def test_quadratic_ridge_produces_eligible_interaction_fixture_estimates() -> None:
    family = "learner_misspecification_v1"
    signal = tune_boundary_signal(family, .05, n=20_000)[0]
    results = run_independent_grid(replications=5, sample_size=300, inference_folds=5, delta=.05, critical_value=-99, vimp_spec=VimpSpec(forest_trees=10), seed=20260804, scenario_families=(family,), boundary_signals={family: signal})
    assert (results.status == "success").any()


def test_critical_value_uses_a_sub_alpha_quantile_and_records_it() -> None:
    """The family attaining the minimum quantile is validated against that same value.

    Its rejection rate therefore targets the quantile, so setting it at alpha puts the
    observed rate on alpha and its 95% upper bound above it about half the time. The
    2026-08-05 Phase-0 rerun failed exactly that way once the section 16.4 safeguard
    stopped supplying margin through abstention.
    """
    assert CRITICAL_QUANTILE < .05
    generator = np.random.default_rng(0)
    frame = pd.DataFrame({
        "scenario_family": np.repeat(list(REQUIRED_SCENARIO_FAMILIES), 2000),
        "studentized_statistic": np.concatenate([generator.normal(size=2000) for _ in REQUIRED_SCENARIO_FAMILIES]),
    })
    assert critical_value_from_training(frame) < critical_value_from_training(frame, quantile=.05)

    results = pd.DataFrame([
        {"scenario_family": family, "replicate": index, "reject": False, "status": "success"}
        for family in REQUIRED_SCENARIO_FAMILIES for index in range(5000)
    ])
    record = validate_grid(results, profile_id="fixture", scenario_family=REQUIRED_SCENARIO_FAMILIES[0], delta_target=.05, inference_rows=300, inference_folds=5, vimp_fingerprint="x", critical_value=-5.14, calibration_replications=6000, calibration_successful_replications_per_family={family: 6000 for family in REQUIRED_SCENARIO_FAMILIES})
    assert record.critical_quantile == CRITICAL_QUANTILE
    assert record.status == "validated"


def test_records_without_the_field_default_to_the_alpha_quantile() -> None:
    """Registries written before `critical_quantile` existed were built at alpha."""
    legacy = {key: value for key, value in valid_record(VimpSpec()).model_dump(mode="json").items() if key != "critical_quantile"}
    assert CalibrationRecord.model_validate(legacy).critical_quantile == .05
