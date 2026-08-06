"""Tabular and self-contained SVG reporting for predictive resolution graphs."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

from renca.calibration import CalibrationEligibility
from renca.certification import PairState
from renca.graph import ResolutionGraph, ResolutionPair
from renca.reporting.fit import NetworkFit
from renca.vimp import VimpEstimate


def _resolution_reason(pair: ResolutionPair, directions: list[VimpEstimate]) -> str:
    statuses = sorted({estimate.status for estimate in directions})
    calibration = sorted({estimate.calibration_status for estimate in directions})
    if "calibrated_success" not in calibration:
        return "Certification unavailable: the analysis is outside the validated calibration profile."
    if "full_worse_than_reduced" in statuses:
        return "Unresolved: the full learner performed worse than the reduced learner; investigate learner adequacy."
    if any(status != "success" for status in statuses):
        return "Unresolved: directional VIMP estimation abstained or failed; inspect diagnostics."
    if pair.state is PairState.UNRESOLVED:
        return "Unresolved: neither practical separation nor searched-family inseparability was established."
    if pair.state is PairState.CANDIDATE_ADJACENCY:
        return "Candidate adjacency: no searched separator established practical separation; this is not a causal edge."
    return "Certified practical nonedge under the matched predictive calibration profile; this is not a causal nonedge."


def _pair_payload(pair: ResolutionPair, directions: list[VimpEstimate]) -> dict[str, object]:
    return {
        "pair_id": pair.pair_id,
        "state": pair.state.value,
        "separator": pair.separator,
        "directional_vimp": [
            {"target": estimate.target, "added_variable": estimate.added_variable, "theta_hat": estimate.theta_hat, "lower_ci": estimate.lower_ci, "upper_ci": estimate.upper_ci, "delta": estimate.delta_target, "calibration_status": estimate.calibration_status, "status": estimate.status}
            for estimate in directions
        ],
        "adjusted_p": pair.adjusted_p,
        "error_control": pair.error_control,
        "causal_status": pair.causal_status,
        "reason": _resolution_reason(pair, directions),
    }


def _svg(graph: ResolutionGraph, payloads: dict[str, dict[str, object]]) -> str:
    positions = {node.node_id: (250 + 175 * node.layout_x, 250 + 175 * node.layout_y) for node in graph.nodes}
    visible = [pair for pair in graph.pairs if pair.render_visible]
    edges: list[str] = []
    for pair in visible:
        x1, y1 = positions[pair.source]; x2, y2 = positions[pair.target]
        strength = max(value or 0 for value in (pair.theta_source_from_target, pair.theta_target_from_source))
        width = min(10, 2 + 16 * strength)
        style = "stroke:#334155;stroke-dasharray:none;opacity:1" if pair.state is PairState.CANDIDATE_ADJACENCY else "stroke:#64748b;stroke-dasharray:7 6;opacity:.62"
        edges.append(f'<line class="resolution-edge" data-pair="{html.escape(pair.pair_id)}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" style="{style};stroke-width:{width:.2f}" tabindex="0" role="button"><title>{html.escape(pair.pair_id)}</title></line>')
    nodes = [f'<circle cx="{positions[node.node_id][0]:.1f}" cy="{positions[node.node_id][1]:.1f}" r="27" class="node"/><text x="{positions[node.node_id][0]:.1f}" y="{positions[node.node_id][1] + 5:.1f}" class="node-label">{html.escape(node.node_id)}</text>' for node in graph.nodes]
    controls = "".join(f'<button class="pair-control" data-pair="{html.escape(pair.pair_id)}">{html.escape(pair.pair_id)} — {html.escape(pair.state.value)}</button>' for pair in graph.pairs)
    initial = next((pair.pair_id for pair in visible), graph.pairs[0].pair_id if graph.pairs else "")
    payload = json.dumps(payloads, sort_keys=True).replace("</", "<\\/")
    return f'''<section class="resolution-graph"><h2>Predictive ResolutionGraph</h2><p class="warning">Predictive evidence only — not causal; all pairs remain <code>not_yet_causal</code>.</p><div class="legend"><span class="legend-candidate">Solid: candidate adjacency</span><span class="legend-unresolved">Dashed: unresolved</span><span>Absent: certified practical nonedge</span><span>Line width: larger directional predictive importance</span></div><div class="graph-layout"><svg viewBox="0 0 500 500" aria-label="Predictive resolution graph" role="img">{''.join(edges)}{''.join(nodes)}</svg><div class="graph-details"><h3>Pair evidence</h3><div id="pair-panel"></div><div class="pair-controls">{controls}</div></div></div></section><script>const pairEvidence=JSON.parse('{payload}');const panel=document.getElementById('pair-panel');function format(v){{return v===null||v===undefined?'—':Number(v).toFixed(4)}}function showPair(id){{const p=pairEvidence[id];if(!p)return;const directions=p.directional_vimp.map(d=>`<li>${{d.added_variable}} → ${{d.target}}: θ=${{format(d.theta_hat)}} [${{format(d.lower_ci)}}, ${{format(d.upper_ci)}}], δ=${{format(d.delta)}} (${{d.status}}, ${{d.calibration_status}})</li>`).join('');panel.innerHTML=`<p><strong>${{p.pair_id}}</strong> — ${{p.state}}</p><p>${{p.reason}}</p><ul><li>Separator: ${{p.separator.length?p.separator.join(', '):'none'}}</li><li>Holm-adjusted p: ${{format(p.adjusted_p)}}</li><li>Error control: ${{p.error_control}}</li><li>Causal status: ${{p.causal_status}}</li>${{directions}}</ul>`;}}document.querySelectorAll('[data-pair]').forEach(el=>{{el.addEventListener('click',()=>showPair(el.dataset.pair));el.addEventListener('keydown',e=>{{if(e.key==='Enter'||e.key===' ')showPair(el.dataset.pair)}})}});showPair('{html.escape(initial)}');</script>'''


def _fit_block(fit: NetworkFit | None) -> str:
    """Lead with how much the analysis could resolve, before any pair state is shown."""
    if fit is None:
        return ""
    def show(value: float | None) -> str:
        return "&mdash;" if value is None else f"{value:.4f}"
    degenerate = fit.predictive_adequacy_median is not None and fit.predictive_adequacy_median <= 0
    return (
        f'<section class="fit{" fit-degenerate" if degenerate else ""}"><h2>Network fit</h2>'
        f'<p class="fit-verdict">{html.escape(fit.interpretation)}</p>'
        f'<table><tr><th>Predictive adequacy (median)</th><td>{show(fit.predictive_adequacy_median)}</td>'
        f'<th>Predictive adequacy (minimum)</th><td>{show(fit.predictive_adequacy_minimum)}</td></tr>'
        f'<tr><th>Resolution floor (median)</th><td>{show(fit.resolution_floor_median)}</td>'
        f'<th>Resolution floor (90th pct)</th><td>{show(fit.resolution_floor_p90)}</td></tr>'
        f'<tr><th>Achieved resolution (median)</th><td>{show(fit.achieved_resolution_median)}</td>'
        f'<th>Achieved resolution (90th pct)</th><td>{show(fit.achieved_resolution_p90)}</td></tr>'
        f'<tr><th>Resolution basis</th><td colspan="3">{html.escape(fit.resolution_basis)}</td></tr></table>'
        '<p class="fit-note">Predictive adequacy is the share of baseline predictive uncertainty the conditioning models removed. It anticipates '
        'how many unrelated pairs will resolve; it is <strong>not</strong> a measure of trustworthiness, and a threshold study found no relationship '
        'between it and false pruning. False pruning is controlled by the calibration profile instead. Adequacy at or below zero is the one hard case: '
        'the contrast underlying every pair state was uninformative. The resolution floor reports precision alone, the finest delta this analysis could '
        'certify at all, while achieved resolution is the per-pair upper limit on Theta and stays meaningful where a pair is unresolved. '
        'Neither index has validated cut-offs and none should be applied.</p></section>'
    )


def write_edge_report(graph: ResolutionGraph, estimates: list[VimpEstimate], output_dir: str | Path, eligibility: list[CalibrationEligibility] | None = None, fit: "NetworkFit | None" = None) -> tuple[Path, Path]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    payloads: dict[str, dict[str, object]] = {}
    pair_fit = {item.pair_id: item for item in (fit.pairs if fit else [])}
    for pair in graph.pairs:
        directions = [estimate for estimate in estimates if estimate.pair_id == pair.pair_id]
        pair_deltas = {estimate.delta_target for estimate in directions}
        pair_eligibility = [item for item in (eligibility or []) if item.delta_target in pair_deltas]
        payload = _pair_payload(pair, directions)
        indices = pair_fit.get(pair.pair_id)
        payload["achieved_resolution"] = indices.achieved_resolution if indices else None
        payload["predictive_adequacy"] = indices.predictive_adequacy if indices else None
        payloads[pair.pair_id] = payload
        rows.append({"pair_id": pair.pair_id, "state": pair.state.value, "separator": ",".join(pair.separator), "adjusted_p": pair.adjusted_p, "causal_status": pair.causal_status, "achieved_resolution": indices.achieved_resolution if indices else None, "resolution_floor": indices.resolution_floor if indices else None, "resolution_basis": indices.resolution_basis if indices else None, "predictive_adequacy": indices.predictive_adequacy if indices else None, "vimp_statuses": ";".join(estimate.status for estimate in directions), "calibration_statuses": ";".join(estimate.calibration_status for estimate in directions), "eligibility_status": ";".join(sorted({item.status for item in pair_eligibility})), "eligibility_mismatch_fields": ";".join(sorted({field for item in pair_eligibility for field in item.mismatch_fields})), "theta_estimates": ";".join(str(estimate.theta_hat) for estimate in directions), "resolution_reason": payload["reason"]})
    frame = pd.DataFrame(rows)
    parquet = destination / "edge_report.parquet"
    frame.to_parquet(parquet, index=False)
    (destination / "calibration_eligibility.json").write_text(json.dumps([item.model_dump(mode="json") for item in (eligibility or [])], sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    eligibility_frame = pd.DataFrame([item.model_dump() for item in (eligibility or [])])
    eligibility_html = eligibility_frame.to_html(index=False) if not eligibility_frame.empty else "<p>No calibration profile was requested; hard certification is unavailable.</p>"
    report = f'<html><head><meta charset="utf-8"><style>body{{font-family:system-ui,sans-serif;margin:2rem;color:#172033}}.warning{{font-weight:600}}.fit{{border:1px solid #cbd5e1;border-left:6px solid #0f766e;padding:.6rem 1rem;margin:1rem 0;border-radius:6px}}.fit-degenerate{{border-left-color:#b91c1c;background:#fef2f2}}.fit-verdict{{font-weight:600}}.fit-note{{font-size:.85rem;color:#475569}}.legend{{display:flex;gap:1rem;flex-wrap:wrap;font-size:.9rem}}.legend-candidate::before{{content:"";display:inline-block;width:2rem;border-top:3px solid #334155;margin-right:.3rem}}.legend-unresolved::before{{content:"";display:inline-block;width:2rem;border-top:3px dashed #64748b;margin-right:.3rem}}.graph-layout{{display:flex;gap:2rem;align-items:flex-start;flex-wrap:wrap}}svg{{width:min(500px,100%);border:1px solid #cbd5e1;border-radius:8px;background:#f8fafc}}.resolution-edge{{cursor:pointer}}.resolution-edge:focus{{outline:4px solid #f59e0b}}.node{{fill:#fff;stroke:#0f172a;stroke-width:2}}.node-label{{font-size:12px;text-anchor:middle;pointer-events:none}}.graph-details{{max-width:42rem}}.pair-controls{{display:grid;gap:.4rem}}.pair-control{{text-align:left}}table{{border-collapse:collapse}}th,td{{border:1px solid #cbd5e1;padding:.4rem;vertical-align:top}}</style></head><body><h1>renca predictive evidence report</h1><p>All conclusions are predictive, not causal. Every result retains <code>not_yet_causal</code>.</p>{_fit_block(fit)}{_svg(graph, payloads)}<h2>Calibration eligibility</h2>{eligibility_html}<h2>Pair evidence table</h2>{frame.to_html(index=False)}</body></html>'
    html_path = destination / "report.html"
    html_path.write_text(report, encoding="utf-8")
    return parquet, html_path
