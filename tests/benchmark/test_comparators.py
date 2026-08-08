from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd
import pytest

from renca.benchmark.comparators import (
    STRUCTURAL_METHODS,
    ebic_glasso_path,
    ebicglasso_adjacency,
    glasso_path,
    pc_adjacency,
    structural_adjacency,
)
from renca.benchmark.dgp import generate_sample, sample_graph

# PC, FCI and GES come from causal-learn, which is an optional extra: the package must not
# require a causal-discovery stack to certify a nonedge. CI installs it so these run.
needs_causal_learn = pytest.mark.skipif(
    importlib.util.find_spec("causallearn") is None,
    reason="causal-learn is not installed; install the 'comparators' extra",
)


@pytest.fixture(scope="module")
def chain() -> pd.DataFrame:
    """v0 -> v1 -> v2, so the only conditional independence is v0 _||_ v2 | v1."""
    generator = np.random.default_rng(4)
    v0 = generator.normal(size=4000)
    v1 = .8 * v0 + .6 * generator.normal(size=4000)
    v2 = .8 * v1 + .6 * generator.normal(size=4000)
    return pd.DataFrame({"v0": v0, "v1": v1, "v2": v2})


@needs_causal_learn
@pytest.mark.parametrize("method,setting", [("pc", .05), ("conservative_pc", .05), ("fci", .05), ("ges", 1.0)])
def test_every_constraint_or_score_baseline_recovers_a_chain(method: str, setting: float, chain: pd.DataFrame) -> None:
    """A sanity floor: with 4,000 clean rows each baseline should find exactly the chain."""
    assert structural_adjacency(method, chain, setting=setting) == {frozenset({"v0", "v1"}), frozenset({"v1", "v2"})}


def test_ebicglasso_recovers_the_moral_graph_at_large_n() -> None:
    """The graphical lasso is not asked to pass the three-node chain, and should not be.

    Two things make that fixture the wrong bar. With only three possible edges and endpoint
    correlations near 0.8, no penalty separates the weak edge from the strong ones. And a
    Gaussian graphical model estimates the *moral* graph, so co-parent pairs carry a real
    partial correlation and can never be pruned however much data it sees -- scoring it
    against DAG adjacency caps it below 1 by construction.
    """
    graph = sample_graph(p=10, seed=4, family="linear_gaussian")
    data = generate_sample(graph, n=4000, seed=88)
    moral = graph.adjacent_pairs() | graph.moral_only_pairs()
    adjacency = structural_adjacency("ebicglasso", data, setting=.5)
    pruned = graph.all_pairs() - adjacency

    assert moral <= adjacency                     # every moral edge recovered
    assert not pruned & graph.adjacent_pairs()    # and no true edge dropped
    ceiling = len(graph.nonadjacent_pairs() - graph.moral_only_pairs())
    assert len(pruned) >= .6 * ceiling


def test_refitting_stops_ebic_from_selecting_a_near_dense_graph() -> None:
    """Scored on the penalised fit, the likelihood improves as the penalty falls purely
    because surviving edges are shrunk less, so EBIC runs to the end of the path. The
    criterion is defined on the unpenalised MLE of each selected support for exactly this
    reason, and without it the baseline would have been a strawman.
    """
    graph = sample_graph(p=10, seed=4, family="linear_gaussian")
    data = generate_sample(graph, n=4000, seed=88)
    correlation = np.corrcoef(data.to_numpy(), rowvar=False)

    refit = ebic_glasso_path(correlation, len(data), points=glasso_path(correlation, refit=True))[2]
    penalised = ebic_glasso_path(correlation, len(data), points=glasso_path(correlation, refit=False))[2]

    assert refit.loc[refit.ebic.idxmin()].edges < penalised.loc[penalised.ebic.idxmin()].edges
    assert penalised.ebic.idxmin() == len(penalised) - 1  # monotone to the densest point


@needs_causal_learn
def test_conservative_pc_has_the_same_skeleton_as_pc() -> None:
    """Section 41 names both, but conservative PC changes only collider orientation.

    Since this comparison scores adjacency, the two are one baseline, not two. Asserting it
    keeps the write-up from presenting a duplicated curve as independent corroboration.
    """
    for seed in range(4):
        graph = sample_graph(p=10, seed=seed, family="linear_gaussian")
        data = generate_sample(graph, n=400, seed=100 + seed)
        assert pc_adjacency(data, alpha=.05) == pc_adjacency(data, alpha=.05, conservative=True)


@needs_causal_learn
def test_the_test_level_traces_a_monotone_pruning_curve() -> None:
    """Sweeping alpha is what turns a baseline into a trade-off curve.

    PC removes an edge when it *fails* to reject independence, so a smaller alpha prunes
    more. If that ordering did not hold the sweep would not be a curve at all.
    """
    graph = sample_graph(p=15, seed=1, family="linear_gaussian")
    data = generate_sample(graph, n=375, seed=55)
    counts = [len(pc_adjacency(data, alpha=alpha)) for alpha in (.001, .01, .05, .20)]
    assert counts == sorted(counts)


def test_ebic_selects_a_sparser_graph_as_gamma_rises() -> None:
    graph = sample_graph(p=15, seed=2, family="linear_gaussian")
    data = generate_sample(graph, n=375, seed=56)
    assert len(ebicglasso_adjacency(data, gamma=1.0)) <= len(ebicglasso_adjacency(data, gamma=.0))


def test_ebic_path_reports_the_criterion_it_minimised() -> None:
    """The selection rule is implemented here rather than taken from a package, so the
    criterion it actually optimises is checked instead of assumed."""
    graph = sample_graph(p=8, seed=3, family="linear_gaussian")
    data = generate_sample(graph, n=1000, seed=57)
    correlation = np.corrcoef(data.to_numpy(), rowvar=False)
    precision, penalty, path = ebic_glasso_path(correlation, len(data), gamma=.5)
    chosen = path.loc[path.ebic.idxmin()]
    assert chosen.penalty == pytest.approx(penalty)
    assert int((np.abs(np.triu(precision, 1)) > 1e-8).sum()) == int(chosen.edges)
    assert path.edges.iloc[0] <= path.edges.iloc[-1]  # the path runs from sparse to dense


def test_an_unknown_baseline_is_rejected_rather_than_silently_skipped() -> None:
    with pytest.raises(ValueError, match="unknown structural baseline"):
        structural_adjacency("mgm", pd.DataFrame({"a": [1.0], "b": [2.0]}), setting=.05)
    assert set(STRUCTURAL_METHODS) == {"pc", "conservative_pc", "fci", "ges", "ebicglasso"}
