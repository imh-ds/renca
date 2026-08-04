"""Typed predictive ResolutionGraph artifacts and portable GraphML export."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

from pydantic import Field

from renca.certification import EdgeCertificate, PairState
from renca.models import Model, ProjectSpec, SCHEMA_VERSION


class ResolutionNode(Model):
    node_id: str
    outcome_type: str
    measurement_level: str
    primary_delta: float
    layout_x: float
    layout_y: float


class ResolutionPair(Model):
    pair_id: str
    source: str
    target: str
    state: PairState
    separator: list[str]
    delta_source: float
    delta_target: float
    theta_source_from_target: float | None = None
    theta_target_from_source: float | None = None
    adjusted_p: float | None = None
    error_control: str
    predictive_status: PairState
    causal_status: Literal["not_yet_causal"] = "not_yet_causal"
    render_visible: bool


class ResolutionGraph(Model):
    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    nodes: list[ResolutionNode]
    pairs: list[ResolutionPair]
    sensitivity_deltas: list[float] = Field(default_factory=list)
    interpretation: Literal["predictive_not_causal"] = "predictive_not_causal"


def _layout(index: int, count: int) -> tuple[float, float]:
    angle = (2 * math.pi * index / count) - (math.pi / 2)
    return round(math.cos(angle), 6), round(math.sin(angle), 6)


def build_resolution_graph(certificates: list[EdgeCertificate], project_spec: ProjectSpec) -> ResolutionGraph:
    """Build an auditable three-state predictive graph from pair certificates."""
    nodes = []
    sorted_specs = sorted(project_spec.nodes, key=lambda node: node.node_id)
    for index, node in enumerate(sorted_specs):
        x, y = _layout(index, len(sorted_specs))
        nodes.append(ResolutionNode(node_id=node.node_id, outcome_type=node.outcome_type.value, measurement_level=node.measurement_level.value, primary_delta=node.delta, layout_x=x, layout_y=y))
    pairs = []
    for certificate in sorted(certificates, key=lambda item: item.pair_id):
        source, target = certificate.pair_id.split("--", 1)
        pairs.append(ResolutionPair(pair_id=certificate.pair_id, source=source, target=target, state=certificate.state, separator=certificate.separator, delta_source=certificate.delta_i, delta_target=certificate.delta_j, theta_source_from_target=certificate.theta_i_from_j, theta_target_from_source=certificate.theta_j_from_i, adjusted_p=certificate.adjusted_p, error_control=certificate.error_control, predictive_status=certificate.state, causal_status=certificate.causal_status, render_visible=certificate.state is not PairState.CERTIFIED_NONEDGE))
    return ResolutionGraph(analysis_id=str(project_spec.analysis_id), nodes=nodes, pairs=pairs)


def write_resolution_graph(graph: ResolutionGraph, output_dir: str | Path) -> tuple[Path, Path]:
    """Write canonical JSON and standards-compatible GraphML evidence artifacts."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "resolution_graph.json"
    json_path.write_text(json.dumps(graph.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")

    namespace = "http://graphml.graphdrawing.org/xmlns"
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}graphml")
    node_keys = [key for key in ResolutionNode.model_fields if key != "node_id"]
    pair_keys = [key for key in ResolutionPair.model_fields if key not in {"pair_id", "source", "target"}]
    for key in node_keys:
        ET.SubElement(root, f"{{{namespace}}}key", {"id": key, "for": "node", "attr.name": key, "attr.type": "string"})
    for key in pair_keys:
        ET.SubElement(root, f"{{{namespace}}}key", {"id": key, "for": "edge", "attr.name": key, "attr.type": "string"})
    graph_element = ET.SubElement(root, f"{{{namespace}}}graph", {"id": "resolution_graph", "edgedefault": "undirected"})
    for node in graph.nodes:
        element = ET.SubElement(graph_element, f"{{{namespace}}}node", {"id": node.node_id})
        for key, value in node.model_dump(mode="json").items():
            if key != "node_id":
                ET.SubElement(element, f"{{{namespace}}}data", {"key": key}).text = str(value).lower() if isinstance(value, bool) else str(value)
    for pair in graph.pairs:
        element = ET.SubElement(graph_element, f"{{{namespace}}}edge", {"id": pair.pair_id, "source": pair.source, "target": pair.target})
        for key, value in pair.model_dump(mode="json").items():
            if key not in {"pair_id", "source", "target"}:
                ET.SubElement(element, f"{{{namespace}}}data", {"key": key}).text = json.dumps(value, separators=(",", ":")) if isinstance(value, list) else str(value).lower() if isinstance(value, bool) else str(value)
    graphml_path = destination / "resolution_graph.graphml"
    ET.ElementTree(root).write(graphml_path, encoding="utf-8", xml_declaration=True)
    return json_path, graphml_path
