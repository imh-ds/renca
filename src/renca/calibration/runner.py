"""Reproducible independent-grid execution for calibration evidence."""

from __future__ import annotations

import numpy as np
import pandas as pd

from renca.calibration.scenarios import generate_scenario
from renca.calibration.validation import REQUIRED_SCENARIO_FAMILIES
from renca.models import NodeSpec, VimpSpec
from renca.screening import SplitManifest
from renca.vimp import fit_crossfitted_vimp


def _inference_manifest(n: int, seed: int, folds: int) -> SplitManifest:
    rows = list(range(n))
    return SplitManifest(schema_version="1.4.0", analysis_id="00000000-0000-0000-0000-000000000001", seed=seed, selection_fraction=.2, inference_folds=folds, sampling_unit="iid", selection_row_positions=[], inference_row_positions=rows, inference_fold_by_row_position={row: row % folds for row in rows}, stratification_columns=[], input_order_sha256="calibration")


def run_independent_grid(*, replications: int, sample_size: int, inference_folds: int, delta: float, critical_value: float, vimp_spec: VimpSpec, seed: int, scenario_families: tuple[str, ...] = REQUIRED_SCENARIO_FAMILIES) -> pd.DataFrame:
    """Evaluate a fixed critical value on disjoint seeded data across declared families."""
    if replications < 1:
        raise ValueError("replications must be positive")
    node = NodeSpec(node_id="y", outcome_type="continuous", loss="squared", delta=delta)
    rows: list[dict[str, object]] = []
    child_seeds = np.random.SeedSequence(seed).spawn(len(scenario_families) * replications)
    for index, family in enumerate(scenario_families):
        for replicate in range(replications):
            run_seed = int(child_seeds[index * replications + replicate].generate_state(1)[0])
            data = generate_scenario(family, sample_size, run_seed, delta)
            estimate = fit_crossfitted_vimp(data, "y", "x", ["z"], node, _inference_manifest(sample_size, run_seed, inference_folds), vimp_spec)
            statistic = None if estimate.theta_hat is None or estimate.se_theta is None or estimate.se_theta <= 0 else (estimate.theta_hat - delta) / estimate.se_theta
            rows.append({"scenario_family": family, "replicate": replicate, "seed": run_seed, "status": estimate.status, "theta_hat": estimate.theta_hat, "se_theta": estimate.se_theta, "studentized_statistic": statistic, "reject": bool(estimate.status == "success" and statistic is not None and statistic <= critical_value)})
    return pd.DataFrame(rows)
