"""Explore feasibility gate: does a sparse nonlinear association map earn its place?

Executes `docs/pilots/explore-feasibility-protocol.md`. Builds nothing in `src/`; the
estimator here is a study article, not a shipped mode.

**The generating process, and why it is built this way.** Truth is a Gaussian graphical
model `Z ~ N(0, Sigma)` whose precision support *is* the undirected skeleton, pushed
through a strictly monotone per-node transform `Y_k = h_k(Z_k)`. Monotonicity is not
cosmetic: it makes `sigma(Y_k) = sigma(Z_k)`, so conditional independence transfers from
`Z` to `Y` exactly and a nonedge is a nonedge rather than an approximation. A
non-monotone transform would discard the sign of `Z_k` and could manufacture dependence
that the skeleton does not contain, which would make every false-inclusion number
meaningless.

Both arms share that machinery. The linear arm takes `h_k = identity`. The nonlinear arm
takes strongly curved but still monotone transforms -- cubic, exponential, hyperbolic
sine, and a steep probit squash standing in for the floor and ceiling effects that
bounded psychological scales actually show. The two arms are matched on `tau`, so they
differ in shape and not in signal strength.

**The oracle is exact, not fitted.** Because `h` is invertible, conditioning on a set of
`Y` variables is conditioning on the same set of `Z` variables, and `Z_i` given any
subset is Gaussian with known mean and variance. The conditional mean of `Y_i` is
therefore a one-dimensional Gaussian integral of `h_i`, evaluated by Gauss-Hermite
quadrature. That gives

    tau(i <- j) = E[(f_i - f_i^-j)^2] / Var(Y_i)

by the tower property, with both conditional means computed rather than estimated. No
criterion in the protocol can be moved by the behaviour of the estimator under test.

**Two methods, one operating point.** Recovery is free if you draw enough edges, so the
incumbent comparison sweeps each method's tuning to the point where its false-inclusion
rate among genuine nonedges is as close to `TARGET_FALSE_INCLUSION` as possible from
below, and reads recovery there. Both methods get the same oracle assistance in finding
that point; neither could do it on real data. That is what makes the comparison fair
rather than realistic, and it is the only way to answer "why use this instead of what
the field already uses".
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.polynomial.hermite_e import hermegauss
from sklearn.covariance import graphical_lasso
from sklearn.preprocessing import SplineTransformer

# ---------------------------------------------------------------- protocol constants

SAMPLE_SIZES = (50, 75, 100, 125, 150)
VARIABLE_COUNTS = (6, 7, 8, 9, 10)
ARMS = ("linear", "nonlinear")

STRONG_TAU = 0.10
"""Section 1 of the protocol. An edge is strong when min(tau(i<-j), tau(j<-i)) reaches
this. The minimum governs because the AND rule retains only what both directions find."""

TAU_MARGIN = 0.01
"""Graphs whose edge strengths land within this of `STRONG_TAU` are redrawn. Oracle Monte
Carlo error is far below it, so no edge can be misclassified by simulation noise."""

MIN_STRONG_EDGES = 2
MIN_WEAK_EDGES = 1
MIN_NONEDGES = 2
MAX_DEGREE_FRACTION = 0.5


def sparsity_cap(p: int) -> int:
    """Densest node the design permits, and the estimator's per-node selection quota.

    One function serves both deliberately. The 2026-08-11 pilot set the quota to a
    different fraction of `p - 1` than the degree cap, and at `p` in {7, 8, 9} the
    rounding put the quota *below* the cap -- so a node at maximum degree could not have
    all its edges selected however good the data were. Recovery at those three variable
    counts measured that arithmetic rather than the method, and the only two cells where
    the constants happened to agree, `p = 6` and `p = 10`, were the two best performers.

    The quota is therefore the sparsity level the design permits. A real analyst does not
    know that level; setting it correctly here isolates the question this study asks, and
    sensitivity to mis-setting it is a separate question this study does not address.
    """
    return max(2, int(round(MAX_DEGREE_FRACTION * (p - 1))))

TARGET_FALSE_INCLUSION = 0.05
RECOVERY_BAR = 0.60
BLANK_BAR = 0.10
EXPECTED_FALSE_EDGES_BAR = 1.0
RUNTIME_BAR_SECONDS = 300.0

ORACLE_ROWS = 20_000
QUADRATURE_NODES = 15

SPLINE_KNOTS = 5
SPLINE_DEGREE = 3
SUBSAMPLES = 50
SUBSAMPLE_FRACTION = 0.5
RETENTION_THRESHOLD = 0.75
LAMBDA_PATH_LENGTH = 20
LAMBDA_MIN_RATIO = 0.02

TAU_BINS = (0.0, 0.02, 0.05, 0.10, 0.20, 1.01)


def _standardise(values: np.ndarray) -> np.ndarray:
    centred = values - values.mean(axis=0, keepdims=True)
    scale = centred.std(axis=0, keepdims=True)
    return centred / np.where(scale > 0, scale, 1.0)


# ---------------------------------------------------------------- generating process

NONLINEAR_SHAPES = ("cubic", "exponential", "sinh", "probit_squash")

_SQRT_TWO = float(np.sqrt(2.0))


def _normal_cdf(z: np.ndarray) -> np.ndarray:
    """`scipy.stats.norm.cdf` by another name; called inside the oracle's hot loop."""
    from scipy.special import erf
    return 0.5 * (1.0 + erf(z / _SQRT_TWO))


