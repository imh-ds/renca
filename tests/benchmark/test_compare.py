from __future__ import annotations

import pandas as pd
import pytest

from renca.benchmark.compare import DELTA_PROFILES, _d_separated, score_prunes, summarize_benchmark
from renca.benchmark.dgp import BenchmarkGraph, sample_graph
from renca.calibration.registry import CalibrationRegistry
from renca.models import VimpSpec
from renca.runner import default_calibration_registry_path


def chain_graph() -> BenchmarkGraph:
    """v0 -> v1 -> v2 <- v3: one chain and one collider at v1... and at v2."""
    return BenchmarkGraph(
        p=4,
        parents=((), (0,), (1, 3), ()),
        coefficients=((), (.7,), (.5, .5), ()),
        forms=((), ("linear",), ("linear", "linear"), ()),
        noise_sd=(1.0, .7, .7, 1.0),
        family="linear_gaussian",
    )


def test_d_separation_handles_chains_and_colliders() -> None:
    """Used to report whether a chosen separator was valid, so its collider case must be right."""
    graph = chain_graph()
    assert _d_separated(graph, "v00", "v02", {"v01"})       # chain blocked by the middle node
    assert not _d_separated(graph, "v00", "v02", set())     # unblocked chain
    assert _d_separated(graph, "v00", "v03", set())         # marginally independent parents
    assert not _d_separated(graph, "v00", "v03", {"v02"})   # conditioning on the collider opens it


def test_scoring_counts_only_declared_absence_as_a_prune() -> None:
    graph = sample_graph(p=6, seed=1, family="linear_gaussian")
    adjacent = sorted(graph.adjacent_pairs(), key=sorted)
    nonadjacent = sorted(graph.nonadjacent_pairs(), key=sorted)
    absent = graph.nonadjacent_pairs()
    scored = score_prunes({adjacent[0], nonadjacent[0], nonadjacent[1]}, graph, absent)

    assert scored["false_prunes"] == 1
    assert scored["true_prunes"] == 2
    assert scored["familywise_false_prune"] is True
    assert score_prunes(set(), graph, absent)["familywise_false_prune"] is False


def test_an_edge_below_delta_is_not_charged_as_a_false_prune() -> None:
    """The pilot's sharpest result: at delta=0.20 every adjacency this method pruned was an
    edge whose oracle Theta sat under 0.20 in both directions. Scoring those as errors would
    report a 43% false-prune rate for a run that made none."""
    graph = sample_graph(p=6, seed=1, family="linear_gaussian")
    weak = sorted(graph.adjacent_pairs(), key=sorted)[0]
    scored = score_prunes({weak}, graph, graph.nonadjacent_pairs() | {weak})

    assert scored["false_prunes"] == 1            # graphical scoring still charges it
    assert scored["practical_false_prunes"] == 0  # practical scoring does not
    assert scored["practical_true_prunes"] == 1


def test_every_delta_profile_named_by_the_study_is_packaged() -> None:
    """The study certifies at three resolutions; a missing profile would silently downgrade
    an arm to `calibration_failed` and score it as pruning nothing."""
    registry = CalibrationRegistry.load(default_calibration_registry_path())
    packaged = {record.profile_id for record in registry.records}
    assert set(DELTA_PROFILES.values()) <= packaged
    for delta, profile_id in DELTA_PROFILES.items():
        record = next(item for item in registry.records if item.profile_id == profile_id)
        assert record.delta_target == pytest.approx(delta)
        assert record.inference_rows == 300
        assert record.status == "validated"


def test_the_calibrated_sample_size_yields_exactly_the_profiled_inference_rows() -> None:
    """375 rows at a 0.2 selection fraction is the only size the packaged profiles bind to."""
    from renca.benchmark.compare import CALIBRATED_SAMPLE_SIZE, benchmark_project_spec
    from renca.benchmark.dgp import generate_sample
    from renca.screening import create_outer_split

    graph = sample_graph(p=15, seed=0, family="linear_gaussian")
    data = generate_sample(graph, n=CALIBRATED_SAMPLE_SIZE, seed=1)
    spec = benchmark_project_spec(p=15, delta=.05, seed=1, vimp_spec=VimpSpec(), profile_id=None, max_separator_size=1, selection_fraction=.2, inference_folds=5)
    assert len(create_outer_split(data, spec).inference_row_positions) == 300


def test_summary_pools_pair_counts_rather_than_averaging_replication_rates() -> None:
    """Graphs differ in edge count, so averaging per-replication rates would weight a
    sparse graph's few edges as heavily as a dense one's."""
    results = pd.DataFrame([
        {"family": "linear_gaussian", "edge_strength": "realistic", "n": 375, "reference_delta": .05, "method": "pc", "setting": .05, "replicate": 1, "false_prunes": 2, "true_prunes": 40, "edges": 20, "nonedges": 80, "moral_only": 8, "familywise_false_prune": True, "practical_false_prunes": 1, "practical_true_prunes": 41, "practical_present": 19, "practical_absent": 81, "practical_familywise_false_prune": True},
        {"family": "linear_gaussian", "edge_strength": "realistic", "n": 375, "reference_delta": .05, "method": "pc", "setting": .05, "replicate": 2, "false_prunes": 0, "true_prunes": 60, "edges": 30, "nonedges": 120, "moral_only": 12, "familywise_false_prune": False, "practical_false_prunes": 0, "practical_true_prunes": 60, "practical_present": 28, "practical_absent": 122, "practical_familywise_false_prune": False},
    ])
    summary = summarize_benchmark(results).iloc[0]

    assert summary.false_prune_rate == pytest.approx(2 / 50)
    assert summary.true_prune_rate == pytest.approx(100 / 200)
    assert summary.familywise_error_rate == pytest.approx(.5)
    assert summary.practical_false_prune_rate == pytest.approx(1 / 47)
