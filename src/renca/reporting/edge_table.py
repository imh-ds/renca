from __future__ import annotations
from pathlib import Path
import pandas as pd
from renca.certification import EdgeCertificate
from renca.vimp import VimpEstimate
def write_edge_report(certificates:list[EdgeCertificate], estimates:list[VimpEstimate], output_dir:str|Path)->tuple[Path,Path]:
    d=Path(output_dir); d.mkdir(parents=True,exist_ok=True)
    rows=[]
    for c in certificates:
        directions=[e for e in estimates if e.pair_id==c.pair_id]
        rows.append({"pair_id":c.pair_id,"state":c.state,"separator":",".join(c.separator),"adjusted_p":c.adjusted_p,"causal_status":c.causal_status,"vimp_statuses":";".join(e.status for e in directions),"theta_estimates":";".join(str(e.theta_hat) for e in directions)})
    frame=pd.DataFrame(rows); parquet=d/"edge_report.parquet"; frame.to_parquet(parquet,index=False)
    html=d/"report.html"; html.write_text("<html><body><h1>renca predictive evidence report</h1><p>All conclusions are predictive, not causal.</p>"+frame.to_html(index=False)+"</body></html>",encoding="utf-8")
    return parquet,html
