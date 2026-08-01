"""Cross-fitted directional VIMP estimates and artifact writing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import Field
from scipy.stats import norm
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge

from renca.models import Model, NodeSpec, OutcomeType, VimpSpec
from renca.screening import SplitManifest
from renca.vimp.folds import inference_folds
from renca.vimp.losses import brier_loss, squared_loss


class VimpEstimate(Model):
    pair_id: str
    target: str
    added_variable: str
    separator: list[str]
    psi_hat: float | None = None
    theta_hat: float | None = None
    se_theta: float | None = None
    upper_ci: float | None = None
    lower_ci: float | None = None
    delta_target: float
    p_equivalence: float | None = None
    calibration_status: Literal["uncalibrated", "calibrated_success", "calibration_failed"] = "uncalibrated"
    nuisance_diagnostic: dict[str, object] = Field(default_factory=dict)
    status: Literal["success", "full_worse_than_reduced", "nonpositive_null_risk", "nonfinite_standard_error", "learner_failure"]


def _predictions(train: pd.DataFrame, valid: pd.DataFrame, target: str, features: list[str], binary: bool, spec: VimpSpec, seed: int) -> tuple[np.ndarray, dict[str, float], str]:
    y_train, y_valid = train[target].to_numpy(), valid[target].to_numpy()
    if not features:
        prediction = np.repeat(y_train.mean(), len(valid))
        loss = brier_loss(y_valid, prediction) if binary else squared_loss(y_valid, prediction)
        return prediction, {"intercept": float(loss.mean())}, "intercept"
    if binary:
        ridge = LogisticRegression(C=1 / spec.ridge_alpha, max_iter=500, random_state=seed).fit(train[features], y_train)
        forest = RandomForestRegressor(n_estimators=spec.forest_trees, max_depth=spec.forest_max_depth, random_state=seed).fit(train[features], y_train)
        candidates = {"logistic": ridge.predict_proba(valid[features])[:, 1], "probability_forest": forest.predict(valid[features])}
        loss_fn = brier_loss
    else:
        ridge = Ridge(alpha=spec.ridge_alpha).fit(train[features], y_train)
        forest = RandomForestRegressor(n_estimators=spec.forest_trees, max_depth=spec.forest_max_depth, random_state=seed).fit(train[features], y_train)
        candidates = {"ridge": ridge.predict(valid[features]), "forest": forest.predict(valid[features])}
        loss_fn = squared_loss
    risks = {name: float(loss_fn(y_valid, prediction).mean()) for name, prediction in candidates.items()}
    selected = min(risks, key=risks.get)
    return candidates[selected], risks, selected


def fit_crossfitted_vimp(data_infer: pd.DataFrame, target: str, added_variable: str, separator: list[str], node_spec: NodeSpec, folds: SplitManifest, vimp_spec: VimpSpec) -> VimpEstimate:
    required = {target, added_variable, *separator}
    if missing := sorted(required - set(data_infer.columns)):
        raise ValueError(f"Missing VIMP columns: {', '.join(missing)}")
    binary = node_spec.outcome_type is OutcomeType.BINARY
    try:
        fold_map = inference_folds(folds, len(data_infer))
        reduced_losses: list[float] = []; full_losses: list[float] = []; null_losses: list[float] = []; diagnostics: dict[str, object] = {"folds": {}, "full_worse_than_reduced": False}
        for fold, (train_rows, valid_rows) in fold_map.items():
            train, valid = data_infer.iloc[train_rows], data_infer.iloc[valid_rows]
            reduced, reduced_risks, reduced_name = _predictions(train, valid, target, separator, binary, vimp_spec, folds.seed + fold)
            full, full_risks, full_name = _predictions(train, valid, target, separator + [added_variable], binary, vimp_spec, folds.seed + fold)
            null, _, _ = _predictions(train, valid, target, [], binary, vimp_spec, folds.seed + fold)
            loss_fn = brier_loss if binary else squared_loss; observed = valid[target].to_numpy()
            reduced_loss, full_loss, null_loss = loss_fn(observed, reduced), loss_fn(observed, full), loss_fn(observed, null)
            reduced_losses.extend(reduced_loss); full_losses.extend(full_loss); null_losses.extend(null_loss)
            diagnostics["folds"][str(fold)] = {"train_rows": train_rows.tolist(), "validation_rows": valid_rows.tolist(), "reduced_risks": reduced_risks, "full_risks": full_risks, "reduced_selected": reduced_name, "full_selected": full_name}
        diff, null = np.asarray(reduced_losses) - np.asarray(full_losses), np.asarray(null_losses)
        psi, risk = float(diff.mean()), float(null.mean())
        diagnostics["null_risk"] = risk
        diagnostics["mean_reduced_loss"] = float(np.mean(reduced_losses))
        diagnostics["mean_full_loss"] = float(np.mean(full_losses))
        if risk <= 0: return VimpEstimate(pair_id="--".join(sorted([target, added_variable])), target=target, added_variable=added_variable, separator=separator, delta_target=node_spec.delta, nuisance_diagnostic=diagnostics, status="nonpositive_null_risk")
        theta = psi / risk; influence = (diff - psi - theta * (null - risk)) / risk; se = float(np.sqrt(np.var(influence, ddof=1) / len(influence)))
        if not np.isfinite(se) or se <= 0: return VimpEstimate(pair_id="--".join(sorted([target, added_variable])), target=target, added_variable=added_variable, separator=separator, psi_hat=psi, theta_hat=theta, delta_target=node_spec.delta, nuisance_diagnostic=diagnostics, status="nonfinite_standard_error")
        diagnostics["full_worse_than_reduced"] = float(np.mean(full_losses)) > float(np.mean(reduced_losses))
        z = norm.ppf((1 + vimp_spec.confidence_level) / 2); status = "full_worse_than_reduced" if diagnostics["full_worse_than_reduced"] else "success"
        return VimpEstimate(pair_id="--".join(sorted([target, added_variable])), target=target, added_variable=added_variable, separator=separator, psi_hat=psi, theta_hat=theta, se_theta=se, lower_ci=theta-z*se, upper_ci=theta+z*se, delta_target=node_spec.delta, nuisance_diagnostic=diagnostics, status=status)
    except Exception as error:
        return VimpEstimate(pair_id="--".join(sorted([target, added_variable])), target=target, added_variable=added_variable, separator=separator, delta_target=node_spec.delta, nuisance_diagnostic={"error": str(error)}, status="learner_failure")


def write_vimp_estimates(estimates: list[VimpEstimate], output_dir: str | Path) -> Path:
    destination = Path(output_dir); destination.mkdir(parents=True, exist_ok=True); path = destination / "vimp_estimates.parquet"
    rows = [{**estimate.model_dump(), "separator": json.dumps(estimate.separator), "nuisance_diagnostic": json.dumps(estimate.nuisance_diagnostic, sort_keys=True)} for estimate in estimates]
    pd.DataFrame(rows).to_parquet(path, index=False); return path
