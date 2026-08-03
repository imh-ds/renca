from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
from renca.calibration import CalibrationEligibility
from renca.certification import EdgeCertificate
from renca.vimp import VimpEstimate
def _resolution_reason(c: EdgeCertificate, directions: list[VimpEstimate]) -> str:
    statuses = sorted({e.status for e in directions})
    calibration = sorted({e.calibration_status for e in directions})
    if "calibrated_success" not in calibration:
        return "Certification unavailable: the analysis is outside the validated calibration profile."
    if "full_worse_than_reduced" in statuses:
        return "Unresolved: the full learner performed worse than the reduced learner; investigate learner adequacy."
    if any(status != "success" for status in statuses):
        return "Unresolved: directional VIMP estimation abstained or failed; inspect diagnostics."
    if c.state == "unresolved":
        return "Unresolved: neither practical separation nor searched-family inseparability was established."
    if c.state == "candidate_adjacency":
        return "Candidate adjacency: no searched separator established practical separation; this is not a causal edge."
    return "Certified practical nonedge under the matched predictive calibration profile; this is not a causal nonedge."


def write_edge_report(certificates:list[EdgeCertificate], estimates:list[VimpEstimate], output_dir:str|Path, eligibility:list[CalibrationEligibility]|None=None)->tuple[Path,Path]:
    d=Path(output_dir); d.mkdir(parents=True,exist_ok=True)
    rows=[]
    for c in certificates:
        directions=[e for e in estimates if e.pair_id==c.pair_id]
        pair_deltas = {e.delta_target for e in directions}
        pair_eligibility = [item for item in (eligibility or []) if item.delta_target in pair_deltas]
        eligibility_status = ";".join(sorted({item.status for item in pair_eligibility}))
        eligibility_mismatches = ";".join(sorted({field for item in pair_eligibility for field in item.mismatch_fields}))
        rows.append({"pair_id":c.pair_id,"state":c.state,"separator":",".join(c.separator),"adjusted_p":c.adjusted_p,"causal_status":c.causal_status,"vimp_statuses":";".join(e.status for e in directions),"calibration_statuses":";".join(e.calibration_status for e in directions),"eligibility_status":eligibility_status,"eligibility_mismatch_fields":eligibility_mismatches,"theta_estimates":";".join(str(e.theta_hat) for e in directions),"resolution_reason":_resolution_reason(c,directions)})
    frame=pd.DataFrame(rows); parquet=d/"edge_report.parquet"; frame.to_parquet(parquet,index=False)
    eligibility_frame = pd.DataFrame([item.model_dump() for item in (eligibility or [])])
    eligibility_path = d / "calibration_eligibility.json"
    eligibility_path.write_text(json.dumps([item.model_dump(mode="json") for item in (eligibility or [])], sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    eligibility_html = eligibility_frame.to_html(index=False) if not eligibility_frame.empty else "<p>No calibration profile was requested; hard certification is unavailable.</p>"
    html=d/"report.html"; html.write_text("<html><body><h1>renca predictive evidence report</h1><p>All conclusions are predictive, not causal. Every result retains <code>not_yet_causal</code>.</p><h2>Calibration eligibility</h2>"+eligibility_html+"<h2>Pair evidence</h2>"+frame.to_html(index=False)+"</body></html>",encoding="utf-8")
    return parquet,html
