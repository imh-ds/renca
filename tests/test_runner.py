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
from renca.artifacts.manifest import read_evidence_bundle_manifest

def payload() -> dict[str, object]:
    return {"schema_version":"1.7.0","analysis_id":"dddb2c74-2a57-4561-8afc-2c56e086674b","preanalysis_reference":"fixture","seed":3,"missing_data_policy":"complete_case","design":{"sampling_unit":"iid","cluster_id_column":None},"split":{"selection_fraction":.2,"inference_folds":3},"audit":{"minimum_rows_per_inference_fold":5,"minimum_clusters":2},"screening":{"max_neighbors":2,"max_separator_size":1,"separators_per_pair":1},"vimp":{"forest_trees":10,"forest_max_depth":3,"ridge_alpha":1.,"confidence_level":.95},"nodes":[{"node_id":"x","outcome_type":"continuous","loss":"squared","delta":.01},{"node_id":"y","outcome_type":"continuous","loss":"squared","delta":.01},{"node_id":"z","outcome_type":"continuous","loss":"squared","delta":.01}]}

def data() -> pd.DataFrame:
    rng=np.random.default_rng(4); z=rng.normal(size=60); return pd.DataFrame({"x":z+rng.normal(scale=.1,size=60),"y":z+rng.normal(scale=.1,size=60),"z":z})

def test_runner_writes_complete_predictive_evidence_ledger(tmp_path: Path) -> None:
    out=tmp_path/"out"; run_analysis(data(),ProjectSpec.model_validate(payload()),out)
    expected={"audit.json","analysis_manifest.json","run_receipt.json","split_manifest.json","separator_candidates.parquet","vimp_estimates.parquet","edge_certificates.parquet","edge_certificates.json","edge_report.parquet","report.html","calibration_eligibility.json","evidence_bundle_manifest.json","resolution_graph.json","resolution_graph.graphml"}
    assert expected <= {path.name for path in out.iterdir()}
    report=pd.read_parquet(out/"edge_report.parquet")
    assert set(report["state"]) == {"unresolved"} and set(report["causal_status"]) == {"not_yet_causal"}
    assert "predictive" in (out/"report.html").read_text()
    assert "resolution_reason" in report.columns
    html = (out / "report.html").read_text()
    assert "Predictive ResolutionGraph" in html and "pair-panel" in html and "stroke-dasharray" in html
    graph = json.loads((out / "resolution_graph.json").read_text())
    assert graph["interpretation"] == "predictive_not_causal" and graph["sensitivity_deltas"] == []
    assert read_evidence_bundle_manifest(out / "evidence_bundle_manifest.json").analysis_id == payload()["analysis_id"]

def test_cli_runs_csv_config_fixture(tmp_path: Path) -> None:
    config=tmp_path/"project.json"; csv=tmp_path/"data.csv"; out=tmp_path/"cli"; config.write_text(json.dumps(payload())); data().to_csv(csv,index=False)
    result=subprocess.run([sys.executable,"-m","renca.cli","run","--config",str(config),"--data",str(csv),"--output",str(out)],capture_output=True,text=True)
    assert result.returncode == 0 and (out/"edge_report.parquet").exists()


def test_runner_uses_packaged_registry_for_declared_profile(tmp_path: Path) -> None:
    configured = payload(); configured["calibration"] = {"profile_id": "missing"}
    out = tmp_path / "out"; run_analysis(data(), ProjectSpec.model_validate(configured), out)
    estimates = pd.read_parquet(out / "vimp_estimates.parquet")
    assert set(estimates.calibration_status) == {"calibration_failed"}
    eligibility = json.loads((out / "calibration_eligibility.json").read_text())
    assert eligibility[0]["mismatch_fields"] == ["profile_id"]


def test_exact_profile_run_is_eligible_and_near_match_stays_unresolved(tmp_path: Path) -> None:
    rng = np.random.default_rng(44)
    shared = rng.normal(size=375)
    calibrated_data = pd.DataFrame({"x": shared + rng.normal(size=375), "y": shared + rng.normal(size=375), "z": rng.normal(size=375)})
    configured = payload()
    configured.update({"split": {"selection_fraction": .2, "inference_folds": 5}, "audit": {"minimum_rows_per_inference_fold": 60, "minimum_clusters": 2}, "vimp": {"forest_trees": 10, "forest_max_depth": 5, "ridge_alpha": 1., "confidence_level": .95, "learner_library_version": "v3_nested_blend"}, "calibration": {"profile_id": "v3-nested-blend-n300-d005-phase0"}})
    for node in configured["nodes"]:
        node["delta"] = .05
    out = tmp_path / "calibrated"
    run_analysis(calibrated_data, ProjectSpec.model_validate(configured), out)
    assert {row["status"] for row in json.loads((out / "calibration_eligibility.json").read_text())} == {"calibrated_success"}
    assert "Calibration eligibility" in (out / "report.html").read_text()
    configured["split"] = {"selection_fraction": .2, "inference_folds": 4}
    uncalibrated = tmp_path / "near_match"
    run_analysis(calibrated_data, ProjectSpec.model_validate(configured), uncalibrated)
    assert set(pd.read_parquet(uncalibrated / "edge_report.parquet").state) == {"unresolved"}
    assert "inference_folds" in json.loads((uncalibrated / "calibration_eligibility.json").read_text())[0]["mismatch_fields"]