def _apply_shape(z: np.ndarray, shape: str) -> np.ndarray:
    """Strictly monotone transforms only, so the skeleton transfers exactly."""
    if shape == "identity":
        return z
    if shape == "cubic":
        return z**3
    if shape == "exponential":
        return np.exp(z)
    if shape == "sinh":
        return np.sinh(1.5 * z)
    if shape == "probit_squash":
        # A steep monotone squash: the floor and ceiling behaviour of a bounded scale,
        # which attenuates linear association far more than it attenuates dependence.
        return _normal_cdf(2.0 * z)
    raise ValueError(f"unknown shape: {shape}")


def sample_precision(rng: np.random.Generator, p: int) -> tuple[np.ndarray, np.ndarray]:
    """Draw a skeleton and a positive-definite precision matrix supported on it."""
    max_degree = sparsity_cap(p)
    adjacency = np.zeros((p, p), dtype=bool)
    order = rng.permutation([(i, j) for i in range(p) for j in range(i + 1, p)])
    for i, j in order:
        if adjacency[i].sum() < max_degree and adjacency[j].sum() < max_degree and rng.random() < 0.45:
            adjacency[i, j] = adjacency[j, i] = True

    precision = np.zeros((p, p))
    magnitudes = rng.uniform(0.20, 0.85, size=(p, p))
    signs = rng.choice((-1.0, 1.0), size=(p, p))
    for i in range(p):
        for j in range(i + 1, p):
            if adjacency[i, j]:
                precision[i, j] = precision[j, i] = signs[i, j] * magnitudes[i, j]
    # Diagonal dominance is the cheapest guarantee of positive definiteness that leaves
    # the off-diagonal support untouched, which is what defines the skeleton.
    np.fill_diagonal(precision, np.abs(precision).sum(axis=1) + rng.uniform(0.1, 0.4, size=p))

    covariance = np.linalg.inv(precision)
    scale = np.sqrt(np.diag(covariance))
    covariance = covariance / np.outer(scale, scale)
    return adjacency, covariance


