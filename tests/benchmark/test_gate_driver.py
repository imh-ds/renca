from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))
comparator_gate = pytest.importorskip("simulations.comparator_gate")

needs_causal_learn = pytest.mark.skipif(
    importlib.util.find_spec("causallearn") is None,
    reason="causal-learn is not installed; install the 'comparators' extra",
)


def shard_arguments(output: Path, **overrides: object) -> argparse.Namespace:
    defaults = {
        "start": 0, "count": 2, "output": output, "family": "linear_gaussian", "edge_strength": "realistic", "n": 375, "p": 6,
        "max_separator_size": 1, "alpha": .05, "seed": 11, "workers": 1, "calibration_registry": None,
        "learner_library_version": "v4_cubic_blend", "indep_test": "fisherz", "skip_renca": True,
    }
    return argparse.Namespace(**{**defaults, **overrides})


@needs_causal_learn
def test_shards_round_trip_through_summarize_into_a_verdict(tmp_path: Path) -> None:
    """The driver is what the workflow actually runs, so its assembly path is exercised
    rather than only the scoring functions it calls."""
    comparator_gate.shard(shard_arguments(tmp_path / "shards" / "a.parquet", start=0))
    comparator_gate.shard(shard_arguments(tmp_path / "shards" / "b.parquet", start=2))

    output = tmp_path / "evidence"
    comparator_gate.summarize(argparse.Namespace(shards=tmp_path / "shards", output=output, alpha=.05))
    verdict = json.loads((output / "comparator_gate_verdict.json").read_text())
    summary = pd.read_parquet(output / "comparator_gate_summary.parquet")

    assert set(summary.method) == set(comparator_gate.COMPARATOR_SETTINGS)
    # Each baseline is scored once per resolution the method would be tested at.
    assert set(summary.reference_delta) == set(comparator_gate.DEFAULT_DELTAS)
    assert verdict["verdict"] == "STOP"  # no arm of the method was run, so the gate is unassessable
    assert "no arm of this method was scored" in verdict["reason"]


@needs_causal_learn
def test_overlapping_shards_are_refused_rather_than_double_counted(tmp_path: Path) -> None:
    """Pooled counts are sums, so a duplicated shard would inflate every rate silently."""
    comparator_gate.shard(shard_arguments(tmp_path / "shards" / "a.parquet", start=0))
    comparator_gate.shard(shard_arguments(tmp_path / "shards" / "duplicate.parquet", start=0))

    with pytest.raises(ValueError, match="duplicate"):
        comparator_gate.summarize(argparse.Namespace(shards=tmp_path / "shards", output=tmp_path / "evidence", alpha=.05))


def test_replicate_seeds_depend_only_on_the_index(tmp_path: Path) -> None:
    """Shard boundaries must not change results, or a rerun with a different split would
    produce different evidence."""
    contiguous = [comparator_gate.replicate_seed(7, index) for index in range(6)]
    split = [comparator_gate.replicate_seed(7, index) for index in range(3)] + [comparator_gate.replicate_seed(7, index) for index in range(3, 6)]
    assert contiguous == split
    assert len(set(contiguous)) == 6
