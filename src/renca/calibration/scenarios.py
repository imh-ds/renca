"""Frozen, boundary-tunable scenario families for VIMP calibration."""

from __future__ import annotations

import numpy as np
import pandas as pd

from renca.calibration.validation import REQUIRED_SCENARIO_FAMILIES


def _signal(delta: float) -> float:
    return float(np.sqrt(delta / max(1 - delta, 1e-12)))


def _draw(family: str, n: int, seed: int, signal: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    z, x, error = rng.normal(size=(3, n))
    if family == "continuous_linear_boundary_v1":
        y = z + signal * x + error
    elif family == "bounded_composite_unsaturated_v1":
        y = 5 + 1.5 * np.tanh(z) + signal * np.tanh(x) + .5 * np.tanh(error)
    elif family == "bounded_composite_saturated_v1":
        y = 5 + 1.5 * np.tanh(z) + signal * np.tanh(x) + .5 * np.tanh(error)
        y = np.where(z < -1.2815515655, 0.0, y)  # exactly 10% lower-bound mass in population.
    elif family == "nonlinear_continuous_v1":
        y = np.sin(z) + signal * np.sin(x) + error
    elif family == "learner_misspecification_v1":
        y = signal * (z * x + x**2 - 1) + error
    else:
        raise ValueError(f"unknown calibration scenario family: {family}")
    return z, x, error, y


def generate_scenario(scenario_family: str, n: int, seed: int, delta: float, *, signal: float | None = None) -> pd.DataFrame:
    """Generate one tabular DGP, retaining bounded-composite scale values."""
    if scenario_family not in REQUIRED_SCENARIO_FAMILIES:
        raise ValueError(f"unknown calibration scenario family: {scenario_family}")
    if n < 30:
        raise ValueError("calibration scenarios require at least 30 rows")
    z, x, _, y = _draw(scenario_family, n, seed, _signal(delta) if signal is None else signal)
    return pd.DataFrame({"z": z, "x": x, "y": y})


def oracle_theta(scenario_family: str, signal: float, *, seed: int = 991, n: int = 200_000) -> float:
    """Common-random-number Monte Carlo oracle for the population squared-loss VIMP."""
    z, x, error, y = _draw(scenario_family, n, seed, signal)
    if scenario_family == "continuous_linear_boundary_v1":
        reduced, full = z, z + signal * x
    elif scenario_family == "bounded_composite_unsaturated_v1":
        reduced, full = 5 + 1.5 * np.tanh(z), 5 + 1.5 * np.tanh(z) + signal * np.tanh(x)
    elif scenario_family == "bounded_composite_saturated_v1":
        active = z >= -1.2815515655
        reduced = np.where(active, 5 + 1.5 * np.tanh(z), 0.0)
        full = np.where(active, 5 + 1.5 * np.tanh(z) + signal * np.tanh(x), 0.0)
    elif scenario_family == "nonlinear_continuous_v1":
        reduced, full = np.sin(z), np.sin(z) + signal * np.sin(x)
    else:
        reduced, full = np.zeros(n), signal * (z * x + x**2 - 1)
    psi = float(np.mean((y - reduced) ** 2 - (y - full) ** 2))
    null_risk = float(np.mean((y - y.mean()) ** 2))
    return psi / null_risk


def tune_boundary_signal(scenario_family: str, delta: float, *, tolerance: float = .002, seed: int = 991, n: int = 200_000) -> tuple[float, float]:
    """Solve the frozen DGP signal so its oracle normalized VIMP reaches delta."""
    low, high = 0.0, 1.0
    while oracle_theta(scenario_family, high, seed=seed, n=n) < delta:
        high *= 2
    for _ in range(28):
        middle = (low + high) / 2
        if oracle_theta(scenario_family, middle, seed=seed, n=n) < delta:
            low = middle
        else:
            high = middle
    signal = (low + high) / 2
    value = oracle_theta(scenario_family, signal, seed=seed, n=n)
    if abs(value - delta) > tolerance:
        raise RuntimeError("boundary tuning did not reach the requested tolerance")
    return signal, value
