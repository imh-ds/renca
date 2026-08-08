"""Random sparse DAGs for the specification section 13.4 comparative gate.

The gate names a realistic operating region -- ``p=15``, ``n<=2000``, degree ``<=3`` --
and requires the method's false-prune/true-prune trade-off to be compared against PC, FCI
and EBICglasso there. This module supplies the ground truth those comparisons need.

Two families are generated from the same graphs.

``linear_gaussian`` is the comparators' home turf: partial correlation is a valid
conditional-independence test, so Fisher-z PC is correctly specified and the graphical
lasso's sparsity pattern is the true conditional-independence structure. Any advantage the
present method shows here cannot be attributed to a misspecified baseline.

``additive_nonlinear`` applies a monotone, quadratic, cubic or saturating transform to each
edge. Specification section 43 requires nonlinear dependence invisible to conditional
covariance; the cubic transform is the sharp case, because ``He_3`` is orthogonal to both
``x`` and ``x**2``, so a partial correlation of zero coexists with strong dependence.

Nonlinear transforms are applied only to parents that are exactly Gaussian -- roots, and
nodes reached only through linear edges. Allowing them to stack produced marginal kurtosis
above 16,000, which would have made Fisher-z PC fail because its normality assumption was
violated rather than because the dependence was nonlinear. Beating a baseline that was
broken for an unrelated reason would prove nothing, so the constraint is a fairness
requirement, not a modelling convenience. It also matches how behavioural models are
specified in practice, where a squared or interaction term is rarely fed into another one.

Every node is scaled to unit population variance. That is not cosmetic: the estimand
divides by ``R_i(empty set)``, so without it a node's ``Theta`` would depend on its
arbitrary marginal scale and no single ``delta`` would mean the same thing twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

DGP_FAMILIES = ("linear_gaussian", "additive_nonlinear")
EDGE_FORMS = ("linear", "quadratic", "cubic", "saturating")

# How much of a node's variance its parents jointly explain, and how many parents share it.
#
# ``realistic`` reflects behavioural networks: a degree-3 node splitting 30-60% across its
# parents leaves individual edges around Theta = 0.1-0.3. That is honest, but it makes the
# coarse resolutions easy in a way that hides the comparison -- at delta = 0.20 roughly 99
# of 105 pairs are already practically absent, so pruning almost everything scores nearly
# perfectly and no method can distinguish itself.
#
# ``strong`` concentrates more variance across fewer parents, putting most edges above 0.20.
# The two truths then nearly coincide at every calibrated delta, which is the only regime
# where a coarse-resolution comparison is informative. Running both is what separates "this
# method resolves too coarsely to be useful here" from "the generator made it look that way".
EDGE_STRENGTHS = {
    "realistic": {"explained": (.30, .60), "max_parents": 3},
    "strong": {"explained": (.60, .85), "max_parents": 2},
}


def node_names(p: int) -> list[str]:
    return [f"v{index:02d}" for index in range(p)]


@dataclass(frozen=True)
class BenchmarkGraph:
    """A DAG in topological order, with the coefficients and forms that generated it."""

    p: int
    parents: tuple[tuple[int, ...], ...]
    coefficients: tuple[tuple[float, ...], ...]
    forms: tuple[tuple[str, ...], ...]
    noise_sd: tuple[float, ...]
    family: str
    edge_strength: str = "realistic"
    scale: tuple[float, ...] = field(default=())

    @property
    def names(self) -> list[str]:
        return node_names(self.p)

    def adjacent_pairs(self) -> set[frozenset[str]]:
        names = self.names
        return {frozenset((names[child], names[parent])) for child, group in enumerate(self.parents) for parent in group}

    def all_pairs(self) -> set[frozenset[str]]:
        names = self.names
        return {frozenset((names[i], names[j])) for i in range(self.p) for j in range(i + 1, self.p)}

    def nonadjacent_pairs(self) -> set[frozenset[str]]:
        return self.all_pairs() - self.adjacent_pairs()

    def moral_only_pairs(self) -> set[frozenset[str]]:
        """Co-parent pairs: non-adjacent in the DAG but adjacent in the moral graph.

        A Gaussian graphical model estimates the moral graph, so EBICglasso *cannot*
        declare these absent however much data it gets -- they carry a nonzero partial
        correlation. Scoring it against DAG adjacency therefore caps its achievable
        true-prune rate, and the cap is reported rather than left to look like poor power.
        """
        names = self.names
        pairs = set()
        for group in self.parents:
            for first in range(len(group)):
                for second in range(first + 1, len(group)):
                    pairs.add(frozenset((names[group[first]], names[group[second]])))
        return pairs - self.adjacent_pairs()

    def markov_blanket(self, index: int) -> set[int]:
        children = [child for child, group in enumerate(self.parents) if index in group]
        blanket = set(self.parents[index]) | set(children)
        for child in children:
            blanket |= set(self.parents[child])
        return blanket - {index}


def _transform(form: str, values: np.ndarray) -> np.ndarray:
    """Edge transforms, each centred and scaled for a standard normal input.

    ``cubic`` is the probabilists' Hermite ``He_3``, orthogonal to ``x`` and ``x**2``. An
    edge carried entirely by it contributes exactly zero partial correlation, which is what
    makes it the case a covariance-based test cannot see.
    """
    if form == "linear":
        return values
    if form == "quadratic":
        return (values**2 - 1) / np.sqrt(2)
    if form == "cubic":
        return (values**3 - 3 * values) / np.sqrt(6)
    if form == "saturating":
        return np.tanh(values) / .6266570686577502  # sd of tanh(N(0,1)); keeps the edge unit-scaled
    raise ValueError(f"unknown edge form: {form}")


def sample_graph(*, p: int = 15, max_degree: int = 3, max_parents: int | None = None, seed: int, family: str = "linear_gaussian", edge_range: tuple[float, float] = (.6, 1.0), edge_strength: str = "realistic") -> BenchmarkGraph:
    """Draw a sparse random DAG whose total degree never exceeds ``max_degree``.

    Candidate pairs are considered in a random order and accepted while both endpoints stay
    under the cap, which satisfies section 13.4's degree constraint exactly rather than in
    expectation. ``edge_range`` is the target edge count as a fraction of the maximum the cap
    allows, so graphs vary in density instead of all arriving at the same saturated shape.

    Filling greedily in topological order instead produced a degenerate family: every draw
    had exactly 21 edges, built as saturated four-node cliques, and **no co-parent pair was
    ever non-adjacent**. That silently removed both colliders-with-unlinked-parents and the
    gap between a DAG and its moral graph -- so the graphical lasso, which can only ever
    estimate the moral graph, would have been handed a benchmark where the two coincide.
    """
    if family not in DGP_FAMILIES:
        raise ValueError(f"unknown dgp family: {family}")
    if edge_strength not in EDGE_STRENGTHS:
        raise ValueError(f"unknown edge strength: {edge_strength}")
    if p < 3:
        raise ValueError("at least three nodes are required")
    profile = EDGE_STRENGTHS[edge_strength]
    max_parents = profile["max_parents"] if max_parents is None else max_parents
    explained_range = profile["explained"]
    generator = np.random.default_rng(seed)
    ceiling = (p * max_degree) // 2
    target = int(generator.integers(max(1, int(ceiling * edge_range[0])), ceiling + 1))
    candidates = [(parent, child) for child in range(p) for parent in range(child)]
    generator.shuffle(candidates)

    degree = [0] * p
    chosen_parents: list[list[int]] = [[] for _ in range(p)]
    accepted = 0
    for parent, child in candidates:
        if accepted >= target:
            break
        if degree[parent] >= max_degree or degree[child] >= max_degree or len(chosen_parents[child]) >= max_parents:
            continue
        chosen_parents[child].append(parent)
        degree[parent] += 1
        degree[child] += 1
        accepted += 1

    gaussian = [True] * p  # a node stays exactly Gaussian while every incoming edge is linear
    parents: list[tuple[int, ...]] = []
    coefficients: list[tuple[float, ...]] = []
    forms: list[tuple[str, ...]] = []
    noise_sd: list[float] = []
    for child in range(p):
        group = sorted(chosen_parents[child])
        # Weights are drawn then renormalised to hit an exact explained fraction, so signal
        # strength is a controlled quantity rather than a by-product of the draw.
        raw = generator.uniform(.4, 1.0, size=len(group)) * generator.choice([-1.0, 1.0], size=len(group))
        explained = float(generator.uniform(*explained_range)) if group else 0.0
        # Only a Gaussian parent may carry a nonlinear edge; see the module docstring.
        edge_forms = tuple(
            str(generator.choice(EDGE_FORMS)) if family == "additive_nonlinear" and gaussian[parent] else "linear"
            for parent in group
        )
        # Gaussianity must propagate: a node fed linearly from a non-Gaussian parent is not
        # Gaussian either, and allowing a cubic onto it would stack transforms again.
        gaussian[child] = all(gaussian[parent] and form == "linear" for parent, form in zip(group, edge_forms))
        parents.append(tuple(group))
        coefficients.append(tuple(float(value) for value in raw))
        forms.append(edge_forms)
        noise_sd.append(explained)  # placeholder; resolved by the scaling pass below
    graph = BenchmarkGraph(p=p, parents=tuple(parents), coefficients=tuple(coefficients), forms=tuple(forms), noise_sd=tuple(noise_sd), family=family, edge_strength=edge_strength)
    return _rescale_to_unit_variance(graph, seed=seed)


def _rescale_to_unit_variance(graph: BenchmarkGraph, *, seed: int, n: int = 60_000) -> BenchmarkGraph:
    """Fix each node's coefficient scale and noise so its population variance is one.

    The scaling constants are derived from a large auxiliary sample keyed to the graph's own
    seed, never from the analysis sample, so the DGP is a fixed population quantity and two
    replications of the same graph at different ``n`` describe the same distribution.
    """
    generator = np.random.default_rng([seed, 0xD6C])
    columns = np.zeros((n, graph.p))
    coefficients: list[tuple[float, ...]] = []
    noise_sd: list[float] = []
    for child in range(graph.p):
        group, weights, forms = graph.parents[child], np.array(graph.coefficients[child]), graph.forms[child]
        explained = graph.noise_sd[child]
        if not group:
            columns[:, child] = generator.normal(size=n)
            coefficients.append(())
            noise_sd.append(1.0)
            continue
        signal = sum(weight * _transform(form, columns[:, parent]) for weight, form, parent in zip(weights, forms, group))
        # Scale the whole parent contribution to the target explained fraction of a unit
        # variance, then let the noise carry the remainder.
        scaled = weights * float(np.sqrt(explained) / max(np.std(signal), 1e-12))
        residual_sd = float(np.sqrt(1 - explained))
        columns[:, child] = sum(weight * _transform(form, columns[:, parent]) for weight, form, parent in zip(scaled, forms, group)) + residual_sd * generator.normal(size=n)
        coefficients.append(tuple(float(value) for value in scaled))
        noise_sd.append(residual_sd)
    return BenchmarkGraph(p=graph.p, parents=graph.parents, coefficients=tuple(coefficients), forms=graph.forms, noise_sd=tuple(noise_sd), family=graph.family, edge_strength=graph.edge_strength)


def generate_sample(graph: BenchmarkGraph, *, n: int, seed: int) -> pd.DataFrame:
    """Draw ``n`` rows from the graph's structural equations."""
    if n < 30:
        raise ValueError("benchmark scenarios require at least 30 rows")
    generator = np.random.default_rng(seed)
    columns = np.zeros((n, graph.p))
    for child in range(graph.p):
        group = graph.parents[child]
        signal = sum(weight * _transform(form, columns[:, parent]) for weight, form, parent in zip(graph.coefficients[child], graph.forms[child], group)) if group else 0.0
        columns[:, child] = signal + graph.noise_sd[child] * generator.normal(size=n)
    return pd.DataFrame(columns, columns=graph.names)


