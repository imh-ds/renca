from __future__ import annotations

import math

import pytest

from renca.certification import PairState, certify_pairs
from renca.vimp import VimpEstimate


def estimate(pair: str, target: str, added: str, theta: float, *, calibrated: bool = True, status: str = "success", separator: list[str] | None = None) -> VimpEstimate:
    p = .001 if theta <= .02 else (.04 if theta < .1 else .99)
    return VimpEstimate(pair_id=pair, target=target, added_variable=added, separator=separator or ["z"], psi_hat=theta, theta_hat=theta, se_theta=.01, lower_ci=theta-.02, upper_ci=theta+.02, delta_target=.1, p_equivalence=p if calibrated else None, calibration_status="calibrated_success" if calibrated else "uncalibrated", status=status)


def test_both_directions_pass_iut_and_holm_certifies() -> None:
    certificates = certify_pairs([estimate("x--y", "x", "y", .01), estimate("x--y", "y", "x", .02)])
    assert certificates[0].state is PairState.CERTIFIED_NONEDGE
    assert certificates[0].raw_p == pytest.approx(max(0.0, certificates[0].raw_p))
    assert certificates[0].adjusted_p <= .05


def test_one_direction_above_threshold_never_certifies() -> None:
    certificate = certify_pairs([estimate("x--y", "x", "y", .01), estimate("x--y", "y", "x", .2)])[0]
    assert certificate.state is PairState.UNRESOLVED


def test_candidate_adjacency_requires_both_lower_bounds_above_delta() -> None:
    certificate = certify_pairs([estimate("x--y", "x", "y", .2), estimate("x--y", "y", "x", .25)])[0]
    assert certificate.state is PairState.CANDIDATE_ADJACENCY


@pytest.mark.parametrize("calibrated,status", [(False, "success"), (True, "learner_failure"), (True, "full_worse_than_reduced")])
def test_invalid_or_uncalibrated_estimate_cannot_prune(calibrated: bool, status: str) -> None:
    certificate = certify_pairs([estimate("x--y", "x", "y", .01, calibrated=calibrated, status=status), estimate("x--y", "y", "x", .01)])[0]
    assert certificate.state is PairState.UNRESOLVED and certificate.adjusted_p is None


def test_holm_rejects_raw_passing_pair_and_invalid_pairs_fail_visibly() -> None:
    weak = [estimate("a--b", "a", "b", .082), estimate("a--b", "b", "a", .082)]
    strong = [estimate("c--d", "c", "d", .01), estimate("c--d", "d", "c", .01)]
    weaker = [estimate("e--f", "e", "f", .084), estimate("e--f", "f", "e", .084)]
    certificates = {item.pair_id: item for item in certify_pairs(weak + strong + weaker)}
    assert certificates["a--b"].raw_p < .05 and certificates["a--b"].adjusted_p > .05
    with pytest.raises(ValueError, match="exactly two"):
        certify_pairs([estimate("x--y", "x", "y", .01)])
