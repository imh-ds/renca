"""High-recall, selection-only neighborhood screening."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge

from renca.models import NodeSpec, ScreeningSpec


def screen_neighbors(data: pd.DataFrame, node_specs: list[NodeSpec], config: ScreeningSpec, *, seed: int) -> dict[str, list[str]]:
    """Return a deterministic high-recall union of marginal, ridge, and forest screens."""
    node_ids = [node.node_id for node in node_specs]
    if missing := sorted(set(node_ids) - set(data.columns)):
        raise ValueError(f"Missing node columns: {', '.join(missing)}")
    values = data[node_ids].astype(float)
    if values.isna().any().any():
        raise ValueError("Selection data contains missing node values")
    neighborhoods: dict[str, list[str]] = {}
    for target in node_ids:
        predictors = [node for node in node_ids if node != target]
        matrix = values[predictors].to_numpy()
        outcome = values[target].to_numpy()
        marginal = np.abs(np.corrcoef(np.column_stack((outcome, matrix)), rowvar=False)[0, 1:])
        ridge = np.abs(Ridge(alpha=1.0).fit(matrix, outcome).coef_)
        forest = RandomForestRegressor(n_estimators=100, max_features=1.0, random_state=seed).fit(matrix, outcome).feature_importances_
        ranked = sorted(predictors, key=lambda node: (-max(marginal[predictors.index(node)], ridge[predictors.index(node)], forest[predictors.index(node)]), node))
        neighborhoods[target] = ranked[: config.max_neighbors]
    return neighborhoods
