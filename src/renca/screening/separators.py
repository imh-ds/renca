"""Selection-only candidate separator ranking and Parquet evidence output."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Literal

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
    selection_method: Literal["cross_fitted_bidirectional_loss"]
    admissibility_flags: list[str]


def _loss(data: pd.DataFrame, target: str, added: str, separator: tuple[str, ...], seed: int) -> float:
    features = list(separator) + [added]
    losses: list[float] = []
    for train, test in KFold(n_splits=min(3, len(data)), shuffle=True, random_state=seed).split(data):
        model = Ridge(alpha=1.0).fit(data.iloc[train][features], data.iloc[train][target])
        residual = data.iloc[test][target] - model.predict(data.iloc[test][features])
        losses.extend((residual ** 2).tolist())
    return float(sum(losses) / len(losses))


def rank_separators(data: pd.DataFrame, node_specs: list[NodeSpec], neighborhoods: dict[str, list[str]], config: ScreeningSpec, *, seed: int) -> list[SeparatorCandidate]:
    """Rank candidate sets by cross-fitted bidirectional predictive loss."""
    nodes = sorted(node.node_id for node in node_specs)
    result: list[SeparatorCandidate] = []
    for node_i, node_j in itertools.combinations(nodes, 2):
        pool = sorted((set(neighborhoods[node_i]) | set(neighborhoods[node_j])) - {node_i, node_j})
        sets = [()] + [combo for size in range(1, config.max_separator_size + 1) for combo in itertools.combinations(pool, size)]
        scored = []
        for separator in sets:
            score = _loss(data, node_i, node_j, separator, seed) + _loss(data, node_j, node_i, separator, seed)
            scored.append((score, separator))
        for rank, (score, separator) in enumerate(sorted(scored, key=lambda item: (item[0], item[1]))[: config.separators_per_pair], start=1):
            result.append(SeparatorCandidate(pair_id=f"{node_i}--{node_j}", node_i=node_i, node_j=node_j, rank=rank, separator=list(separator), selection_score=score, selection_method="cross_fitted_bidirectional_loss", admissibility_flags=[]))
    return result


def write_separator_candidates(candidates: list[SeparatorCandidate], output_dir: str | Path) -> Path:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "separator_candidates.parquet"
    rows = [{**candidate.model_dump(), "separator": json.dumps(candidate.separator), "admissibility_flags": json.dumps(candidate.admissibility_flags)} for candidate in candidates]
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path
