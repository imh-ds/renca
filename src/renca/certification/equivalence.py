from __future__ import annotations
import json
from enum import StrEnum
from pathlib import Path
from typing import Literal
import pandas as pd
from pydantic import Field
from scipy.stats import norm
from statsmodels.stats.multitest import multipletests
from renca.models import Model
from renca.vimp import VimpEstimate

class PairState(StrEnum):
    CERTIFIED_NONEDGE="certified_nonedge"; CANDIDATE_ADJACENCY="candidate_adjacency"; UNRESOLVED="unresolved"
class EdgeCertificate(Model):
    pair_id: str; state: PairState; separator: list[str]; delta_i: float; delta_j: float
    theta_i_from_j: float|None=None; theta_j_from_i: float|None=None; raw_p: float|None=None; adjusted_p: float|None=None
    error_control: Literal["FWER_Holm"]="FWER_Holm"; assumptions:list[str]=Field(default_factory=lambda:["preselected_separator","cross_fitted_regression_adequacy"]); causal_status:Literal["not_yet_causal"]="not_yet_causal"

def _p(e: VimpEstimate) -> float|None:
    if e.calibration_status != "calibrated_success" or e.status != "success" or e.theta_hat is None or e.se_theta is None or e.se_theta <= 0: return None
    return float(norm.cdf((e.theta_hat-e.delta_target)/e.se_theta))
def certify_pairs(estimates:list[VimpEstimate], alpha:float=.05)->list[EdgeCertificate]:
    grouped:dict[str,list[VimpEstimate]]={}
    for e in estimates: grouped.setdefault(e.pair_id,[]).append(e)
    provisional=[]
    for pair, es in grouped.items():
        if len(es)!=2 or es[0].separator != es[1].separator: raise ValueError(f"Pair {pair} must contain exactly two matching rank-one directions")
        a,b=es; pa,pb=_p(a),_p(b); raw=max(pa,pb) if pa is not None and pb is not None else None
        lower=lambda e: e.lower_ci is not None and e.lower_ci>e.delta_target
        state=PairState.CANDIDATE_ADJACENCY if lower(a) and lower(b) else PairState.UNRESOLVED
        provisional.append((a,b,raw,state))
    valid=[x[2] for x in provisional if x[2] is not None]; adjusted=multipletests(valid,alpha=alpha,method="holm")[1] if valid else [] ; it=iter(adjusted); out=[]
    for a,b,raw,state in provisional:
        adj=float(next(it)) if raw is not None else None
        if adj is not None and adj<=alpha: state=PairState.CERTIFIED_NONEDGE
        out.append(EdgeCertificate(pair_id=a.pair_id,state=state,separator=a.separator,delta_i=a.delta_target,delta_j=b.delta_target,theta_i_from_j=a.theta_hat,theta_j_from_i=b.theta_hat,raw_p=raw,adjusted_p=adj))
    return sorted(out,key=lambda x:x.pair_id)
def write_edge_certificates(certificates:list[EdgeCertificate],output_dir:str|Path)->Path:
    """Write deterministic Parquet and canonical JSON certificate artifacts."""
    d=Path(output_dir); d.mkdir(parents=True,exist_ok=True)
    ordered=sorted(certificates,key=lambda certificate: certificate.pair_id)
    p=d/"edge_certificates.parquet"; pd.DataFrame([c.model_dump() for c in ordered]).to_parquet(p,index=False)
    json_path=d/"edge_certificates.json"
    temporary=json_path.with_suffix(".json.tmp")
    temporary.write_bytes((json.dumps([c.model_dump(mode="json") for c in ordered],sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n").encode())
    temporary.replace(json_path)
    return p
