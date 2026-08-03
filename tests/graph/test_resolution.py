from __future__ import annotations

import json
from xml.etree import ElementTree as ET

from renca.certification import EdgeCertificate, PairState
from renca.graph import build_resolution_graph, write_resolution_graph
from renca.models import ProjectSpec, write_json_schemas
from renca.reporting.edge_table import _svg


def spec() -> ProjectSpec:
    return ProjectSpec.model_validate({"schema_version": "1.7.0", "analysis_id": "dddb2c74-2a57-4561-8afc-2c56e086674b", "preanalysis_reference": "fixture", "seed": 1, "missing_data_policy": "complete_case", "design": {"sampling_unit": "iid", "cluster_id_column": None}, "nodes": [{"node_id": "a", "outcome_type": "continuous", "loss": "squared", "delta": .05}, {"node_id": "b", "outcome_type": "continuous", "loss": "squared", "delta": .05}, {"node_id": "c", "outcome_type": "continuous", "loss": "squared", "delta": .05}]})


def certificate(pair_id: str, state: PairState) -> EdgeCertificate:
    return EdgeCertificate(pair_id=pair_id, state=state, separator=["c"] if pair_id == "a--b" else [], delta_i=.05, delta_j=.05, theta_i_from_j=.2, theta_j_from_i=.1, adjusted_p=.01 if state is PairState.CERTIFIED_NONEDGE else 1.)


def test_graph_preserves_all_pair_states_and_has_deterministic_layout(tmp_path) -> None:
    graph = build_resolution_graph([certificate("a--b", PairState.CANDIDATE_ADJACENCY), certificate("a--c", PairState.UNRESOLVED), certificate("b--c", PairState.CERTIFIED_NONEDGE)], spec())
    assert [node.node_id for node in graph.nodes] == ["a", "b", "c"]
    assert [pair.state for pair in graph.pairs] == [PairState.CANDIDATE_ADJACENCY, PairState.UNRESOLVED, PairState.CERTIFIED_NONEDGE]
    assert [pair.render_visible for pair in graph.pairs] == [True, True, False]
    assert graph.sensitivity_deltas == [] and graph.interpretation == "predictive_not_causal"
    json_path, graphml_path = write_resolution_graph(graph, tmp_path)
    assert json.loads(json_path.read_text())["pairs"][2]["render_visible"] is False
    root = ET.parse(graphml_path).getroot()
    assert len(root.findall("{http://graphml.graphdrawing.org/xmlns}key")) > 0
    assert len(root.findall(".//{http://graphml.graphdrawing.org/xmlns}edge")) == 3
    assert write_json_schemas(tmp_path / "schemas")["resolution_graph"].exists()


def test_svg_uses_three_state_visual_semantics() -> None:
    graph = build_resolution_graph([certificate("a--b", PairState.CANDIDATE_ADJACENCY), certificate("a--c", PairState.UNRESOLVED), certificate("b--c", PairState.CERTIFIED_NONEDGE)], spec())
    payloads = {pair.pair_id: {"pair_id": pair.pair_id, "state": pair.state.value, "separator": [], "directional_vimp": [], "adjusted_p": pair.adjusted_p, "error_control": pair.error_control, "causal_status": pair.causal_status, "reason": "fixture"} for pair in graph.pairs}
    svg = _svg(graph, payloads)
    assert 'data-pair="a--b"' in svg and 'stroke-dasharray:none' in svg
    assert 'data-pair="a--c"' in svg and 'stroke-dasharray:7 6' in svg
    assert '<line class="resolution-edge" data-pair="b--c"' not in svg