def oracle_tau(covariance: np.ndarray, shapes: list[str], rng: np.random.Generator) -> np.ndarray:
    """Exact directional tau by Gaussian conditioning and Gauss-Hermite quadrature."""
    p = covariance.shape[0]
    latent = rng.multivariate_normal(np.zeros(p), covariance, size=ORACLE_ROWS, method="cholesky")
    nodes, weights = hermegauss(QUADRATURE_NODES)
    weights = weights / weights.sum()

    def conditional_mean(target: int, given: list[int]) -> np.ndarray:
        """E[h_target(Z_target) | Z_given] evaluated at every drawn row."""
        if not given:
            centre = np.zeros(ORACLE_ROWS)
            spread = float(np.sqrt(covariance[target, target]))
        else:
            block = covariance[np.ix_(given, given)]
            cross = covariance[target, given]
            weightsolve = np.linalg.solve(block, cross)
            centre = latent[:, given] @ weightsolve
            spread = float(np.sqrt(max(covariance[target, target] - cross @ weightsolve, 1e-12)))
        grid = centre[:, None] + spread * nodes[None, :]
        return _apply_shape(grid, shapes[target]) @ weights

    tau = np.zeros((p, p))
    for target in range(p):
        observed = _apply_shape(latent[:, target], shapes[target])
        variance = float(np.var(observed))
        others = [k for k in range(p) if k != target]
        full = conditional_mean(target, others)
        for added in others:
            reduced = conditional_mean(target, [k for k in others if k != added])
            tau[target, added] = float(np.mean((full - reduced) ** 2)) / variance
    return tau


@dataclass
class Truth:
    adjacency: np.ndarray
    covariance: np.ndarray
    shapes: list[str]
    edge_strength: np.ndarray  # symmetric min over directions


def draw_truth(rng: np.random.Generator, p: int, arm: str) -> tuple[Truth, int]:
    """Rejection-sample until the graph can actually be scored against the protocol."""
    for attempt in range(200):
        adjacency, covariance = sample_precision(rng, p)
        shapes = (["identity"] * p if arm == "linear"
                  else [NONLINEAR_SHAPES[k % len(NONLINEAR_SHAPES)] for k in rng.permutation(p)])
        tau = oracle_tau(covariance, shapes, rng)
        strength = np.minimum(tau, tau.T)
        np.fill_diagonal(strength, 0.0)
        strength[~adjacency] = 0.0

        upper = np.triu_indices(p, 1)
        values = strength[upper]
        present = adjacency[upper]
        strong = int(((values >= STRONG_TAU) & present).sum())
        weak = int(((values > 0) & (values < STRONG_TAU) & present).sum())
        # A nonedge must be exactly zero, and no edge may sit on the strong boundary
        # where oracle Monte Carlo error could flip its class.
        boundary = bool(np.any(np.abs(values[present] - STRONG_TAU) < TAU_MARGIN))
        if strong >= MIN_STRONG_EDGES and weak >= MIN_WEAK_EDGES and int((~present).sum()) >= MIN_NONEDGES and not boundary:
            return Truth(adjacency, covariance, shapes, strength), attempt
    raise RuntimeError(f"could not draw an admissible graph at p={p}, arm={arm}")


def generate(truth: Truth, n: int, rng: np.random.Generator) -> np.ndarray:
    p = truth.covariance.shape[0]
    latent = rng.multivariate_normal(np.zeros(p), truth.covariance, size=n, method="cholesky")
    return np.column_stack([_apply_shape(latent[:, k], truth.shapes[k]) for k in range(p)])


# ---------------------------------------------------------------- explore estimator


def _spline_blocks(values: np.ndarray) -> list[np.ndarray]:
    """One orthonormalised smooth basis per variable, centred so no block carries the mean."""
    blocks = []
    for column in range(values.shape[1]):
        basis = SplineTransformer(n_knots=SPLINE_KNOTS, degree=SPLINE_DEGREE, include_bias=False).fit_transform(values[:, [column]])
        basis = basis - basis.mean(axis=0, keepdims=True)
        # Orthonormalising each block makes the group-lasso block update a closed-form
        # soft threshold rather than an inner optimisation.
        u, s, _ = np.linalg.svd(basis, full_matrices=False)
        blocks.append(u[:, s > 1e-8 * max(s[0], 1e-12)])
    return blocks


