from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from renca.benchmark.dgp import (
    BenchmarkGraph,
    DGP_FAMILIES,
    generate_sample,
    graph_summary,
    oracle_edge_theta,
    oracle_theta,
    population_covariance,
    practical_nonedge_pairs,
    sample_graph,
)


@pytest.mark.parametrize("family", DGP_FAMILIES)
def test_graphs_respect_the_operating_region_the_gate_names(family: str) -> None:
    """Specification section 13.4 fixes p=15 and degree <= 3, so the cap must bind exactly."""
    for seed in range(12):
        summary = graph_summary(sample_graph(p=15, seed=seed, family=family))
        assert summary["p"] == 15
        assert summary["max_degree"] <= 3
        assert summary["edges"] + summary["nonedges"] == 105


@pytest.mark.parametrize("family", DGP_FAMILIES)
def test_every_node_is_scaled_to_unit_variance(family: str) -> None:
    """`Theta` divides by `R_i(empty)`, so an unscaled node would silently rescale its own delta."""
    for seed in range(4):
        graph = sample_graph(p=15, seed=seed, family=family)
        variances = generate_sample(graph, n=60_000, seed=900 + seed).var()
        assert variances.between(.85, 1.15).all(), variances[~variances.between(.85, 1.15)]


def test_nonlinear_transforms_never_stack() -> None:
    """Stacked cubics gave marginal kurtosis above 16,000, which breaks Fisher-z for the
    wrong reason: PC would fail on non-normality rather than on nonlinearity, and beating
    a baseline broken by an unrelated violation would prove nothing.
    """
    for seed in range(12):
        graph = sample_graph(p=15, seed=seed, family="additive_nonlinear")
        gaussian = [True] * graph.p
        for child, (group, forms) in enumerate(zip(graph.parents, graph.forms)):
            for parent, form in zip(group, forms):
                assert form == "linear" or gaussian[parent], f"nonlinear edge {parent}->{child} onto a non-Gaussian parent"
            gaussian[child] = all(gaussian[parent] and form == "linear" for parent, form in zip(group, forms))
        assert generate_sample(graph, n=40_000, seed=7).kurtosis().max() < 100


def test_a_cubic_edge_is_invisible_to_partial_correlation() -> None:
    """The discriminating case: `He_3` is orthogonal to x and x**2 by construction.

    A covariance-based conditional-independence test therefore sees nothing while the
    dependence is strong, which is the whole reason section 43 requires this condition.
    """
    graph = BenchmarkGraph(
        p=2, parents=((), (0,)), coefficients=((), (1.0,)), forms=((), ("cubic",)), noise_sd=(1.0, .5), family="additive_nonlinear",
    )
    sample = generate_sample(graph, n=200_000, seed=3)
    correlation = float(np.corrcoef(sample.v00, sample.v01)[0, 1])
    # Zero linear association, but the parent explains a large share of the child's variance.
    assert abs(correlation) < .01
    explained = 1 - float(np.var(sample.v01 - _cubic_fit(sample.v00, sample.v01)) / np.var(sample.v01))
    assert explained > .5


def _cubic_fit(x: pd.Series, y: pd.Series) -> np.ndarray:
    design = np.column_stack([np.ones(len(x)), x, x**2, x**3])
    return design @ np.linalg.lstsq(design, y.to_numpy(), rcond=None)[0]


def test_linear_gaussian_oracle_matches_a_large_sample_estimate() -> None:
    """The oracle decides whether a scored false prune was really an error, so it is checked
    against data rather than trusted as algebra."""
    graph = sample_graph(p=8, seed=5, family="linear_gaussian")
    sample = generate_sample(graph, n=400_000, seed=11)
    empirical = np.cov(sample.to_numpy(), rowvar=False)
    assert np.abs(empirical - population_covariance(graph)).max() < .02

    target, added, separator = graph.names[3], graph.names[1], [graph.names[0]]
    reduced = _residual_variance(sample, target, separator)
    expanded = _residual_variance(sample, target, separator + [added])
    measured = (reduced - expanded) / float(sample[target].var())
    assert oracle_theta(graph, target, added, separator) == pytest.approx(measured, abs=.005)


def _residual_variance(sample: pd.DataFrame, target: str, features: list[str]) -> float:
    design = np.column_stack([np.ones(len(sample))] + [sample[name].to_numpy() for name in features])
    residual = sample[target].to_numpy() - design @ np.linalg.lstsq(design, sample[target].to_numpy(), rcond=None)[0]
    return float(np.var(residual))


def test_a_real_share_of_true_edges_falls_below_the_calibrated_deltas() -> None:
    """The generated graphs deliberately span a realistic range of edge strengths.

    A degree-3 node splitting 30-60% explained variance across its parents leaves some edges
    genuinely negligible, and that is what real networks look like. It also means graphical
    adjacency and practical absence are *not* the same truth, which is why both are scored:
    in the pilot, all nine adjacencies pruned at delta=0.20 were edges under 0.20.

    This test exists so that if the design is ever changed to make every edge strong, the
    reason for the two-truth scoring disappears loudly rather than silently.
    """
    graphs = [sample_graph(p=15, seed=seed, family="linear_gaussian") for seed in range(10)]
    thetas = pd.concat([oracle_edge_theta(graph) for graph in graphs])
    assert (thetas.theta >= 0).all()

    below = {
        delta: sum(len(practical_nonedge_pairs(graph, delta) - graph.nonadjacent_pairs()) for graph in graphs)
        for delta in (.05, .10, .20)
    }
    edges = sum(len(graph.adjacent_pairs()) for graph in graphs)
    assert below[.05] < below[.10] < below[.20]      # coarser resolutions absorb more edges
    assert below[.05] / edges < .15                  # but 0.05 leaves nearly every edge real
    assert .2 < below[.20] / edges < .7              # while 0.20 reclassifies a large minority


def test_samples_are_reproducible_and_seed_separated() -> None:
    graph = sample_graph(p=10, seed=2, family="linear_gaussian")
    assert generate_sample(graph, n=200, seed=4).equals(generate_sample(graph, n=200, seed=4))
    assert not generate_sample(graph, n=200, seed=4).equals(generate_sample(graph, n=200, seed=5))
    assert sample_graph(p=10, seed=2, family="linear_gaussian").parents == graph.parents
