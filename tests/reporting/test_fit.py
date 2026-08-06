from __future__ import annotations

import json

import pytest

from renca.models import ProjectSpec
from renca.reporting.fit import build_network_fit, write_network_fit
from renca.vimp import VimpEstimate

CRITICAL = -5.137323402339938


def spec(delta: float = .05) -> ProjectSpec:
    return ProjectSpec.model_validate({
        "schema_version": "1.7.0",
        "analysis_id": "dddb2c74-2a57-4561-8afc-2c56e086674b",
        "preanalysis_reference": "fixture",
        "seed": 1,
        "missing_data_policy": "complete_case",
        "design": {"sampling_unit": "iid", "cluster_id_column": None},
        "nodes": [{"node_id": name, "outcome_type": "continuous", "loss": "squared", "delta": delta} for name in ("x", "y")],
    })


def estimate(target: str, added: str, theta: float, se: float, *, null_risk: float = 1., reduced: float = .8) -> VimpEstimate:
    return VimpEstimate(
        pair_id="--".join(sorted([target, added])), target=target, added_variable=added, separator=[],
        theta_hat=theta, psi_hat=theta * null_risk, se_theta=se, delta_target=.05, status="success",
        nuisance_diagnostic={"null_risk": null_risk, "mean_reduced_loss": reduced},
    )


def test_predictive_adequacy_is_the_share_of_baseline_uncertainty_removed() -> None:
    fit = build_network_fit([estimate("y", "x", .01, .002, null_risk=2., reduced=1.5), estimate("x", "y", .01, .002, null_risk=1., reduced=.6)], spec(), CRITICAL)
    # 1 - 1.5/2 = 0.25 and 1 - 0.6/1 = 0.40
    assert fit.predictive_adequacy_median == pytest.approx(.325)
    assert fit.predictive_adequacy_minimum == pytest.approx(.25)


def test_uninformative_models_produce_a_refusal_to_interpret() -> None:
    """Pure noise certifies every pair; the index must say the result carries no information."""
    noise = [estimate("y", "x", .0001, .0005, null_risk=1., reduced=1.), estimate("x", "y", .0001, .0005, null_risk=1., reduced=1.)]
    fit = build_network_fit(noise, spec(), CRITICAL)

    assert fit.predictive_adequacy_median == pytest.approx(0)
    assert "do not support conclusions about network structure" in fit.interpretation


def test_resolution_floor_measures_precision_and_ignores_effect_size() -> None:
    """A network of strong true relationships is not a poorly resolved one.

    The achieved resolution moves with theta because it bounds Theta from above. Only the
    floor is a precision measure, so it must be identical for two analyses that differ only
    in effect size.
    """
    weak = build_network_fit([estimate("y", "x", .01, .01), estimate("x", "y", .01, .01)], spec(), CRITICAL)
    strong = build_network_fit([estimate("y", "x", .40, .01), estimate("x", "y", .40, .01)], spec(), CRITICAL)

    assert weak.resolution_floor_median == pytest.approx(strong.resolution_floor_median)
    assert strong.achieved_resolution_median > weak.achieved_resolution_median
    assert weak.achieved_resolution_median == pytest.approx(.01 + abs(CRITICAL) * .01)


def test_a_pair_takes_the_worse_of_its_two_directions() -> None:
    fit = build_network_fit([estimate("y", "x", .01, .01), estimate("x", "y", .01, .03)], spec(), CRITICAL)
    pair = fit.pairs[0]
    assert pair.resolution_floor == pytest.approx(abs(CRITICAL) * .03)
    assert pair.achieved_resolution == pytest.approx(.01 + abs(CRITICAL) * .03)


def test_verdict_flags_a_delta_finer_than_the_data_can_deliver() -> None:
    """The configuration mismatch otherwise appears only as unexplained unresolved pairs."""
    coarse = build_network_fit([estimate("y", "x", .01, .05), estimate("x", "y", .01, .05)], spec(delta=.05), CRITICAL)
    assert "coarser than every requested delta" in coarse.interpretation

    fine = build_network_fit([estimate("y", "x", .001, .0005), estimate("x", "y", .001, .0005)], spec(delta=.05), CRITICAL)
    assert "coarser than every requested delta" not in fine.interpretation


def test_verdict_never_presents_adequacy_as_a_trust_signal() -> None:
    """The threshold study found no relationship between adequacy and false pruning.

    Wording that implies otherwise would claim a protection the index does not provide,
    so the verdict must say what adequacy anticipates and where safety actually comes
    from. This is a wording contract, deliberately pinned.
    """
    fit = build_network_fit([estimate("y", "x", .01, .01), estimate("x", "y", .01, .01)], spec(), CRITICAL)
    verdict = fit.interpretation.lower()

    assert "not a measure of whether results can be trusted" in verdict
    assert "controlled by the calibration profile" in verdict
    assert "no validated cut-offs" in verdict
    for forbidden in ("reliable", "trustworthy", "acceptable", "good fit", "passes"):
        assert forbidden not in verdict


def test_uncalibrated_runs_fall_back_to_a_labelled_normal_approximation() -> None:
    fit = build_network_fit([estimate("y", "x", .01, .01), estimate("x", "y", .01, .01)], spec(), critical_value=None)
    assert fit.resolution_basis == "normal_approximation"
    assert all(pair.resolution_basis == "normal_approximation" for pair in fit.pairs)
    assert "unvalidated normal approximation" in fit.interpretation


def test_failed_estimates_yield_no_resolution_rather_than_a_wrong_one() -> None:
    broken = VimpEstimate(pair_id="x--y", target="y", added_variable="x", separator=[], delta_target=.05, status="learner_failure", nuisance_diagnostic={})
    fit = build_network_fit([broken, estimate("x", "y", .01, .01)], spec(), CRITICAL)
    assert fit.pairs[0].achieved_resolution is None
    assert fit.pairs[0].resolution_basis == "unavailable"


def test_fit_artifact_is_canonical_and_never_claims_validated_thresholds(tmp_path) -> None:
    fit = build_network_fit([estimate("y", "x", .01, .01), estimate("x", "y", .01, .01)], spec(), CRITICAL)
    path = write_network_fit(fit, tmp_path)
    payload = json.loads(path.read_text())
    assert path.name == "network_fit.json"
    assert payload["thresholds_are_validated"] is False
    assert write_network_fit(fit, tmp_path).read_bytes() == path.read_bytes()
