"""Explore p-extension: how does the mode scale from 10 variables toward 30?

Executes [`docs/pilots/explore-p-extension-protocol.md`](../docs/pilots/explore-p-extension-protocol.md).
Builds nothing in `src/`; the estimators here are study articles.

Three differences from the completed 6-to-10-variable study, each approved and each
answering something that study could not.

**Density is set by average connections per variable**, not by an edge probability. A
percentage means something different at 6 variables than at 30: a fixed 30% would give
30-variable networks about 130 relationships, which no published psychological network
resembles. Two connections per variable is sparse; four is moderately dense.

**Half the variables are curved, not all of them.** The completed study transformed every
variable in its nonlinear arm, so every relationship there was curved and none could be
compared against a straight one inside the same network. Here a relationship is *curved*
when either of its variables is transformed and *straight* when neither is, so both exist
side by side and the source of any advantage becomes attributable.

**A third arm runs the identical pipeline with straight-line terms only.** The completed
study compared explore against the field standard, and those differ in several ways at once
-- curved terms, but also a different selection procedure and a different treatment of each
variable. `explore-straight` holds everything fixed except the basis, which is the only way
to say what the curves themselves are worth.

**False connections are the share of *retained* relationships that are genuinely absent** --
of the lines drawn, how many are spurious. The completed study gated the complementary
quantity, the share of absent pairs that received a line. They are not interchangeable, and
recomputing the completed study under this definition would fail 17 of its 50 passing cells
at a 0.05 bar. Both are recorded here so either reading is available.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explore_gate import (  # noqa: E402  -- path shim must precede the import
    NONLINEAR_SHAPES, QUADRATURE_NODES, STRONG_TAU, TAU_MARGIN,
    _apply_shape, _group_lasso_path, _spline_blocks, _standardise,
    baseline_path, ebic_choice, explore_edges, oracle_tau,
)

VARIABLE_COUNTS = (12, 15, 20, 25, 30)
SAMPLE_SIZES = (75, 100, 150, 250, 500)
DENSITIES = {"sparse": 2.0, "moderate": 4.0}
ARMS = ("linear", "mixed")

CURVED_FRACTION = 0.5
MIN_STRONG_EDGES = 2
MIN_WEAK_EDGES = 1
MIN_CURVED_EDGES = 1
MIN_STRAIGHT_EDGES = 1

SUBSAMPLES = 50
SUBSAMPLE_FRACTION = 0.5
RETENTION_THRESHOLD = 0.75
FALSE_CONNECTION_BAR = 0.10

STRONG_TARGET_EDGES = 3
STRONG_MAGNITUDE = (0.45, 0.70)
MODEST_MAGNITUDE = (0.08, 0.28)
EIGENVALUE_FLOOR = 0.08
"""Smallest eigenvalue the precision matrix is allowed. Off-diagonals are scaled down
together when a draw falls below it, which is what keeps the matrix a valid one."""

DRAW_ATTEMPTS = 100


def degree_cap(average_degree: float) -> int:
    """Densest node the sampler permits, and the estimator's per-node quota.

    One function serves both, which is the lesson of the completed study: deriving them
    separately let rounding put the quota below the cap, so a node at maximum degree could
    not have all its relationships selected however good the data were.
    """
    return int(round(average_degree)) + 2


# ---------------------------------------------------------------- generating process


@dataclass
class Truth:
    adjacency: np.ndarray
    covariance: np.ndarray
    shapes: list[str]
    strength: np.ndarray
    curved_pair: np.ndarray


def sample_structure(rng: np.random.Generator, p: int, average_degree: float) -> tuple[np.ndarray, np.ndarray]:
    """Draw a skeleton at the requested average degree and a precision matrix on it."""
    cap = degree_cap(average_degree)
    target_edges = int(round(p * average_degree / 2))
    adjacency = np.zeros((p, p), dtype=bool)
    pairs = [(i, j) for i in range(p) for j in range(i + 1, p)]
    chosen_pairs: list[tuple[int, int]] = []
    for index in rng.permutation(len(pairs)):
        if len(chosen_pairs) >= target_edges:
            break
        i, j = pairs[index]
        if adjacency[i].sum() < cap and adjacency[j].sum() < cap:
            adjacency[i, j] = adjacency[j, i] = True
            chosen_pairs.append((i, j))

    # Relationship strengths are heterogeneous by design: a few genuinely strong, the rest
    # modest. Real psychological networks look like that, and drawing every edge from one
    # range does not.
    #
    # This replaced a construction that guaranteed positive definiteness by diagonal
    # dominance, which set each diagonal entry to the *sum* of a node's edge magnitudes and
    # so roughly halved every partial correlation when the average degree doubled. Density
    # and relationship strength were welded together: at degree 4 only a third of graphs
    # carried the two strong relationships the protocol requires, and the sampler exhausted
    # its attempts on Actions. Replacing dominance with an eigenvalue shift made it worse
    # rather than better, which is what identified the real constraint -- any valid precision
    # matrix with many strong off-diagonals needs a large diagonal, so a dense graph *cannot*
    # have uniformly strong relationships. Heterogeneity is the way out, not a milder shift.
    #
    # With a unit diagonal the off-diagonal entries are the partial correlations themselves,
    # so strength is set directly rather than emerging from whatever positive definiteness
    # happened to cost.
    offdiag = np.zeros((p, p))
    for rank, position in enumerate(rng.permutation(len(chosen_pairs))):
        i, j = chosen_pairs[position]
        low, high = STRONG_MAGNITUDE if rank < STRONG_TARGET_EDGES else MODEST_MAGNITUDE
        offdiag[i, j] = offdiag[j, i] = rng.choice((-1.0, 1.0)) * rng.uniform(low, high)
    smallest = float(np.linalg.eigvalsh(np.eye(p) + offdiag)[0])
    if smallest < EIGENVALUE_FLOOR:
        offdiag *= (1 - EIGENVALUE_FLOOR) / (1 - smallest)

    covariance = np.linalg.inv(np.eye(p) + offdiag)
    scale = np.sqrt(np.diag(covariance))
    return adjacency, covariance / np.outer(scale, scale)


def draw_truth(rng: np.random.Generator, p: int, average_degree: float, arm: str) -> tuple[Truth, int]:
    """Rejection-sample until the graph can actually be scored against the protocol."""
    curved_count = 0 if arm == "linear" else int(round(CURVED_FRACTION * p))
    for attempt in range(DRAW_ATTEMPTS):
        adjacency, covariance = sample_structure(rng, p, average_degree)
        curved_nodes = rng.permutation(p)[:curved_count]
        shapes = ["identity"] * p
        for position, node in enumerate(curved_nodes):
            shapes[node] = NONLINEAR_SHAPES[position % len(NONLINEAR_SHAPES)]

        tau = oracle_tau(covariance, shapes, rng)
        strength = np.minimum(tau, tau.T)
        np.fill_diagonal(strength, 0.0)
        strength[~adjacency] = 0.0
        curved = np.array([shape != "identity" for shape in shapes])
        curved_pair = curved[:, None] | curved[None, :]

        upper = np.triu_indices(p, 1)
        values, present, is_curved = strength[upper], adjacency[upper], curved_pair[upper]
        strong = (values >= STRONG_TAU) & present
        if np.any(np.abs(values[present] - STRONG_TAU) < TAU_MARGIN):
            continue
        if int(strong.sum()) < MIN_STRONG_EDGES or int((present & (values < STRONG_TAU)).sum()) < MIN_WEAK_EDGES:
            continue
        # Criteria 6 and 7 compare curved against straight relationships inside one network,
        # so a graph carrying only one kind cannot score them.
        if arm == "mixed" and (int((present & is_curved).sum()) < MIN_CURVED_EDGES or int((present & ~is_curved).sum()) < MIN_STRAIGHT_EDGES):
            continue
        return Truth(adjacency, covariance, shapes, strength, curved_pair), attempt
    raise RuntimeError(f"no admissible graph at p={p}, degree={average_degree}, arm={arm}")


def generate(truth: Truth, n: int, rng: np.random.Generator) -> np.ndarray:
    p = truth.covariance.shape[0]
    latent = rng.multivariate_normal(np.zeros(p), truth.covariance, size=n, method="cholesky")
    return np.column_stack([_apply_shape(latent[:, k], truth.shapes[k]) for k in range(p)])


# ---------------------------------------------------------------- estimator arms


def _linear_blocks(values: np.ndarray) -> list[np.ndarray]:
    """One orthonormalised straight-line term per variable.

    Identical in role to the spline blocks, so `explore-straight` differs from `explore`
    in the basis and in nothing else -- not the penalty, not the resampling, not the AND
    rule. That is the whole point of the arm.
    """
    blocks = []
    for column in range(values.shape[1]):
        vector = values[:, [column]] - values[:, [column]].mean()
        norm = float(np.linalg.norm(vector))
        blocks.append(vector / norm if norm > 0 else vector)
    return blocks


def selection_frequencies(values: np.ndarray, rng: np.random.Generator, average_degree: float, *, curved: bool) -> np.ndarray:
    n, p = values.shape
    standardised = _standardise(values)
    blocks_by_column = (_spline_blocks if curved else _linear_blocks)(standardised)
    quota = degree_cap(average_degree)
    size = max(8, int(round(SUBSAMPLE_FRACTION * n)))

    counts = np.zeros((p, p))
    for _ in range(SUBSAMPLES):
        rows = rng.choice(n, size=size, replace=False)
        for target in range(p):
            others = [k for k in range(p) if k != target]
            active = _group_lasso_path([blocks_by_column[k][rows] for k in others], standardised[rows, target], quota)
            for position in active:
                counts[target, others[position]] += 1
    return counts / SUBSAMPLES


# ---------------------------------------------------------------- scoring


def score(estimated: np.ndarray, truth: Truth) -> dict[str, float]:
    p = truth.adjacency.shape[0]
    upper = np.triu_indices(p, 1)
    drawn, present = estimated[upper], truth.adjacency[upper]
    strength, curved = truth.strength[upper], truth.curved_pair[upper]
    strong = present & (strength >= STRONG_TAU)
    weak = present & (strength < STRONG_TAU)

    def share(mask: np.ndarray) -> float:
        return float(drawn[mask].mean()) if mask.any() else np.nan

    return {
        # Protocol section 2: of the lines drawn, how many are spurious.
        "false_connection_share": float((~present)[drawn].mean()) if drawn.any() else np.nan,
        "retained_edges": float(drawn.sum()),
        "false_edges": float(drawn[~present].sum()),
        # The completed study's quantity, kept so both readings are available.
        "false_positive_rate": share(~present),
        "strong_recovery": share(strong),
        "weak_recovery": share(weak),
        "curved_recovery": share(present & curved),
        "straight_recovery": share(present & ~curved),
        "curved_strong_recovery": share(strong & curved),
        "straight_strong_recovery": share(strong & ~curved),
        "blank": float(not drawn.any()),
        "strong_edges_present": float(strong.sum()),
        "true_edges": float(present.sum()),
    }


def matched_point(candidates: list[tuple[float, np.ndarray]], truth: Truth, *, target_edges: float | None) -> dict[str, float]:
    """Best operating point under one of the two matched rules.

    With `target_edges`, both methods are held to the same number of drawn relationships --
    which method spends a fixed budget of lines better. Without it, both are held to the
    same false-connection share and recovery is read there. Recovery bought by drawing more
    is not recovery, so neither method is ever read at its own default.
    """
    scored = [score(adjacency, truth) for _, adjacency in candidates]
    if target_edges is not None:
        return min(scored, key=lambda item: (abs(item["retained_edges"] - target_edges), -item["strong_recovery"]))
    admissible = [item for item in scored
                  if not np.isnan(item["false_connection_share"]) and item["false_connection_share"] <= FALSE_CONNECTION_BAR]
    if not admissible:
        return min(scored, key=lambda item: (np.inf if np.isnan(item["false_connection_share"]) else item["false_connection_share"]))
    return max(admissible, key=lambda item: (-1.0 if np.isnan(item["strong_recovery"]) else item["strong_recovery"], item["retained_edges"]))


# ---------------------------------------------------------------- replication


def replicate(index: int, p: int, n: int, density: str, arm: str, seed: int) -> dict[str, object]:
    average_degree = DENSITIES[density]
    rng = np.random.default_rng(np.random.SeedSequence(
        [seed, p, n, sorted(DENSITIES).index(density), ARMS.index(arm), index]))

    oracle_started = time.perf_counter()
    truth, redraws = draw_truth(rng, p, average_degree, arm)
    oracle_seconds = time.perf_counter() - oracle_started
    values = generate(truth, n, rng)
    target_edges = float(truth.adjacency[np.triu_indices(p, 1)].sum())

    record: dict[str, object] = {
        "replicate": index, "variables": p, "sample_size": n, "density": density, "arm": arm,
        "redraws": redraws, "oracle_seconds": oracle_seconds, "true_edges": target_edges,
    }
    thresholds = np.linspace(0.5, 1.0, 11)

    explore_frequencies = None
    for label, curved in (("explore", True), ("explore_straight", False)):
        started = time.perf_counter()
        frequencies = selection_frequencies(values, rng, average_degree, curved=curved)
        record[f"{label}_seconds"] = time.perf_counter() - started
        if curved:
            explore_frequencies = frequencies
        path = [(float(t), explore_edges(frequencies, t)) for t in thresholds]
        record.update({f"{label}_{k}": v for k, v in score(explore_edges(frequencies, RETENTION_THRESHOLD), truth).items()})
        record.update({f"{label}_matched_fc_{k}": v for k, v in matched_point(path, truth, target_edges=None).items()})
        record.update({f"{label}_matched_density_{k}": v for k, v in matched_point(path, truth, target_edges=target_edges).items()})

    started = time.perf_counter()
    path = baseline_path(values)
    if path:
        record.update({f"baseline_{k}": v for k, v in score(ebic_choice(values, path), truth).items()})
        record.update({f"baseline_matched_fc_{k}": v for k, v in matched_point(path, truth, target_edges=None).items()})
        record.update({f"baseline_matched_density_{k}": v for k, v in matched_point(path, truth, target_edges=target_edges).items()})
    record["baseline_seconds"] = time.perf_counter() - started

    # Stability: a second independent dataset from the same truth, compared against the
    # explore fit already scored above rather than a fresh one on the same data -- refitting
    # would measure resampling noise instead of between-dataset agreement, and would cost a
    # fit the stage projections would then have to carry.
    second = explore_edges(selection_frequencies(generate(truth, n, rng), rng, average_degree, curved=True), RETENTION_THRESHOLD)
    first = explore_edges(explore_frequencies, RETENTION_THRESHOLD)
    upper = np.triu_indices(p, 1)
    a, b = first[upper], second[upper]
    present, strength = truth.adjacency[upper], truth.strength[upper]
    for name, mask in (("strong", present & (strength >= STRONG_TAU)), ("weak", present & (strength < STRONG_TAU)), ("absent", ~present)):
        union = int((a | b)[mask].sum())
        record[f"stability_{name}"] = (int((a & b)[mask].sum()) / union) if union else np.nan
    union_all = int((a | b).sum())
    record["stability_all"] = (int((a & b).sum()) / union_all) if union_all else np.nan
    return record


def shard(args: argparse.Namespace) -> None:
    for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[variable] = "1"
    # Memory is read from the OS after the fact rather than traced during. `tracemalloc`
    # inflated these timings roughly tenfold in local testing, which would have corrupted
    # the one measurement this stage exists to take -- and it tracks only the Python
    # allocator, so it misses the numpy arrays that dominate this workload anyway.
    rows = [replicate(index, args.variables, args.sample_size, args.density, args.arm, args.seed)
            for index in range(args.offset, args.offset + args.replications)]
    frame = pd.DataFrame(rows)
    try:
        import resource
        frame["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except (ImportError, AttributeError):  # not available on Windows; the runners are Linux
        frame["peak_rss_mb"] = np.nan
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)
    total = frame.explore_seconds + frame.explore_straight_seconds + frame.baseline_seconds + frame.oracle_seconds
    print(f"p={args.variables} n={args.sample_size} {args.density}/{args.arm}: {len(frame)} reps | "
          f"explore {frame.explore_seconds.median():.1f}s straight {frame.explore_straight_seconds.median():.1f}s "
          f"baseline {frame.baseline_seconds.median():.1f}s oracle {frame.oracle_seconds.median():.1f}s | "
          f"total/rep {total.median():.1f}s | peak RSS {frame.peak_rss_mb.iloc[0]:.0f}MB", flush=True)


# ---------------------------------------------------------------- stage 0 summary


def summarize(args: argparse.Namespace) -> None:
    frames = [pd.read_parquet(path) for path in sorted(Path(args.shards).glob("*.parquet"))]
    if not frames:
        raise ValueError(f"no shard Parquet files found in {args.shards}")
    data = pd.concat(frames, ignore_index=True)
    data["total_seconds"] = data.explore_seconds + data.explore_straight_seconds + data.baseline_seconds + data.oracle_seconds
    # Stability costs one further explore fit per replication, which the timing must carry
    # or the stage projections will understate the real grids.
    data["replication_seconds"] = data.total_seconds + data.explore_seconds

    summary = data.groupby(["variables", "sample_size"]).agg(
        replications=("replicate", "count"),
        explore_seconds=("explore_seconds", "median"),
        explore_straight_seconds=("explore_straight_seconds", "median"),
        baseline_seconds=("baseline_seconds", "median"),
        oracle_seconds=("oracle_seconds", "median"),
        replication_seconds=("replication_seconds", "median"),
        peak_rss_mb=("peak_rss_mb", "max"),
        redraws=("redraws", "mean"),
    ).reset_index()

    # Scaling slope in variable count: seconds ~ p**exponent, read between the two p values
    # at each sample size. One p value gives a number; two give a slope, which is the only
    # thing that can say whether the extrapolations behind Stages 1 and 2 hold.
    slopes = {}
    for n, group in summary.groupby("sample_size"):
        if len(group) >= 2:
            ordered = group.sort_values("variables")
            low, high = ordered.iloc[0], ordered.iloc[-1]
            slopes[str(int(n))] = round(float(
                np.log(high.replication_seconds / low.replication_seconds) / np.log(high.variables / low.variables)), 2)

    def project(cells: list[tuple[int, int]], replications: int) -> float:
        """Core-hours for a grid, from measured cost and the fitted exponent.

        **Cost is not scaled by sample size.** The first version of this function scaled by
        `n / reference_n`, which predicted 9s per replication for the 30-variable
        100-person cell against 44s measured -- a fivefold under-estimate. Sample size
        barely moves the cost in this range: 44.3s against 45.1s at 30 variables for a
        fivefold difference in rows. The work is dominated by the loop over variables,
        subsamples and penalty steps, none of which grow with row count, and more data can
        even shorten the penalty path by reaching the selection quota sooner.

        The steeper of the two measured slopes is used, so the estimate errs high.
        """
        exponent = max(slopes.values()) if slopes else 2.0
        reference = summary.loc[summary.variables.idxmax()]
        reference_seconds = float(summary[summary.variables == reference.variables].replication_seconds.max())
        return sum(reference_seconds * (p / reference.variables) ** exponent * replications
                   for p, _ in cells) / 3600

    stage1 = [(p, n) for p in (12, 15) for n in (75, 100, 150, 250) for _ in range(4)]
    stage2 = [(p, n) for p in (20, 25, 30) for n in (100, 150, 250, 500) for _ in range(4)]
    longest = max(summary.replication_seconds) * 500 / 3600

    args.output.mkdir(parents=True, exist_ok=True)
    data.to_parquet(args.output / "p_extension_stage0_results.parquet", index=False)
    summary.to_csv(args.output / "p_extension_stage0_summary.csv", index=False)

    verdict = {
        "stage": "0",
        "purpose": "Measure how cost scales with variable count and sample size, and replace the protocol's extrapolated cost figures with measurements. Ten replications establish no performance criterion and none may be cited from this run.",
        "scaling_exponent_in_p_by_sample_size": slopes,
        "projected_core_hours": {
            "stage_1_32_cells_500_reps": round(project(stage1, 500), 1),
            "stage_2_48_cells_500_reps": round(project(stage2, 500), 1),
        },
        "protocol_extrapolation_for_comparison": {"stage_1": 90, "stage_2": 470},
        "largest_single_cell_hours_at_500_reps": round(longest, 1),
        "actions_job_limit_hours": 6,
        "shards_needed_for_largest_cell": int(np.ceil(longest / 6)),
        "peak_rss_mb": round(float(summary.peak_rss_mb.max()), 1),
    }
    (args.output / "p_extension_stage0_verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    pd.set_option("display.width", 250)
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.2f}"))
    print()
    print(json.dumps(verdict, indent=2, sort_keys=True))


RECOVERY_BAR = 0.60
BLANK_BAR = 0.10
STABILITY_BAR = 0.80
STRAIGHT_TOLERANCE = 0.05
BOOTSTRAP_DRAWS = 2000


def _clopper_pearson(successes: int, trials: int) -> tuple[float, float]:
    """Exact binomial interval, treating each drawn relationship as its own trial."""
    from scipy.stats import beta
    if trials == 0:
        return float("nan"), float("nan")
    lower = 0.0 if successes == 0 else float(beta.ppf(.025, successes, trials - successes + 1))
    upper = 1.0 if successes == trials else float(beta.ppf(.975, successes + 1, trials - successes))
    return lower, upper


def _bootstrap_share(numerator: np.ndarray, denominator: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    """Percentile interval resampling whole replications.

    Relationships drawn within one network are not independent, so the exact binomial
    interval above is too narrow. This one resamples replications rather than edges, which
    respects that, and it is the interval that governs where the two disagree.
    """
    count = len(numerator)
    if count == 0 or denominator.sum() == 0:
        return float("nan"), float("nan")
    picks = rng.integers(0, count, size=(BOOTSTRAP_DRAWS, count))
    totals = denominator[picks].sum(axis=1)
    shares = np.divide(numerator[picks].sum(axis=1), totals, out=np.full(BOOTSTRAP_DRAWS, np.nan), where=totals > 0)
    return float(np.nanpercentile(shares, 2.5)), float(np.nanpercentile(shares, 97.5))


def summarize_criteria(args: argparse.Namespace) -> None:
    """Score the protocol's seven criteria. Stages 1 and 2 only."""
    frames = [pd.read_parquet(path) for path in sorted(Path(args.shards).glob("*.parquet"))]
    if not frames:
        raise ValueError(f"no shard Parquet files found in {args.shards}")
    data = pd.concat(frames, ignore_index=True)
    rng = np.random.default_rng(20260812)

    rows = []
    for (p, n, density, arm), group in data.groupby(["variables", "sample_size", "density", "arm"]):
        # Criteria 1 to 4 are scored at the default operating point, which is what a user
        # actually gets. Scoring them at the matched-false-inclusion point would be circular,
        # since that point is chosen to sit under the very bar criterion 1 tests.
        false_edges, retained = group.explore_false_edges.to_numpy(), group.explore_retained_edges.to_numpy()
        share = float(false_edges.sum() / retained.sum()) if retained.sum() else np.nan
        exact = _clopper_pearson(int(false_edges.sum()), int(retained.sum()))
        booted = _bootstrap_share(false_edges, retained, rng)

        scorable = group[group.explore_strong_edges_present >= MIN_STRONG_EDGES]
        recovery = float(group.explore_strong_recovery.mean())
        blank = float(scorable.explore_blank.mean()) if len(scorable) else np.nan
        stability = float(group.stability_strong.median())

        record = {
            "variables": int(p), "sample_size": int(n), "density": density, "arm": arm,
            "replications": len(group),
            "false_connection_share": share,
            "false_share_exact_low": exact[0], "false_share_exact_high": exact[1],
            "false_share_boot_low": booted[0], "false_share_boot_high": booted[1],
            "false_edges_per_network": float(group.explore_false_edges.mean()),
            "false_positive_rate": float(group.explore_false_positive_rate.mean()),
            "strong_recovery": recovery,
            "weak_recovery": float(group.explore_weak_recovery.mean()),
            "blank_given_strong_truth": blank,
            "stability_strong": stability,
            "stability_weak": float(group.stability_weak.median()),
            "runtime_seconds": float(group.explore_seconds.median()),
        }
        for setting in ("matched_fc", "matched_density"):
            for kind in ("curved", "straight"):
                for method in ("explore", "explore_straight", "baseline"):
                    column = f"{method}_{setting}_{kind}_recovery"
                    record[f"{method}_{setting}_{kind}"] = float(group[column].mean()) if column in group else np.nan

        record["pass_1_false_connections"] = bool(share <= FALSE_CONNECTION_BAR)
        record["pass_2_recovery"] = bool(recovery >= RECOVERY_BAR)
        record["pass_3_blank"] = bool(blank <= BLANK_BAR) if not np.isnan(blank) else False
        record["pass_4_stability"] = bool(stability >= STABILITY_BAR) if not np.isnan(stability) else False
        # Criteria 5 to 7 compare performance on curved relationships, which exist only in
        # the mixed arm. The fully linear arm is a control: it is gated on 1 to 4 and its
        # comparisons are reported rather than required.
        if arm == "mixed":
            record["pass_5_beats_baseline"] = bool(
                record["explore_matched_fc_curved"] > record["baseline_matched_fc_curved"]
                and record["explore_matched_density_curved"] > record["baseline_matched_density_curved"])
            record["pass_6_beats_straight_on_curved"] = bool(
                record["explore_matched_fc_curved"] > record["explore_straight_matched_fc_curved"])
            record["pass_7_holds_on_straight"] = bool(
                record["explore_matched_fc_straight"] >= record["explore_straight_matched_fc_straight"] - STRAIGHT_TOLERANCE)
        else:
            record["pass_5_beats_baseline"] = record["pass_6_beats_straight_on_curved"] = record["pass_7_holds_on_straight"] = True
        rows.append(record)

    summary = pd.DataFrame(rows).sort_values(["arm", "density", "variables", "sample_size"], ignore_index=True)
    gates = [column for column in summary.columns if column.startswith("pass_")]
    summary["eligible"] = summary[gates].all(axis=1)

    args.output.mkdir(parents=True, exist_ok=True)
    data.to_parquet(args.output / f"p_extension_stage{args.stage}_results.parquet", index=False)
    summary.to_csv(args.output / f"p_extension_stage{args.stage}_summary.csv", index=False)

    verdict = {
        "stage": args.stage,
        "cells_evaluated": int(len(summary)),
        "cells_eligible": int(summary.eligible.sum()),
        "operating_region": [
            {"variables": int(r.variables), "sample_size": int(r.sample_size), "density": r.density, "arm": r.arm}
            for r in summary[summary.eligible].itertuples()],
        "first_failing_gate": {
            f"{r.arm}-{r.density}-p{int(r.variables)}-n{int(r.sample_size)}": next((g for g in gates if not getattr(r, g)), None)
            for r in summary[~summary.eligible].itertuples()},
        "false_edges_per_network_by_size_and_density": {
            f"p{int(p)}-{d}": round(float(g.false_edges_per_network.mean()), 3)
            for (p, d), g in summary.groupby(["variables", "density"])},
        "reading": (
            "Criteria 1 to 4 are scored at the default operating point, which is what a user gets; scoring them "
            "at the matched-false-inclusion point would be circular. Criteria 5 to 7 compare curved-relationship "
            "performance and apply to the mixed arm only, since the fully linear arm contains no curved "
            "relationships; that arm is a control gated on 1 to 4. Where the exact binomial and bootstrap "
            "intervals on the false-connection share disagree, the bootstrap governs, because relationships "
            "within one network are not independent."),
    }
    (args.output / f"p_extension_stage{args.stage}_verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    pd.set_option("display.width", 300)
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print()
    print(json.dumps(verdict, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    shard_parser = commands.add_parser("shard", help="run one cell")
    shard_parser.add_argument("--variables", type=int, required=True, choices=VARIABLE_COUNTS)
    shard_parser.add_argument("--sample-size", type=int, required=True, choices=SAMPLE_SIZES)
    shard_parser.add_argument("--density", choices=tuple(DENSITIES), default="moderate")
    shard_parser.add_argument("--arm", choices=ARMS, default="mixed")
    shard_parser.add_argument("--replications", type=int, default=10)
    shard_parser.add_argument("--offset", type=int, default=0)
    shard_parser.add_argument("--seed", type=int, default=20260812)
    shard_parser.add_argument("--output", type=Path, required=True)
    shard_parser.set_defaults(func=shard)

    summarize_parser = commands.add_parser("summarize", help="assemble the stage report")
    summarize_parser.add_argument("--shards", type=Path, required=True)
    summarize_parser.add_argument("--output", type=Path, required=True)
    summarize_parser.add_argument("--stage", default="0", choices=("0", "1", "2"))
    summarize_parser.set_defaults(func=lambda args: summarize(args) if args.stage == "0" else summarize_criteria(args))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
