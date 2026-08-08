from __future__ import annotations

import json

import pytest

from renca.models import ProjectSpec
from renca.reporting.fit import NetworkFit, PairFit
from renca.reporting.resolution_path import build_resolution_path, write_resolution_path


def spec(delta: float = .05, grid: list[float] | None = None) -> ProjectSpec:
    payload: dict[str, object] = {
        "schema_version": "1.7.0",
        "analysis_id": "dddb2c74-2a57-4561-8afc-2c56e086674b",
        "preanalysis_reference": "fixture",
        "seed": 1,
        "missing_data_policy": "complete_case",
        "design": {"sampling_unit": "iid", "cluster_id_column": None},
        "nodes": [{"node_id": name, "outcome_type": "continuous", "loss": "squared", "delta": delta} for name in ("x", "y")],
    }
    if grid is not None:
        payload["resolution_grid"] = grid
    return ProjectSpec.model_validate(payload)


def fit(resolutions: list[float | None], basis: str = "calibrated") -> NetworkFit:
    return NetworkFit(
        analysis_id="dddb2c74-2a57-4561-8afc-2c56e086674b",
        resolution_basis=basis,
        interpretation="fixture",
        pairs=[PairFit(pair_id=f"p{index}", achieved_resolution=value, resolution_basis=basis if value is not None else "unavailable") for index, value in enumerate(resolutions)],
    )


def test_path_counts_pairs_the_data_could_place_below_each_delta() -> None:
    path = build_resolution_path(fit([.01, .08, .30]), spec(grid=[.02, .10, .40]))
    counts = {row.delta: row.resolvable_pairs for row in path.rows}

    assert counts == {.02: 1, .05: 1, .10: 2, .40: 3}
    assert [row.delta for row in path.rows] == [.02, .05, .10, .40]


def test_only_the_primary_delta_is_ever_marked_calibrated() -> None:
    """A resolution other than a node's own delta has no matched profile."""
    path = build_resolution_path(fit([.01, .08]), spec(grid=[.02, .10]))
    calibrated = {row.delta: row.calibrated for row in path.rows}

    assert calibrated == {.02: False, .05: True, .10: False}
    assert path.certificates_apply_only_at_primary_delta is True
    assert "not certificates" in path.interpretation
    assert "invalidates the error control" in path.interpretation


def test_uncalibrated_runs_mark_every_row_uncalibrated() -> None:
    path = build_resolution_path(fit([.01, .08], basis="normal_approximation"), spec(grid=[.10]))
    assert not any(row.calibrated for row in path.rows)


def test_unmeasurable_pairs_are_excluded_from_the_denominator_not_counted_as_resolved() -> None:
    path = build_resolution_path(fit([.01, None, None]), spec())
    row = path.rows[0]

    assert row.resolvable_pairs == 1
    assert row.measurable_pairs == 1
    assert row.total_pairs == 3


def test_verdict_names_a_coarser_resolution_that_would_settle_more() -> None:
    """The point of the path: distinguish 'question too fine' from 'variables related'."""
    reachable = build_resolution_path(fit([.30, .30, .30]), spec(grid=[.40]))
    assert "coarser resolution of 0.400" in reachable.interpretation

    already = build_resolution_path(fit([.001, .002]), spec(grid=[.40]))
    assert "coarser resolution" not in already.interpretation


def test_grid_defaults_to_the_primary_delta_alone() -> None:
    path = build_resolution_path(fit([.01]), spec())
    assert [row.delta for row in path.rows] == [.05]
    assert path.rows[0].is_primary is True


def test_artifacts_are_canonical_and_carry_the_no_certificate_flag(tmp_path) -> None:
    path = build_resolution_path(fit([.01, .08]), spec(grid=[.10]))
    parquet, json_path = write_resolution_path(path, tmp_path)
    payload = json.loads(json_path.read_text())

    assert parquet.name == "resolution_path.parquet"
    assert payload["certificates_apply_only_at_primary_delta"] is True
    assert write_resolution_path(path, tmp_path)[1].read_bytes() == json_path.read_bytes()


def test_grid_rejects_a_nonpositive_resolution() -> None:
    with pytest.raises(ValueError):
        spec(grid=[0.0])
