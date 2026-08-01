from __future__ import annotations

import math

import numpy as np
import pandas as pd

from renca.models import NodeSpec, VimpSpec
from renca.screening import SplitManifest
from renca.vimp import fit_crossfitted_vimp


def manifest(n: int = 180) -> SplitManifest:
    positions = list(range(n))
    return SplitManifest(schema_version="1.3.0", analysis_id="dddb2c74-2a57-4561-8afc-2c56e086674b", seed=11, selection_fraction=0.2, inference_folds=3, sampling_unit="iid", selection_row_positions=[], inference_row_positions=positions, inference_fold_by_row_position={row: row % 3 for row in positions}, stratification_columns=[], input_order_sha256="fixture")


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
