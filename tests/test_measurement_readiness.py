from __future__ import annotations

import pandas as pd
import pytest

from renca.audit import audit_project
from renca.models import ProjectSpec
from renca.runner import run_analysis
from test_runner import data, payload


def spec_with_node(node: dict[str, object]) -> ProjectSpec:
    project = payload()
    project["nodes"] = [node, {"node_id": "other", "outcome_type": "continuous", "loss": "squared", "delta": 0.01}]
    return ProjectSpec.model_validate(project)


def test_bounded_composite_is_approved_when_in_bounds_and_unsaturated() -> None:
    spec = spec_with_node({"node_id": "score", "outcome_type": "continuous", "loss": "squared", "delta": .01, "measurement_level": "bounded_composite", "scale_min": 0, "scale_max": 10, "continuous_approximation": True})
    values = list(range(10)) * 6
    report = audit_project(pd.DataFrame({"score": values, "other": list(range(60))}), spec)
    assert report.eligible and report.measurement_outcomes["score"]["confirmatory_eligible"] is True


@pytest.mark.parametrize("values,code", [([0] * 10 + list(range(1, 10)) * 5, "boundary_saturation"), ([0, 1, 2, 3] * 15, "insufficient_scale_resolution"), ([-1] + list(range(1, 10)) * 6, "scale_bounds")])
def test_bounded_composite_failures_are_visible(values: list[int], code: str) -> None:
    spec = spec_with_node({"node_id": "score", "outcome_type": "continuous", "loss": "squared", "delta": .01, "measurement_level": "bounded_composite", "scale_min": 0, "scale_max": 10, "continuous_approximation": True})
    report = audit_project(pd.DataFrame({"score": values, "other": list(range(len(values)))}), spec)
    assert not report.eligible and any(check.code == code for check in report.checks)


def test_ordinal_item_is_ineligible_and_runner_stops(tmp_path) -> None:
    project = payload(); project["nodes"][0]["measurement_level"] = "ordinal_item"
    with pytest.raises(ValueError, match="Audit failed"):
        run_analysis(data(), ProjectSpec.model_validate(project), tmp_path / "out")
    assert not (tmp_path / "out").exists()