def population_covariance(graph: BenchmarkGraph) -> np.ndarray:
    """Exact population covariance, available only for the linear Gaussian family."""
    if graph.family != "linear_gaussian":
        raise ValueError("an exact covariance exists only for the linear Gaussian family")
    covariance = np.zeros((graph.p, graph.p))
    for child in range(graph.p):
        group, weights = list(graph.parents[child]), np.array(graph.coefficients[child])
        if group:
            covariance[child, :child] = weights @ covariance[np.ix_(group, range(child))]
            covariance[:child, child] = covariance[child, :child]
            covariance[child, child] = float(weights @ covariance[np.ix_(group, group)] @ weights) + graph.noise_sd[child] ** 2
        else:
            covariance[child, child] = graph.noise_sd[child] ** 2
    return covariance


def _conditional_variance(covariance: np.ndarray, target: int, conditioning: list[int]) -> float:
    if not conditioning:
        return float(covariance[target, target])
    block = covariance[np.ix_(conditioning, conditioning)]
    cross = covariance[target, conditioning]
    return float(covariance[target, target] - cross @ np.linalg.solve(block, cross))


def oracle_theta(graph: BenchmarkGraph, target: str, added: str, separator: list[str]) -> float:
    """Exact normalized VIMP for the linear Gaussian family.

    Used to verify that the generated edges really are above ``delta`` -- otherwise a
    "false prune" scored against graphical adjacency could be the method correctly reporting
    a relationship that is practically negligible, which would penalise it for being right.
    """
    covariance = population_covariance(graph)
    index = {name: position for position, name in enumerate(graph.names)}
    conditioning = [index[name] for name in separator]
    reduced = _conditional_variance(covariance, index[target], conditioning)
    expanded = _conditional_variance(covariance, index[target], conditioning + [index[added]])
    return (reduced - expanded) / float(covariance[index[target], index[target]])


