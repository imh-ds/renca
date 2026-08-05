"""Reproducible independent-grid execution for calibration evidence."""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from renca.calibration.scenarios import generate_scenario, tune_boundary_signal
from renca.calibration.validation import REQUIRED_SCENARIO_FAMILIES
from renca.models import NodeSpec, VimpSpec
from renca.screening import SplitManifest
from renca.vimp import fit_crossfitted_vimp

_GRID: dict[str, object] = {}


def _inference_manifest(n: int, seed: int, folds: int) -> SplitManifest:
    rows = list(range(n))
    return SplitManifest(schema_version="1.7.0", analysis_id="00000000-0000-0000-0000-000000000001", seed=seed, selection_fraction=.2, inference_folds=folds, sampling_unit="iid", selection_row_positions=[], inference_row_positions=rows, inference_fold_by_row_position={row: row % folds for row in rows}, stratification_columns=[], input_order_sha256="calibration")


def replication_seed(seed: int, family: str, replicate: int) -> int:
    """Seed a replication from its family and index alone, never from execution order."""
    return int(np.random.SeedSequence([seed, REQUIRED_SCENARIO_FAMILIES.index(family), replicate]).generate_state(1)[0])


def _initialize_grid_worker(sample_size: int, inference_folds: int, delta: float, critical_value: float, vimp_spec: VimpSpec) -> None:
    _GRID.update(sample_size=sample_size, inference_folds=inference_folds, delta=delta, critical_value=critical_value, vimp_spec=vimp_spec, node=NodeSpec(node_id="y", outcome_type="continuous", loss="squared", delta=delta))


def _run_grid_replication(item: tuple[str, int, int, float]) -> dict[str, object]:
    family, replicate, run_seed, signal = item
    delta, sample_size = _GRID["delta"], _GRID["sample_size"]
    data = generate_scenario(family, sample_size, run_seed, delta, signal=signal)
    estimate = fit_crossfitted_vimp(data, "y", "x", ["z"], _GRID["node"], _inference_manifest(sample_size, run_seed, _GRID["inference_folds"]), _GRID["vimp_spec"])
    statistic = None if estimate.theta_hat is None or estimate.se_theta is None or estimate.se_theta <= 0 else (estimate.theta_hat - delta) / estimate.se_theta
    return {"scenario_family": family, "replicate": replicate, "seed": run_seed, "signal": signal, "status": estimate.status, "theta_hat": estimate.theta_hat, "se_theta": estimate.se_theta, "studentized_statistic": statistic, "reject": bool(estimate.status == "success" and statistic is not None and statistic <= _GRID["critical_value"])}


def run_independent_grid(*, replications: int, sample_size: int, inference_folds: int, delta: float, critical_value: float, vimp_spec: VimpSpec, seed: int, scenario_families: tuple[str, ...] = REQUIRED_SCENARIO_FAMILIES, boundary_signals: dict[str, float] | None = None, replicate_start: int = 0, workers: int | None = None) -> pd.DataFrame:
    """Evaluate a fixed critical value on disjoint seeded data across declared families.

    `workers` fans replications out across processes. Each one is seeded from its family
    and index, and `ProcessPoolExecutor.map` preserves input order, so the worker count
    changes throughput but never results or row order. It defaults to serial execution so
    existing callers and short test grids do not pay for pool startup.
    """
    if replications < 1:
        raise ValueError("replications must be positive")
    signals = boundary_signals or {family: tune_boundary_signal(family, delta)[0] for family in scenario_families}
    items = [
        (family, replicate_start + replicate, replication_seed(seed, family, replicate_start + replicate), signals[family])
        for family in scenario_families
        for replicate in range(replications)
    ]
    initializer_args = (sample_size, inference_folds, delta, critical_value, vimp_spec)
    # Pin BLAS/OpenMP to one thread. This is a correctness requirement, not a tuning
    # choice: threaded reductions change floating-point summation order, and the
    # resulting ~1e-8 drift would make the distribution artifact's recorded SHA-256
    # depend on the host's core count. The env vars are for workers, which read them at
    # start-up; threadpool_limits pins the already-initialised pools in this process.
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[variable] = "1"
    with threadpool_limits(limits=1):
        if workers and workers > 1:
            with ProcessPoolExecutor(max_workers=workers, initializer=_initialize_grid_worker, initargs=initializer_args) as pool:
                rows = list(pool.map(_run_grid_replication, items, chunksize=1))
        else:
            _initialize_grid_worker(*initializer_args)
            rows = [_run_grid_replication(item) for item in items]
    return pd.DataFrame(rows)
