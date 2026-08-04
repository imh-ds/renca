from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from renca.models import NodeSpec, VimpSpec
from renca.screening import SplitManifest
from renca.vimp import fit_crossfitted_vimp


def manifest(n: int = 180, folds: int = 3) -> SplitManifest:
    positions = list(range(n))
    return SplitManifest(schema_version="1.7.0", analysis_id="dddb2c74-2a57-4561-8afc-2c56e086674b", seed=11, selection_fraction=0.2, inference_folds=folds, sampling_unit="iid", selection_row_positions=[], inference_row_positions=positions, inference_fold_by_row_position={row: row % folds for row in positions}, stratification_columns=[], input_order_sha256="fixture")


def continuous_node() -> NodeSpec:
    return NodeSpec(node_id="y", outcome_type="continuous", loss="squared", delta=0.01)


def test_continuous_null_signal_has_small_vimp_and_fold_isolation() -> None:
    rng = np.random.default_rng(1); z = rng.normal(size=180); data = pd.DataFrame({"z": z, "x": rng.normal(size=180), "y": z + rng.normal(scale=.1, size=180)})
    estimate = fit_crossfitted_vimp(data, "y", "x", ["z"], continuous_node(), manifest(), VimpSpec(forest_trees=10))
    assert estimate.status in {"success", "full_worse_than_reduced"}
    assert abs(estimate.theta_hat) < .1
    assert math.isclose(estimate.theta_hat, estimate.psi_hat / estimate.nuisance_diagnostic["null_risk"])
    seen: set[int] = set()
    for fold in estimate.nuisance_diagnostic["folds"].values():
        assert set(fold["train_rows"]).isdisjoint(fold["validation_rows"]); seen.update(fold["validation_rows"])
    assert seen == set(range(180))


def test_continuous_and_binary_signals_are_positive_and_deterministic() -> None:
    rng = np.random.default_rng(2); z = rng.normal(size=180); x = rng.normal(size=180)
    continuous = pd.DataFrame({"z": z, "x": x, "y": z + x + rng.normal(scale=.1, size=180)})
    spec = VimpSpec(forest_trees=10)
    first = fit_crossfitted_vimp(continuous, "y", "x", ["z"], continuous_node(), manifest(), spec)
    second = fit_crossfitted_vimp(continuous, "y", "x", ["z"], continuous_node(), manifest(), spec)
    assert first == second and first.theta_hat > .2 and first.se_theta > 0 and first.lower_ci < first.upper_ci
    probability = 1 / (1 + np.exp(-(z + x))); binary = pd.DataFrame({"z": z, "x": x, "y": rng.binomial(1, probability)})
    node = NodeSpec(node_id="y", outcome_type="binary", loss="brier", delta=.01)
    result = fit_crossfitted_vimp(binary, "y", "x", ["z"], node, manifest(), spec)
    assert result.status in {"success", "full_worse_than_reduced"} and result.theta_hat > 0 and result.se_theta > 0


def test_nested_safeguard_needs_material_and_consistent_degradation() -> None:
    """Section 16.4 asks for degradation that is *material* and holds *across perturbations*.

    An irrelevant added variable drives psi slightly negative in most folds through nothing
    but extra estimation variance. That is consistent but not material, and it is the
    strongest evidence of practical irrelevance available -- so it must not abstain. A bare
    `psi < 0` test cannot tell the two apart, which is what the tightened parameters here
    reproduce.
    """
    rng = np.random.default_rng(2)
    z = rng.normal(size=300); x = rng.normal(size=300)
    data = pd.DataFrame({"z": z, "x": x, "y": z + rng.normal(scale=.5, size=300)})
    node = NodeSpec(node_id="y", outcome_type="continuous", loss="squared", delta=.05)
    library = {"forest_trees": 10, "learner_library_version": "v3_nested_blend"}

    default = fit_crossfitted_vimp(data, "y", "x", ["z"], node, manifest(300, 5), VimpSpec(**library))
    safeguard = default.nuisance_diagnostic["nested_safeguard"]
    assert default.theta_hat < 0
    assert default.status == "success"
    assert safeguard["consistently_worse"] is True
    assert safeguard["materially_worse"] is False

    legacy = fit_crossfitted_vimp(data, "y", "x", ["z"], node, manifest(300, 5), VimpSpec(**library, nested_safeguard_materiality_z=1e-9, nested_safeguard_fold_fraction=.51))
    assert legacy.status == "full_worse_than_reduced"
    assert legacy.theta_hat == default.theta_hat


def test_nested_blend_is_deterministic_and_records_convex_weights() -> None:
    rng = np.random.default_rng(14); z = rng.normal(size=180); x = rng.normal(size=180)
    data = pd.DataFrame({"z": z, "x": x, "y": z * x + rng.normal(scale=.3, size=180)})
    spec = VimpSpec(forest_trees=10, learner_library_version="v3_nested_blend")
    first = fit_crossfitted_vimp(data, "y", "x", ["z"], continuous_node(), manifest(), spec)
    second = fit_crossfitted_vimp(data, "y", "x", ["z"], continuous_node(), manifest(), spec)
    assert first == second
    for fold in first.nuisance_diagnostic["folds"].values():
        assert fold["full_selected"] == "nested_convex_blend"
        assert sum(fold["full_risks"][f"blend_weight_{name}"] for name in ("ridge", "quadratic_ridge", "forest")) == pytest.approx(1)