def monte_carlo_theta(graph: BenchmarkGraph, target: str, added: str, separator: list[str], *, n: int = 200_000, seed: int = 4409, degree: int = 3) -> float:
    """Large-sample ``Theta`` for families with no closed form.

    The best predictor is approximated by least squares on a degree-``degree`` polynomial
    with interactions. That basis contains every edge transform this module generates, so
    the approximation error comes only from the conditional expectation of an omitted
    parent, which is smooth in at most three variables at this sample size.
    """
    from sklearn.preprocessing import PolynomialFeatures

    sample = generate_sample(graph, n=n, seed=seed)
    outcome = sample[target].to_numpy()

    def risk(features: list[str]) -> float:
        if not features:
            return float(np.var(outcome))
        design = PolynomialFeatures(degree=degree, include_bias=True).fit_transform(sample[features].to_numpy())
        residual = outcome - design @ np.linalg.lstsq(design, outcome, rcond=None)[0]
        return float(np.mean(residual**2))

    return (risk(separator) - risk(separator + [added])) / risk([])


def oracle_edge_theta(graph: BenchmarkGraph, *, conditioning: Literal["parents", "markov_blanket"] = "parents", n: int = 200_000, seed: int = 4409) -> pd.DataFrame:
    """Oracle ``Theta`` for every adjacent pair, conditioned on the rest of its structure.

    This decides whether a pruned adjacency was an error. The generated graphs deliberately
    span a realistic range of edge strengths, so a real edge can carry a ``Theta`` below the
    ``delta`` being tested -- and such an edge *should* be certified, because the estimand is
    practical rather than exact absence. Scoring it as a false prune would penalise the
    method for behaving correctly, so `practical_nonedge_pairs` uses this to relabel.
    """
    exact = graph.family == "linear_gaussian"
    rows = []
    for child, group in enumerate(graph.parents):
        for parent in group:
            for target, added in ((child, parent), (parent, child)):
                context = graph.markov_blanket(target) if conditioning == "markov_blanket" else set(graph.parents[target])
                separator = sorted(graph.names[other] for other in context - {added})
                theta = oracle_theta(graph, graph.names[target], graph.names[added], separator) if exact else monte_carlo_theta(graph, graph.names[target], graph.names[added], separator, n=n, seed=seed)
                rows.append({
                    "target": graph.names[target],
                    "added": graph.names[added],
                    "separator_size": len(separator),
                    "theta": theta,
                    "exact": exact,
                })
    return pd.DataFrame(rows).sort_values(["target", "added"], ignore_index=True) if rows else pd.DataFrame(columns=["target", "added", "separator_size", "theta", "exact"])