def _group_lasso_path(blocks: list[np.ndarray], outcome: np.ndarray, quota: int) -> list[int]:
    """Walk lambda down until `quota` groups are active; return that active set."""
    target = outcome - outcome.mean()
    n = len(target)
    correlations = [float(np.linalg.norm(block.T @ target)) for block in blocks]
    lambda_max = max(correlations) / n if correlations else 0.0
    if lambda_max <= 0:
        return []
    path = np.geomspace(lambda_max, lambda_max * LAMBDA_MIN_RATIO, LAMBDA_PATH_LENGTH)

    coefficients = [np.zeros(block.shape[1]) for block in blocks]
    fitted = np.zeros(n)
    best: list[int] = []
    for penalty in path:
        for _ in range(25):
            largest = 0.0
            for index, block in enumerate(blocks):
                partial = target - fitted + block @ coefficients[index]
                gradient = block.T @ partial
                norm = float(np.linalg.norm(gradient))
                updated = np.zeros_like(gradient) if norm <= penalty * n else gradient * (1 - penalty * n / norm)
                shift = updated - coefficients[index]
                if np.any(shift):
                    fitted = fitted + block @ shift
                    coefficients[index] = updated
                    largest = max(largest, float(np.linalg.norm(shift)))
            if largest < 1e-6:
                break
        active = [index for index, value in enumerate(coefficients) if np.linalg.norm(value) > 0]
        if len(active) > quota:
            return best
        best = active
        if len(active) == quota:
            return best
    return best


