"""Independent calibration scenario families for the VIMP decision rule."""

from __future__ import annotations

import numpy as np
import pandas as pd

from renca.calibration.validation import REQUIRED_SCENARIO_FAMILIES


def generate_scenario(scenario_family: str, n: int, seed: int, delta: float) -> pd.DataFrame:
    """Generate one tabular DGP, retaining raw bounded values when relevant."""
    if scenario_family not in REQUIRED_SCENARIO_FAMILIES:
        raise ValueError(f"unknown calibration scenario family: {scenario_family}")
    if n < 30:
        raise ValueError("calibration scenarios require at least 30 rows")
    rng = np.random.default_rng(seed)
    z, x, error = rng.normal(size=(3, n))
    beta = float(np.sqrt(delta / max(1 - delta, 1e-12)))
    if scenario_family == "continuous_linear_boundary_v1":
        y = z + beta * x + error
    elif scenario_family == "bounded_composite_unsaturated_v1":
        y = 5 + 2.2 * np.tanh((z + beta * x + error) / 2)
    elif scenario_family == "bounded_composite_saturated_v1":
        y = np.clip(1.2 + z + beta * x + error, 0, 10)
    elif scenario_family == "nonlinear_continuous_v1":
        y = np.sin(z) + beta * np.sin(x) + error
    else:  # learner_misspecification_v1: the linear candidate is misspecified.
        y = z * x + beta * (x**2 - 1) + error
    return pd.DataFrame({"z": z, "x": x, "y": y})