def practical_nonedge_pairs(graph: BenchmarkGraph, delta: float, *, edge_theta: pd.DataFrame | None = None, **kwargs: object) -> set[frozenset[str]]:
    """Pairs that are absent *at resolution ``delta``*, which is the estimand under test.

    A non-adjacent pair always qualifies. An adjacent pair qualifies when **both** directions
    carry ``Theta <= delta``, matching the intersection-union test: the certificate requires
    each direction separately to be negligible, so one strong direction keeps the pair.

    Reported alongside graphical adjacency rather than instead of it. Adjacency is what PC
    and FCI target, and relabelling only to this definition would quietly change the
    question to the one this method happens to answer.
    """
    table = oracle_edge_theta(graph, **kwargs) if edge_theta is None else edge_theta  # type: ignore[arg-type]
    weak = set()
    if len(table):
        strongest = table.assign(pair=[frozenset((row.target, row.added)) for row in table.itertuples()]).groupby("pair").theta.max()
        weak = {pair for pair, theta in strongest.items() if theta <= delta}
    return graph.nonadjacent_pairs() | weak


def graph_summary(graph: BenchmarkGraph) -> dict[str, object]:
    degree: dict[str, int] = {name: 0 for name in graph.names}
    for pair in graph.adjacent_pairs():
        for name in pair:
            degree[name] += 1
    return {
        "p": graph.p,
        "family": graph.family,
        "edge_strength": graph.edge_strength,
        "edges": len(graph.adjacent_pairs()),
        "nonedges": len(graph.nonadjacent_pairs()),
        "max_degree": max(degree.values()) if degree else 0,
        "cubic_edges": sum(1 for group in graph.forms for form in group if form == "cubic"),
    }
