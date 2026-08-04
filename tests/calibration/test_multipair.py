from __future__ import annotations

import pandas as pd
import pytest

from renca.calibration.multipair import (
    block_correlation,
    boundary_pairs,
    generate_multipair_scenario,
    null_pairs,
    oracle_block_theta,
    run_multipair_replication,
    summarize_multipair_grid,
)
from renca.models import VimpSpec


def test_boundary_block_places_both_directions_at_delta() -> None:
    """The pair test takes the maximum directional p-value, so both sides must sit at delta.

    The population value is exact by construction -- ``rho**2 = delta * (c**2 + 1)`` gives
    ``theta = rho**2 / (c**2 + 1) = delta`` in both directions -- so the tolerance here only
    absorbs Monte Carlo error in the oracle estimator.
    """
    for delta in (0.02, 0.05):
        forward, reverse = oracle_block_theta(delta, 1.0, n=400_000)
        assert forward == pytest.approx(delta, abs=0.002)
        assert reverse == pytest.approx(delta, abs=0.002)


def test_block_correlation_rejects_unattainable_configurations() -> None:
    with pytest.raises(ValueError, match="unattainable"):
        block_correlation(0.5, 2.0)


def test_scenario_is_deterministic_and_only_couples_within_blocks() -> None:
    first = generate_multipair_scenario(blocks=2, n=600, seed=5, delta=0.05)
    second = generate_multipair_scenario(blocks=2, n=600, seed=5, delta=0.05)

    assert first.equals(second)
    assert list(first.columns) == ["z0", "x0", "y0", "z1", "x1", "y1"]
    assert abs(first.x0.corr(first.y0)) > 0.4
    assert abs(first.x0.corr(first.y1)) < 0.15
    assert abs(first.z0.corr(first.z1)) < 0.15


def test_pair_bookkeeping_names_every_within_block_pair() -> None:
    assert boundary_pairs(2) == {"x0--y0": "z0", "x1--y1": "z1"}
    assert null_pairs(2) == {"x0--y0", "x0--z0", "y0--z0", "x1--y1", "x1--z1", "y1--z1"}


def test_replication_without_a_profile_reports_no_certification() -> None:
    """A run outside the validated profile must produce evidence but never a certificate."""
    result = run_multipair_replication(
        blocks=1,
        sample_size=120,
        seed=11,
        delta=0.05,
        vimp_spec=VimpSpec(forest_trees=10, learner_library_version="v3_nested_blend"),
        inference_folds=3,
    )

    assert result["pairs"] == 3
    assert result["family_size"] == 0
    assert result["calibrated_directions"] == 0
    assert result["false_certifications"] == 0
    assert result["familywise_error"] is False
    assert result["boundary_pairs"] == 1


def test_summary_reports_an_exact_upper_bound_and_flags_loss_of_control() -> None:
    controlled = pd.DataFrame({
        "familywise_error": [False] * 400,
        "false_certifications": [0] * 400,
        "boundary_false_certifications": [0] * 400,
        "true_nonedge_certifications": [3] * 400,
        "true_nonedge_pairs": [9] * 400,
        "boundary_separator_recovered": [2] * 400,
        "boundary_pairs": [2] * 400,
        "family_size": [7] * 400,
        "abstentions": [4] * 400,
        "pairs": [15] * 400,
    })
    summary = summarize_multipair_grid(controlled)

    assert summary["familywise_error_rate"] == 0.0
    assert summary["familywise_upper_bound"] < 0.05
    assert summary["controlled"] is True
    assert summary["true_nonedge_certification_rate"] == pytest.approx(1 / 3)
    assert summary["separator_recovery_rate"] == 1.0

    breached = controlled.assign(familywise_error=[True] * 40 + [False] * 360)
    assert summarize_multipair_grid(breached)["controlled"] is False


def test_summary_rejects_an_empty_grid() -> None:
    with pytest.raises(ValueError, match="no replications"):
        summarize_multipair_grid(pd.DataFrame())
