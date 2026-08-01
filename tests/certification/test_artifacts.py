from __future__ import annotations

import pandas as pd
import json

from renca.certification import certify_pairs, write_edge_certificates
from renca.models import write_json_schemas
from .test_equivalence import estimate


def test_certificate_parquet_and_schema(tmp_path) -> None:
    certificates = certify_pairs([estimate("x--y", "x", "y", .01), estimate("x--y", "y", "x", .01)])
    path = write_edge_certificates(certificates, tmp_path)
    artifact = pd.read_parquet(path)
    assert path.name == "edge_certificates.parquet"
    assert set(artifact.columns) == {"pair_id", "state", "separator", "delta_i", "delta_j", "theta_i_from_j", "theta_j_from_i", "raw_p", "adjusted_p", "error_control", "assumptions", "causal_status"}
    assert artifact.loc[0, "causal_status"] == "not_yet_causal"
    json_path = tmp_path / "edge_certificates.json"
    assert json.loads(json_path.read_text())[0]["pair_id"] == "x--y"
    first = json_path.read_bytes()
    write_edge_certificates(certificates, tmp_path)
    assert json_path.read_bytes() == first
    assert write_json_schemas(tmp_path / "schemas")["edge_certificate"].exists()