def explore_selection(values: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Per-node selection frequencies over stability-selection subsamples."""
    n, p = values.shape
    standardised = _standardise(values)
    blocks_by_column = _spline_blocks(standardised)
    quota = sparsity_cap(p)
    size = max(SPLINE_KNOTS + SPLINE_DEGREE, int(round(SUBSAMPLE_FRACTION * n)))

    counts = np.zeros((p, p))
    for _ in range(SUBSAMPLES):
        rows = rng.choice(n, size=size, replace=False)
        for target in range(p):
            others = [k for k in range(p) if k != target]
            blocks = [blocks_by_column[k][rows] for k in others]
            active = _group_lasso_path(blocks, standardised[rows, target], quota)
            for position in active:
                counts[target, others[position]] += 1
    return counts / SUBSAMPLES


def explore_edges(frequencies: np.ndarray, threshold: float) -> np.ndarray:
    """AND rule: both nodewise models must retain the pair."""
    retained = frequencies >= threshold
    return retained & retained.T


# ---------------------------------------------------------------- incumbent baseline


def baseline_path(values: np.ndarray) -> list[tuple[float, np.ndarray]]:
    """Gaussian graphical model over a penalty path -- the field's current default."""
    standardised = _standardise(values)
    correlation = np.corrcoef(standardised, rowvar=False)
    correlation = np.nan_to_num(correlation, nan=0.0)
    np.fill_diagonal(correlation, 1.0)
    offdiag = np.abs(correlation - np.eye(correlation.shape[0]))
    top = max(float(offdiag.max()), 1e-3)
    results = []
    for penalty in np.geomspace(top, top * LAMBDA_MIN_RATIO, LAMBDA_PATH_LENGTH):
        try:
            _, precision = graphical_lasso(correlation, alpha=float(penalty), max_iter=100)
        except Exception:
            continue
        adjacency = np.abs(precision) > 1e-8
        np.fill_diagonal(adjacency, False)
        results.append((float(penalty), adjacency))
    return results


def ebic_choice(values: np.ndarray, path: list[tuple[float, np.ndarray]], gamma: float = 0.5) -> np.ndarray:
    """Extended BIC selection, matching how the incumbent is used in practice."""
    n, p = values.shape
    standardised = _standardise(values)
    correlation = np.nan_to_num(np.corrcoef(standardised, rowvar=False), nan=0.0)
    np.fill_diagonal(correlation, 1.0)
    best_score, best = np.inf, np.zeros((p, p), dtype=bool)
    for penalty, adjacency in path:
        try:
            _, precision = graphical_lasso(correlation, alpha=penalty, max_iter=100)
            sign, logdet = np.linalg.slogdet(precision)
            if sign <= 0:
                continue
        except Exception:
            continue
        edges = int(adjacency[np.triu_indices(p, 1)].sum())
        likelihood = n * (logdet - float(np.trace(correlation @ precision)))
        score = -likelihood + edges * np.log(n) + 4 * gamma * edges * np.log(p)
        if score < best_score:
            best_score, best = score, adjacency
    return best


# ---------------------------------------------------------------- scoring


def score_edges(estimated: np.ndarray, truth: Truth) -> dict[str, float]:
    upper = np.triu_indices(truth.adjacency.shape[0], 1)
    drawn = estimated[upper]
    present = truth.adjacency[upper]
    strength = truth.edge_strength[upper]
    strong = present & (strength >= STRONG_TAU)
    weak = present & (strength < STRONG_TAU)
    nonedges = ~present
    return {
        "false_inclusion_rate": float(drawn[nonedges].mean()) if nonedges.any() else float("nan"),
        "false_edges": float(drawn[nonedges].sum()),
        "strong_recovery": float(drawn[strong].mean()) if strong.any() else float("nan"),
        "weak_recovery": float(drawn[weak].mean()) if weak.any() else float("nan"),
        "precision": float(present[drawn].mean()) if drawn.any() else float("nan"),
        "edges_drawn": float(drawn.sum()),
        "blank": float(not drawn.any()),
        "strong_edges_present": float(strong.sum()),
    }


def matched_operating_point(candidates: list[tuple[float, np.ndarray]], truth: Truth) -> dict[str, float]:
    """The point whose false inclusion is nearest TARGET_FALSE_INCLUSION from below.

    Recovery bought by drawing more edges is not recovery, so both methods are read at
    the same false-inclusion level rather than at their own defaults.
    """
    scored = [score_edges(adjacency, truth) for _, adjacency in candidates]
    admissible = [item for item in scored
                  if not np.isnan(item["false_inclusion_rate"]) and item["false_inclusion_rate"] <= TARGET_FALSE_INCLUSION]
    if not admissible:  # every point overshoots; take the least offensive one
        return min(scored, key=lambda item: item["false_inclusion_rate"])
    # Maximise recovery subject to the constraint. Selecting the first admissible point
    # instead would hand the advantage to whichever method's path happens to be ordered
    # from permissive to strict, which is an artefact of the search and not of the method.
    return max(admissible, key=lambda item: (
        -1.0 if np.isnan(item["strong_recovery"]) else item["strong_recovery"], item["edges_drawn"]))


# ---------------------------------------------------------------- replication driver


def replicate(index: int, n: int, p: int, arm: str, seed: int) -> dict[str, object]:
    import time
    rng = np.random.default_rng(np.random.SeedSequence([seed, n, p, ARMS.index(arm), index]))
    truth, redraws = draw_truth(rng, p, arm)
    values = generate(truth, n, rng)

    started = time.perf_counter()
    frequencies = explore_selection(values, rng)
    runtime = time.perf_counter() - started

    default = explore_edges(frequencies, RETENTION_THRESHOLD)
    record: dict[str, object] = {
        "replicate": index, "sample_size": n, "variables": p, "arm": arm,
        "redraws": redraws, "runtime_seconds": runtime,
        **{f"explore_{key}": value for key, value in score_edges(default, truth).items()},
    }

    thresholds = [(t, explore_edges(frequencies, t)) for t in np.linspace(0.5, 1.0, 11)]
    record.update({f"explore_matched_{key}": value for key, value in matched_operating_point(thresholds, truth).items()})

    path = baseline_path(values)
    if path:
        record.update({f"baseline_{key}": value for key, value in score_edges(ebic_choice(values, path), truth).items()})
        record.update({f"baseline_matched_{key}": value for key, value in matched_operating_point(path, truth).items()})

    upper = np.triu_indices(p, 1)
    for low, high in zip(TAU_BINS[:-1], TAU_BINS[1:]):
        mask = truth.adjacency[upper] & (truth.edge_strength[upper] >= low) & (truth.edge_strength[upper] < high)
        record[f"recovery_tau_{low:g}_{high:g}"] = float(default[upper][mask].mean()) if mask.any() else np.nan
        record[f"count_tau_{low:g}_{high:g}"] = float(mask.sum())

    # Reproducibility diagnostic: an independent dataset from the same truth.
    second = explore_edges(explore_selection(generate(truth, n, rng), rng), RETENTION_THRESHOLD)
    first_set = {tuple(pair) for pair in np.argwhere(np.triu(default, 1))}
    second_set = {tuple(pair) for pair in np.argwhere(np.triu(second, 1))}
    if not first_set and not second_set:
        record["jaccard"] = np.nan  # undefined; two blank graphs are not agreement
        record["both_blank"] = 1.0
    else:
        record["jaccard"] = len(first_set & second_set) / len(first_set | second_set)
        record["both_blank"] = 0.0
    return record


def shard(args: argparse.Namespace) -> None:
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[variable] = "1"
    rows = [replicate(index, args.sample_size, args.variables, args.arm, args.seed) for index in range(args.replications)]
    frame = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)
    print(f"n={args.sample_size} p={args.variables} {args.arm}: {len(frame)} reps, "
          f"median runtime {frame.runtime_seconds.median():.1f}s, "
          f"blank {frame.explore_blank.mean():.3f}, "
          f"strong recovery {frame.explore_strong_recovery.mean():.3f}", flush=True)


