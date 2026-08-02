"""Experimental, nested learner-selection strategies for sparse interactions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.model_selection import KFold

from renca.calibration.runner import _inference_manifest
from renca.calibration.scenarios import generate_scenario, tune_boundary_signal
from renca.models import VimpSpec
from renca.vimp.estimate import _fit_predict


NAMES = ["ridge", "quadratic_ridge", "forest"]


def predict(train: pd.DataFrame, valid: pd.DataFrame, features: list[str], seed: int, spec: VimpSpec, strategy: str) -> np.ndarray:
    if not features:
        return np.repeat(train.y.mean(), len(valid))
    repeats = 3 if strategy == "repeated_selection" else 1
    inner_predictions: list[np.ndarray] = []
    losses: dict[str, list[float]] = {name: [] for name in NAMES}
    for repeat in range(repeats):
        splitter = KFold(n_splits=3, shuffle=True, random_state=seed + repeat)
        for inner_train, inner_valid in splitter.split(train):
            for name in NAMES:
                prediction = _fit_predict(name, train.iloc[inner_train], train.iloc[inner_valid], "y", features, False, spec, seed + repeat)
                losses[name].extend(((train.iloc[inner_valid].y.to_numpy() - prediction) ** 2).tolist())
    if strategy == "blend":
        # One nested OOF matrix; convex weights prevent extrapolation and overfitting.
        matrix = np.empty((len(train), len(NAMES)))
        for column, name in enumerate(NAMES):
            for inner_train, inner_valid in KFold(n_splits=3, shuffle=True, random_state=seed).split(train):
                matrix[inner_valid, column] = _fit_predict(name, train.iloc[inner_train], train.iloc[inner_valid], "y", features, False, spec, seed)
        result = minimize(lambda w: float(np.mean((train.y.to_numpy() - matrix @ w) ** 2)), np.repeat(1 / len(NAMES), len(NAMES)), bounds=[(0, 1)] * len(NAMES), constraints={"type": "eq", "fun": lambda w: w.sum() - 1})
        weights = result.x if result.success else np.array([1.0, 0.0, 0.0])
        return sum(weight * _fit_predict(name, train, valid, "y", features, False, spec, seed) for weight, name in zip(weights, NAMES))
    selected = min(NAMES, key=lambda name: float(np.mean(losses[name])))
    return _fit_predict(selected, train, valid, "y", features, False, spec, seed)


def one(data: pd.DataFrame, seed: int, spec: VimpSpec, strategy: str) -> dict[str, float | bool]:
    manifest = _inference_manifest(len(data), seed, 5); reduced_loss: list[float] = []; full_loss: list[float] = []
    for fold in range(5):
        validation = np.array([row for row, value in manifest.inference_fold_by_row_position.items() if value == fold])
        training = np.setdiff1d(np.arange(len(data)), validation)
        train, valid = data.iloc[training], data.iloc[validation]
        reduced = predict(train, valid, ["z"], seed + fold, spec, strategy)
        full = predict(train, valid, ["z", "x"], seed + fold, spec, strategy)
        reduced_loss.extend((valid.y.to_numpy() - reduced) ** 2); full_loss.extend((valid.y.to_numpy() - full) ** 2)
    return {"full_worse": float(np.mean(full_loss)) > float(np.mean(reduced_loss)), "risk_gap": float(np.mean(full_loss) - np.mean(reduced_loss))}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--replications", type=int, default=10); args = parser.parse_args()
    family = "learner_misspecification_v1"; signal = tune_boundary_signal(family, .05, n=50_000)[0]; spec = VimpSpec(forest_trees=10)
    rows = []
    for strategy in ("current_selection", "repeated_selection", "blend"):
        for replicate in range(args.replications):
            seed = 20260807 + replicate; result = one(generate_scenario(family, 300, seed, .05, signal=signal), seed, spec, strategy)
            rows.append({"strategy": strategy, "replicate": replicate, **result})
    frame = pd.DataFrame(rows); args.output.parent.mkdir(parents=True, exist_ok=True); frame.to_csv(args.output, index=False)
    print(frame.groupby("strategy").agg(abstention_rate=("full_worse", "mean"), mean_risk_gap=("risk_gap", "mean")).to_string())


if __name__ == "__main__":
    main()
