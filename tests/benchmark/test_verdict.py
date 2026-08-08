from __future__ import annotations

import pandas as pd
import pytest

from renca.benchmark.verdict import MATERIAL_MARGIN, USEFUL_PRUNE_FLOOR, dominated_baselines, gate_verdict, matched_power_comparison, spec_criterion_baselines


def cell(rows: list[tuple[str, float, float, float]], *, familywise: float = .0) -> pd.DataFrame:
    """(method, setting, false_prune_rate, true_prune_rate) for one family/n cell.

    Every row shares one `reference_delta` -- the resolution the method under test was run
    at -- because that is how a real cell is assembled: each baseline is scored once per
    resolution so it can be compared against the method at the same one.
    """
    reference = next((setting for method, setting, *_ in rows if method == "renca"), .05)
    return pd.DataFrame([
        {
            "family": "linear_gaussian", "n": 375, "reference_delta": reference,
            "method": method, "setting": setting,
            "false_prune_rate": false_rate, "true_prune_rate": true_rate,
            "practical_false_prune_rate": false_rate, "practical_true_prune_rate": true_rate,
            "familywise_error_rate": familywise if method == "renca" else 0.0,
            "familywise_upper_bound": familywise if method == "renca" else 0.0,
            "practical_familywise_error_rate": familywise if method == "renca" else 0.0,
            "practical_familywise_upper_bound": familywise if method == "renca" else 0.0,
        }
        for method, setting, false_rate, true_rate in rows
    ])


def test_domination_requires_winning_on_both_axes() -> None:
    """Pruning nothing gives a perfect false-prune rate, so one axis alone proves nothing."""
    summary = cell([("renca", .05, .00, .40), ("pc", .05, .10, .35), ("fci", .05, .00, .90)])
    renca = summary[summary.method == "renca"].iloc[0]
    dominated = {item["method"] for item in dominated_baselines(summary, renca)}

    assert dominated == {"pc"}  # fci prunes far more, so it is not dominated despite equal error


def test_a_margin_smaller_than_measurement_noise_is_not_material() -> None:
    summary = cell([("renca", .05, .020, .40), ("pc", .05, .020 + MATERIAL_MARGIN / 2, .30)])
    assert dominated_baselines(summary, summary.iloc[0]) == []


def test_matched_power_compares_against_baselines_that_prune_at_least_as_much() -> None:
    """A baseline tuned to prune far more will also false-prune more; comparing against it
    would flatter the method, so the comparison is held at matched pruning power."""
    summary = cell([("renca", .05, .02, .50), ("pc", .001, .30, .95), ("pc", .20, .04, .60), ("ges", 1.0, .01, .20)])
    matched = matched_power_comparison(summary, summary.iloc[0])

    assert matched["exists"] and matched["method"] == "pc" and matched["setting"] == .20
    assert matched["renca_is_better"] is True  # ges prunes too little to qualify


def test_verdict_is_go_only_when_every_condition_holds_in_one_region() -> None:
    summary = cell([("renca", .05, .00, .40), ("pc", .05, .12, .35)])
    verdict = gate_verdict(summary)

    assert verdict["verdict"] == "GO"
    assert verdict["regions_passing"] == 1
    assert "practical threshold is substantively interpretable" in verdict["requires_human_signoff"]


def test_uncontrolled_familywise_error_stops_the_program() -> None:
    """Section 44 criterion 1: this is a stop condition, not a tuning problem."""
    summary = cell([("renca", .05, .30, .40), ("pc", .05, .50, .35)], familywise=.9)
    assert gate_verdict(summary)["verdict"] == "STOP"


def test_controlled_error_without_a_beaten_baseline_is_a_redesign() -> None:
    summary = cell([("renca", .05, .02, .40), ("pc", .05, .00, .90)])
    verdict = gate_verdict(summary)

    assert verdict["verdict"] == "REDESIGN"
    assert "criterion 3" in verdict["reason"]


def test_pruning_almost_nothing_is_a_redesign_even_with_perfect_error() -> None:
    summary = cell([("renca", .05, .00, USEFUL_PRUNE_FLOOR / 2), ("pc", .05, .20, .90)])
    verdict = gate_verdict(summary)

    assert verdict["verdict"] == "REDESIGN"
    assert "mostly unresolved" in verdict["reason"]


def test_a_summary_without_the_method_cannot_pass_the_gate() -> None:
    summary = cell([("pc", .05, .02, .40)])
    assert gate_verdict(summary)["verdict"] == "STOP"


def test_the_spec_criterion_credits_trading_pruning_power_for_error() -> None:
    """Section 44 criterion 3 falsifies only when the method prunes far fewer true nonedges
    *and* fails to reduce false prunes. Pruning 85% where PC prunes 100%, at a twelfth of
    the error, is the intended trade -- strict Pareto dominance would have called it a
    failure, so both are reported and the verdict runs on the specification's own rule."""
    summary = cell([("renca", .20, .02, .85), ("pc", .05, .24, 1.0)])
    renca = summary[summary.method == "renca"].iloc[0]

    assert dominated_baselines(summary, renca) == []  # renca prunes less, so no dominance
    beaten = spec_criterion_baselines(summary, renca)
    assert [item["method"] for item in beaten] == ["pc"]
    assert beaten[0]["pruning_retained"] == pytest.approx(.85)
    assert gate_verdict(summary)["verdict"] == "GO"


def test_pruning_far_less_than_a_baseline_is_not_credited() -> None:
    """Below the 'nearly as many' floor the trade stops counting, however clean the error."""
    summary = cell([("renca", .20, .00, .50), ("pc", .05, .24, 1.0)])
    assert spec_criterion_baselines(summary, summary.iloc[0]) == []
    assert gate_verdict(summary)["verdict"] == "REDESIGN"
