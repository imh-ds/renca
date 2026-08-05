from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from renca.calibration.thresholds import (
    _standardised,
    generate_threshold_scenario,
    run_threshold_replication,
    summarize_learnability,
    summarize_threshold_grid,
)
from renca.models import VimpSpec


def test_both_forms_are_unit_variance_so_the_targets_stay_exact() -> None:
    values = np.random.default_rng(1).normal(size=400_000)
    assert _standardised(values, "linear").var() == pytest.approx(1, abs=.01)
    assert _standardised(values, "oscillatory").var() == pytest.approx(1, abs=.01)


@pytest.mark.parametrize("adequacy,theta", [(0., 0.), (.35, .15), (.6, .02), (.05, .15)])
@pytest.mark.parametrize("added_form", ["linear", "oscillatory"])
def test_scenario_realises_the_requested_adequacy_and_theta(adequacy: float, theta: float, added_form: str) -> None:
    """The study reads cut-offs off these axes, so they must be set rather than approximated."""
    data = generate_threshold_scenario(adequacy=adequacy, theta=theta, separator_form="linear", added_form=added_form, n=300_000, seed=3)
    separator = _standardised(data.z.to_numpy(), "linear")
    added = _standardised(data.x.to_numpy(), added_form)
    outcome = data.y.to_numpy()
    baseline = float(np.var(outcome))
    reduced = float(np.mean((outcome - math.sqrt(adequacy) * separator) ** 2))
    expanded = float(np.mean((outcome - math.sqrt(adequacy) * separator - math.sqrt(theta) * added) ** 2))

    assert 1 - reduced / baseline == pytest.approx(adequacy, abs=.01)
    assert (reduced - expanded) / baseline == pytest.approx(theta, abs=.01)


def test_scenario_rejects_an_unattainable_variance_budget() -> None:
    with pytest.raises(ValueError, match="sum below one"):
        generate_threshold_scenario(adequacy=.7, theta=.4, separator_form="linear", added_form="linear", n=100, seed=1)


def test_replication_labels_truth_from_theta_rather_than_the_estimate() -> None:
    spec = VimpSpec(forest_trees=10, learner_library_version="v3_nested_blend")
    edge = run_threshold_replication(adequacy=.35, theta=.15, separator_form="linear", added_form="linear", n=200, seed=5, delta=.05, critical_value=-5.14, vimp_spec=spec)
    nonedge = run_threshold_replication(adequacy=.35, theta=.0, separator_form="linear", added_form="linear", n=200, seed=5, delta=.05, critical_value=-5.14, vimp_spec=spec)

    assert edge["true_edge"] is True and nonedge["true_edge"] is False
    assert edge["false_prune"] == (edge["certified"] and True)
    assert nonedge["correct_prune"] == (nonedge["certified"] and True)
    assert nonedge["false_prune"] is False
    assert edge["observed_adequacy"] is not None


def test_summaries_separate_false_prunes_from_correct_prunes() -> None:
    """An unlearnable added variable must show as downward theta bias, not as a lower adequacy.

    Adequacy is computed from the reduced model, so it cannot see that the added variable's
    contribution was missed. The learnability breakdown is what exposes it.
    """
    frame = pd.DataFrame({
        "observed_adequacy": [.30, .30, .29, .29],
        "true_edge": [True, False, True, False],
        "false_prune": [False, False, True, False],
        "correct_prune": [False, True, False, True],
        "theta_hat": [.152, .001, .040, .005],
        "true_theta": [.15, .0, .15, .0],
        "status": ["success"] * 4,
        "separator_form": ["linear"] * 4,
        "added_form": ["linear", "linear", "oscillatory", "oscillatory"],
    })
    by_adequacy = summarize_threshold_grid(frame)
    assert set(by_adequacy.columns) >= {"adequacy_bin", "false_prune_rate", "correct_prune_rate", "median_theta_bias"}
    assert by_adequacy.replications.sum() == 4

    by_learnability = summarize_learnability(frame).set_index("added_form")
    assert by_learnability.loc["oscillatory", "median_theta_bias"] < 0 < by_learnability.loc["linear", "median_theta_bias"]
    assert by_learnability.loc["oscillatory", "false_prune_rate"] == 1.
    assert by_learnability.loc["linear", "false_prune_rate"] == 0.
    # The blind spot: adequacy is essentially identical across the two.
    assert by_learnability.loc["oscillatory", "median_observed_adequacy"] == pytest.approx(by_learnability.loc["linear", "median_observed_adequacy"], abs=.02)


def test_summary_rejects_an_empty_grid() -> None:
    with pytest.raises(ValueError, match="no replications"):
        summarize_threshold_grid(pd.DataFrame())
