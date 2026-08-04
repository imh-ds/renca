"""Selection-only candidate separator ranking and Parquet evidence output."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold

from renca.models import Model, NodeSpec, ScreeningSpec


class SeparatorCandidate(Model):
    pair_id: str
    node_i: str
    node_j: str
    rank: int
    separator: list[str]
    selection_score: float
    selection_method: Literal["cross_fitted_bidirectional_gain"]
    admissibility_flags: list[str]


def _cv_loss(data: pd.DataFrame, target: str, features: list[str], seed: int, cache: dict[tuple[str, tuple[str, ...]], float]) -> float:
    """Cross-fitted squared loss; an empty feature set scores the intercept-only model."""
    key = (target, tuple(features))
    if key not in cache:
        losses: list[float] = []
        for train, test in KFold(n_splits=min(3, len(data)), shuffle=True, random_state=seed).split(data):
            fitted, held_out = data.iloc[train], data.iloc[test]
            if features:
                prediction = Ridge(alpha=1.0).fit(fitted[features], fitted[target]).predict(held_out[features])
            else:
                prediction = np.repeat(fitted[target].to_numpy().mean(), len(held_out))
            losses.extend(((held_out[target] - prediction) ** 2).tolist())
        cache[key] = float(sum(losses) / len(losses))
    return cache[key]


def _bidirectional_gain(data: pd.DataFrame, node_i: str, node_j: str, separator: tuple[str, ...], seed: int, null_risk: dict[str, float], cache: dict[tuple[str, tuple[str, ...]], float]) -> float:
    """Residual normalized bidirectional conditional importance left by `separator`.

    This mirrors the confirmatory contrast ``(R(S) - R(S + added)) / R(empty)`` in both
    directions, so a lower score means the separator came closer to practically separating the
    pair. Ranking on the expanded-model risk alone would instead reward separators that merely
    predict the two targets well, which favours colliders and strong common predictors.
    """
    columns = list(separator)
    forward = (_cv_loss(data, node_i, columns, seed, cache) - _cv_loss(data, node_i, columns + [node_j], seed, cache)) / null_risk[node_i]
    reverse = (_cv_loss(data, node_j, columns, seed, cache) - _cv_loss(data, node_j, columns + [node_i], seed, cache)) / null_risk[node_j]
    return forward + reverse


def rank_separators(data: pd.DataFrame, node_specs: list[NodeSpec], neighborhoods: dict[str, list[str]], config: ScreeningSpec, *, seed: int) -> list[SeparatorCandidate]:
    """Rank candidate sets by cross-fitted bidirectional conditional importance."""
    nodes = sorted(node.node_id for node in node_specs)
    cache: dict[tuple[str, tuple[str, ...]], float] = {}
    null_risk = {node: _cv_loss(data, node, [], seed, cache) for node in nodes}
    if degenerate := sorted(node for node, risk in null_risk.items() if risk <= 0):
        raise ValueError(f"Cannot rank separators against a nonpositive null risk: {', '.join(degenerate)}")
    result: list[SeparatorCandidate] = []
    for node_i, node_j in itertools.combinations(nodes, 2):
        pool = sorted((set(neighborhoods[node_i]) | set(neighborhoods[node_j])) - {node_i, node_j})
        sets = [()] + [combo for size in range(1, config.max_separator_size + 1) for combo in itertools.combinations(pool, size)]
        scored = [(_bidirectional_gain(data, node_i, node_j, separator, seed, null_risk, cache), separator) for separator in sets]
        for rank, (score, separator) in enumerate(sorted(scored, key=lambda item: (item[0], item[1]))[: config.separators_per_pair], start=1):
            result.append(SeparatorCandidate(pair_id=f"{node_i}--{node_j}", node_i=node_i, node_j=node_j, rank=rank, separator=list(separator), selection_score=score, selection_method="cross_fitted_bidirectional_gain", admissibility_flags=[]))
    return result


def write_separator_candidates(candidates: list[SeparatorCandidate], output_dir: str | Path) -> Path:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "separator_candidates.parquet"
    rows = [{**candidate.model_dump(), "separator": json.dumps(candidate.separator), "admissibility_flags": json.dumps(candidate.admissibility_flags)} for candidate in candidates]
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path