# ---------------------------------------------------------------- summary


def summarize(args: argparse.Namespace) -> None:
    frames = [pd.read_parquet(path) for path in sorted(Path(args.shards).glob("*.parquet"))]
    if not frames:
        raise ValueError(f"no shard Parquet files found in {args.shards}")
    data = pd.concat(frames, ignore_index=True)

    rows = []
    for (n, p, arm), group in data.groupby(["sample_size", "variables", "arm"]):
        # Criterion 3 is conditional: a blank graph is only a failure when the truth
        # actually contained strong edges to find.
        eligible_blank = group[group.explore_strong_edges_present >= MIN_STRONG_EDGES]
        false_inclusion = float(group.explore_false_inclusion_rate.mean())
        expected_false = float(group.explore_false_edges.mean())
        recovery = float(group.explore_strong_recovery.mean())
        blank = float(eligible_blank.explore_blank.mean()) if len(eligible_blank) else np.nan
        runtime = float(group.runtime_seconds.median())
        explore_matched = float(group.explore_matched_strong_recovery.mean())
        baseline_matched = float(group.baseline_matched_strong_recovery.mean()) if "baseline_matched_strong_recovery" in group else np.nan
        beats = bool(explore_matched > baseline_matched) if not np.isnan(baseline_matched) else False
        rows.append({
            "sample_size": int(n), "variables": int(p), "arm": arm, "replications": len(group),
            "false_inclusion_rate": false_inclusion,
            "expected_false_edges": expected_false,
            "strong_recovery": recovery,
            "blank_given_strong_truth": blank,
            "explore_matched_recovery": explore_matched,
            "baseline_matched_recovery": baseline_matched,
            "matched_gain": explore_matched - baseline_matched,
            "runtime_seconds": runtime,
            "precision": float(group.explore_precision.mean()),
            "weak_recovery": float(group.explore_weak_recovery.mean()),
            "unconditional_blank": float(group.explore_blank.mean()),
            "jaccard_median": float(group.jaccard.median()),
            "both_blank_rate": float(group.both_blank.mean()),
            "pass_1a": false_inclusion <= TARGET_FALSE_INCLUSION,
            "pass_1b": expected_false <= EXPECTED_FALSE_EDGES_BAR,
            "pass_2": recovery >= RECOVERY_BAR,
            "pass_3": bool(blank <= BLANK_BAR) if not np.isnan(blank) else False,
            # Criterion 4 gates the nonlinear arm only; the linear arm reports the cost
            # of flexibility rather than being failed for it.
            "pass_4": beats if arm == "nonlinear" else True,
            "pass_5": runtime <= RUNTIME_BAR_SECONDS,
        })
    summary = pd.DataFrame(rows).sort_values(["arm", "sample_size", "variables"], ignore_index=True)
    gates = ["pass_1a", "pass_1b", "pass_2", "pass_3", "pass_4", "pass_5"]
    summary["eligible"] = summary[gates].all(axis=1)

    args.output.mkdir(parents=True, exist_ok=True)
    data.to_parquet(args.output / "explore_gate_results.parquet", index=False)
    summary.to_csv(args.output / "explore_gate_summary.csv", index=False)
    _plot(summary, args.output / "explore_gate.png")

    verdict = {
        "stage": args.stage,
        "operating_region": [
            {"sample_size": int(row.sample_size), "variables": int(row.variables), "arm": row.arm}
            for row in summary[summary.eligible].itertuples()
        ],
        "cells_evaluated": int(len(summary)),
        "cells_eligible": int(summary.eligible.sum()),
        "first_failing_gate": {
            f"{row.arm}-n{int(row.sample_size)}-p{int(row.variables)}": next((gate for gate in gates if not getattr(row, gate)), None)
            for row in summary[~summary.eligible].itertuples()
        },
        "median_runtime_seconds_by_cell": {
            f"{row.arm}-n{int(row.sample_size)}-p{int(row.variables)}": round(float(row.runtime_seconds), 2)
            for row in summary.itertuples()
        },
        "reading": (
            "A pilot stage may reject a design; it may not approve one. No criterion is established at "
            "pilot replication counts, and no cell listed under `operating_region` from a pilot run may be "
            "cited as eligible. The full run at the protocol's replication count is the only evidence that "
            "establishes the operating region."
            if args.stage == "pilot" else
            "Full-run evidence. `operating_region` lists the cells meeting every gated criterion in "
            "`docs/pilots/explore-feasibility-protocol.md`."
        ),
    }
    (args.output / "explore_gate_verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    pd.set_option("display.width", 260)
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print()
    print(json.dumps(verdict, indent=2, sort_keys=True))


def _plot(summary: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(2, 2, figsize=(13, 8.5))
    panels = [
        ("strong_recovery", "recovery of strong edges", RECOVERY_BAR),
        ("false_inclusion_rate", "false inclusion among nonedges", TARGET_FALSE_INCLUSION),
        ("blank_given_strong_truth", "blank graph when truth has strong edges", BLANK_BAR),
        ("matched_gain", "recovery gain over linear baseline", 0.0),
    ]
    for axis, (column, title, bar) in zip(axes.ravel(), panels):
        for arm, group in summary.groupby("arm"):
            averaged = group.groupby("sample_size")[column].mean()
            axis.plot(averaged.index, averaged.values, marker="o", label=arm)
        axis.axhline(bar, color="grey", linestyle=":", label="criterion")
        axis.set_title(title)
        axis.set_xlabel("sample size")
        axis.legend(fontsize=8)
        axis.grid(alpha=.3)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    shard_parser = commands.add_parser("shard", help="run one cell")
    shard_parser.add_argument("--sample-size", type=int, required=True, choices=SAMPLE_SIZES)
    shard_parser.add_argument("--variables", type=int, required=True, choices=VARIABLE_COUNTS)
    shard_parser.add_argument("--arm", choices=ARMS, required=True)
    shard_parser.add_argument("--replications", type=int, default=500)
    shard_parser.add_argument("--seed", type=int, default=20260811)
    shard_parser.add_argument("--output", type=Path, required=True)
    shard_parser.set_defaults(func=shard)

    summarize_parser = commands.add_parser("summarize", help="assemble shards into the operating region")
    summarize_parser.add_argument("--shards", type=Path, required=True)
    summarize_parser.add_argument("--output", type=Path, required=True)
    summarize_parser.add_argument("--stage", choices=("pilot", "full"), required=True)
    summarize_parser.set_defaults(func=summarize)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
