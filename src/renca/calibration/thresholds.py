"""Threshold study for the network fit indices.

`renca.reporting.fit` reports predictive adequacy and the resolution floor without
cut-offs, because SEM's conventional thresholds came from simulation work mapping index
values to error rates and the equivalent had not been run. This module runs it.

The design fixes the target's baseline risk at one, so a scenario is specified directly in
the units the indices report:

    y = sqrt(A) * g(z) + sqrt(T) * h(x) + sqrt(1 - A - T) * e

with `g`, `h`, `z`, `x` and `e` independent and standardised. Then `R(empty) = 1`,
`R({z}) = T + (1 - A - T)`, and `R({z, x}) = 1 - A - T`, so

    true predictive adequacy = A          true Theta = T

Both axes are therefore set exactly rather than tuned, and a cell is a true nonedge when
`T < delta` and a true edge when `T >= delta`. Certifying a true edge is a false prune.

`g` and `h` are independently switchable between a form the learner library fits easily and
an oscillatory form it cannot. That separation matters: predictive adequacy is computed from
the *reduced* model, so it measures whether the separator is learnable and says nothing
about whether the added variable's contribution is detectable. A pilot found `theta_hat`
collapsing from 0.159 to 0.043 against a true 0.15 when only the added variable was
unlearnable, while adequacy barely moved (0.326 to 0.309). Establishing whether that blind
spot produces false prunes, and whether any reported index anticipates it, is the point of
the study rather than an aside.
"""

from __future__ import annotations

import math
from typing import Literal

import numpy as np
import pandas as pd

from renca.models import NodeSpec, VimpSpec
from renca.screening import SplitManifest
from renca.vimp import fit_crossfitted_vimp

LearnableForm = Literal["linear", "oscillatory"]
OSCILLATION = 4.0


def _standardised(values: np.ndarray, form: LearnableForm) -> np.ndarray:
    """Unit-variance transform; the oscillatory form is outside the learner library's reach."""
    if form == "linear":
        return values
    # Var(sin(k Z)) = (1 - exp(-2k^2)) / 2 for standard normal Z.
    return np.sin(OSCILLATION * values) / math.sqrt((1 - math.exp(-2 * OSCILLATION**2)) / 2)


def generate_threshold_scenario(*, adequacy: float, theta: float, separator_form: LearnableForm, added_form: LearnableForm, n: int, seed: int) -> pd.DataFrame:
    """Draw a scenario whose true adequacy and true Theta are exactly as requested."""
    if adequacy < 0 or theta < 0 or adequacy + theta >= 1:
        raise ValueError("adequacy and theta must be non-negative and sum below one")
    generator = np.random.default_rng(seed)
    z, x, error = generator.normal(size=(3, n))
    y = (
        math.sqrt(adequacy) * _standardised(z, separator_form)
        + math.sqrt(theta) * _standardised(x, added_form)
        + math.sqrt(1 - adequacy - theta) * error
    )
    return pd.DataFrame({"z": z, "x": x, "y": y})


def _manifest(n: int, seed: int, folds: int) -> SplitManifest:
    rows = list(range(n))
    return SplitManifest(schema_version="1.7.0", analysis_id="00000000-0000-0000-0000-000000000002", seed=seed, selection_fraction=.2, inference_folds=folds, sampling_unit="iid", selection_row_positions=[], inference_row_positions=rows, inference_fold_by_row_position={row: row % folds for row in rows}, stratification_columns=[], input_order_sha256="threshold")


def run_threshold_replication(*, adequacy: float, theta: float, separator_form: LearnableForm, added_form: LearnableForm, n: int, seed: int, delta: float, critical_value: float, vimp_spec: VimpSpec, inference_folds: int = 5) -> dict[str, object]:
    """Run one directional estimate and record its indices against the known truth."""
    data = generate_threshold_scenario(adequacy=adequacy, theta=theta, separator_form=separator_form, added_form=added_form, n=n, seed=seed)
    node = NodeSpec(node_id="y", outcome_type="continuous", loss="squared", delta=delta)
    estimate = fit_crossfitted_vimp(data, "y", "x", ["z"], node, _manifest(n, seed, inference_folds), vimp_spec)
    diagnostic = estimate.nuisance_diagnostic
    null_risk, reduced = diagnostic.get("null_risk"), diagnostic.get("mean_reduced_loss")
    observed_adequacy = 1 - reduced / null_risk if isinstance(null_risk, (int, float)) and isinstance(reduced, (int, float)) and null_risk > 0 else None
    usable = estimate.status == "success" and estimate.theta_hat is not None and estimate.se_theta is not None and estimate.se_theta > 0
    statistic = (estimate.theta_hat - delta) / estimate.se_theta if usable else None
    certified = bool(usable and statistic is not None and statistic <= critical_value)
    true_edge = theta >= delta
    return {
        "true_adequacy": adequacy,
        "true_theta": theta,
        "separator_form": separator_form,
        "added_form": added_form,
        "n": n,
        "seed": seed,
        "status": estimate.status,
        "observed_adequacy": observed_adequacy,
        "theta_hat": estimate.theta_hat,
        "se_theta": estimate.se_theta,
        "resolution_floor": abs(critical_value) * estimate.se_theta if usable else None,
        "certified": certified,
        "true_edge": true_edge,
        # Certifying a true edge is a false prune; certifying a true nonedge is the
        # outcome the method exists to produce.
        "false_prune": bool(certified and true_edge),
        "correct_prune": bool(certified and not true_edge),
    }


def summarize_threshold_grid(results: pd.DataFrame, *, bins: tuple[float, ...] = (-math.inf, 0., .02, .05, .10, .20, .40, math.inf)) -> pd.DataFrame:
    """Map observed adequacy onto false-prune and correct-prune rates."""
    if results.empty:
        raise ValueError("no replications to summarize")
    frame = results.copy()
    frame["adequacy_bin"] = pd.cut(frame.observed_adequacy, bins=list(bins))
    rows = []
    for label, subset in frame.groupby("adequacy_bin", observed=True):
        edges, nonedges = subset[subset.true_edge], subset[~subset.true_edge]
        rows.append({
            "adequacy_bin": str(label),
            "replications": len(subset),
            "true_edges": len(edges),
            "false_prune_rate": float(edges.false_prune.mean()) if len(edges) else float("nan"),
            "true_nonedges": len(nonedges),
            "correct_prune_rate": float(nonedges.correct_prune.mean()) if len(nonedges) else float("nan"),
            "median_theta_bias": float((subset.theta_hat - subset.true_theta).median()),
            "abstention_rate": float((subset.status != "success").mean()),
        })
    return pd.DataFrame(rows)


def summarize_learnability(results: pd.DataFrame) -> pd.DataFrame:
    """Bias and false-prune rate by which parts of the model the library can fit."""
    rows = []
    for (separator_form, added_form), subset in results.groupby(["separator_form", "added_form"], observed=True):
        edges = subset[subset.true_edge]
        rows.append({
            "separator_form": separator_form,
            "added_form": added_form,
            "replications": len(subset),
            "median_observed_adequacy": float(subset.observed_adequacy.median()),
            "median_theta_bias": float((subset.theta_hat - subset.true_theta).median()),
            "false_prune_rate": float(edges.false_prune.mean()) if len(edges) else float("nan"),
            "correct_prune_rate": float(subset[~subset.true_edge].correct_prune.mean()) if len(subset[~subset.true_edge]) else float("nan"),
        })
    return pd.DataFrame(rows)
