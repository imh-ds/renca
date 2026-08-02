from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from renca.models import ProjectSpec
from renca.runner import run_analysis

def payload() -> dict[str, object]:
    return {"schema_version":"1.6.0","analysis_id":"dddb2c74-2a57-4561-8afc-2c56e086674b","preanalysis_reference":"fixture","seed":3,"missing_data_policy":"complete_case","design":{"sampling_unit":"iid","cluster_id_column":None},"split":{"selection_fraction":.2,"inference_folds":3},"audit":{"minimum_rows_per_inference_fold":5,"minimum_clusters":2},"screening":{"max_neighbors":2,"max_separator_size":1,"separators_per_pair":1},"vimp":{"forest_trees":10,"forest_max_depth":3,"ridge_alpha":1.,"confidence_level":.95},"nodes":[{"node_id":"x","outcome_type":"continuous","loss":"squared","delta":.01},{"node_id":"y","outcome_type":"continuous","loss":"squared","delta":.01},{"node_id":"z","outcome_type":"continuous","loss":"squared","delta":.01}]}

def data() -> pd.DataFrame:
    rng=np.random.default_rng(4); z=rng.normal(size=60); return pd.DataFrame({"x":z+rng.normal(scale=.1,size=60),"y":z+rng.normal(scale=.1,size=60),"z":z})

def test_runner_writes_complete_predictive_evidence_ledger(tmp_path: Path) -> None:
    out=tmp_path/"out"; run_analysis(data(),ProjectSpec.model_validate(payload()),out)
    expected={"audit.json","analysis_manifest.json","run_receipt.json","split_manifest.json","separator_candidates.parquet","vimp_estimates.parquet","edge_certificates.parquet","edge_certificates.json","edge_report.parquet","report.html"}
    assert expected <= {path.name for path in out.iterdir()}
    report=pd.read_parquet(out/"edge_report.parquet")
    assert set(report["state"]) == {"unresolved"} and set(report["causal_status"]) == {"not_yet_causal"}
    assert "predictive" in (out/"report.html").read_text()

def test_cli_runs_csv_config_fixture(tmp_path: Path) -> None:
    config=tmp_path/"project.json"; csv=tmp_path/"data.csv"; out=tmp_path/"cli"; config.write_text(json.dumps(payload())); data().to_csv(csv,index=False)
    result=subprocess.run([sys.executable,"-m","renca.cli","run","--config",str(config),"--data",str(csv),"--output",str(out)],capture_output=True,text=True)
    assert result.returncode == 0 and (out/"edge_report.parquet").exists()


def test_runner_refuses_declared_profile_without_registry(tmp_path: Path) -> None:
    configured = payload(); configured["calibration"] = {"profile_id": "missing"}
    with pytest.raises(ValueError, match="calibration registry"):
        run_analysis(data(), ProjectSpec.model_validate(configured), tmp_path / "out")
