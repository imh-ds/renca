from __future__ import annotations

import json

import pandas as pd

from renca.models import write_json_schemas
from renca.vimp import VimpEstimate, write_vimp_estimates


def test_vimp_parquet_round_trip_and_schema(tmp_path) -> None:
    estimate = VimpEstimate(pair_id="x--y", target="y", added_variable="x", separator=["z"], psi_hat=.1, theta_hat=.2, se_theta=.01, lower_ci=.18, upper_ci=.22, delta_target=.01, nuisance_diagnostic={"null_risk": .5}, status="success")
    path = write_vimp_estimates([estimate], tmp_path); artifact = pd.read_parquet(path)
    assert path.name == "vimp_estimates.parquet" and artifact.loc[0, "p_equivalence"] is None or pd.isna(artifact.loc[0, "p_equivalence"])
    assert json.loads(artifact.loc[0, "separator"]) == ["z"] and json.loads(artifact.loc[0, "nuisance_diagnostic"])["null_risk"] == .5
    assert write_json_schemas(tmp_path / "schemas")["vimp_estimate"].exists()
