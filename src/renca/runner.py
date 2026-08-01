from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
from renca.artifacts.manifest import build_analysis_manifest, write_audit_artifacts
from renca.audit import audit_project
from renca.certification import certify_pairs, write_edge_certificates
from renca.models import ProjectSpec
from renca.reporting.edge_table import write_edge_report
from renca.screening import create_outer_split, rank_separators, screen_neighbors, write_separator_candidates, write_split_manifest
from renca.vimp import fit_crossfitted_vimp, write_vimp_estimates
@dataclass(frozen=True)
class RunArtifacts: output_dir: Path
def run_analysis(data:pd.DataFrame,project_spec:ProjectSpec,output_dir:str|Path)->RunArtifacts:
    report=audit_project(data,project_spec)
    if not report.eligible: raise ValueError("Audit failed")
    clean=data.dropna(subset=[n.node_id for n in project_spec.nodes]).reset_index(drop=True); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    write_audit_artifacts(report,build_analysis_manifest(clean,project_spec,report),out)
    split=create_outer_split(clean,project_spec); write_split_manifest(split,out)
    selected=clean.iloc[split.selection_row_positions]; neighborhoods=screen_neighbors(selected,project_spec.nodes,project_spec.screening,seed=project_spec.seed); candidates=rank_separators(selected,project_spec.nodes,neighborhoods,project_spec.screening,seed=project_spec.seed); write_separator_candidates(candidates,out)
    nodes={n.node_id:n for n in project_spec.nodes}; estimates=[]
    for c in candidates:
        estimates.extend([fit_crossfitted_vimp(clean,c.node_i,c.node_j,c.separator,nodes[c.node_i],split,project_spec.vimp),fit_crossfitted_vimp(clean,c.node_j,c.node_i,c.separator,nodes[c.node_j],split,project_spec.vimp)])
    write_vimp_estimates(estimates,out); certificates=certify_pairs(estimates); write_edge_certificates(certificates,out); write_edge_report(certificates,estimates,out); return RunArtifacts(out)
