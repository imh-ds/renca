"""Structural baselines for the specification section 13.4 comparative gate.

PC, FCI and GES come from `causal-learn`, because specification section 21.1 requires
established implementations and their native graph outputs rather than reimplementations.
EBICglasso is implemented here -- both the graphical lasso itself and the selection rule of
Foygel and Drton (2010) as `qgraph::EBICglasso` applies it -- because no maintained Python
package provides it and `sklearn`'s graphical lasso does not return exact zeros, which the
criterion needs in order to count edges. See `graphical_lasso_precision`.

Every adapter returns the same thing: the set of **adjacent** pairs. What the comparison
needs is the complement -- which pairs a method declares absent -- and reducing each method
to its adjacency set is what makes an orientation-producing algorithm, a partial ancestral
graph, and a regularised precision matrix scoreable on one axis.

Two asymmetries are load-bearing and are the reason this comparison is not a like-for-like
race, so they are stated here rather than left to the write-up.

First, **these baselines declare absence by failing to reject**. An absent PC edge means no
evidence of association survived a conditional-independence test; an absent EBICglasso edge
means a penalty shrank a partial correlation to zero. Neither is evidence of absence, and
neither carries an error guarantee in that direction: at small ``n`` both prune more, not
less. The present method inverts the null and pays for it, so it will always prune less at
matched error. Reporting only "pruned fraction" would therefore be meaningless.

Second, **their estimand is exact conditional independence; ours is practical**. A true
edge weak enough to fall under ``delta`` should be pruned by the present method, yet counts
as a false prune against graphical adjacency. `dgp.practical_nonedge_pairs` relabels those
edges from the oracle so the penalty is measured rather than assumed away, and applies the
same relabel to these baselines so the comparison stays symmetric.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

# Section 13.4 requires the baselines to run under "the same candidate conditioning-size
# limit" as the method, whose `ScreeningSpec.max_separator_size` is capped at 3.
MAX_CONDITIONING_SIZE = 3
STRUCTURAL_METHODS = ("pc", "conservative_pc", "fci", "ges", "ebicglasso")


def _pairs_from_matrix(names: list[str], matrix: np.ndarray) -> set[frozenset[str]]:
    """Adjacency from a causal-learn graph matrix, ignoring every endpoint mark."""
    return {
        frozenset((names[i], names[j]))
        for i in range(len(names))
        for j in range(i + 1, len(names))
        if matrix[i, j] != 0 or matrix[j, i] != 0
    }


def pc_adjacency(data: pd.DataFrame, *, alpha: float = .05, max_k: int = MAX_CONDITIONING_SIZE, indep_test: str = "fisherz", conservative: bool = False) -> set[frozenset[str]]:
    """PC skeleton. ``conservative`` selects the conservative collider rule.

    Conservative PC changes only how unshielded triples are oriented, never which edges the
    adjacency search removes, so its adjacency set is identical to PC's by construction.
    It is exposed anyway because specification section 41 names it, and a test asserts the
    identity rather than leaving a reader to assume it.
    """
    from causallearn.search.ConstraintBased.PC import pc

    names = list(data.columns)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        graph = pc(data.to_numpy(), alpha=alpha, indep_test=indep_test, stable=True, uc_rule=2 if conservative else 0, show_progress=False, node_names=names, max_k=max_k)
    return _pairs_from_matrix(names, graph.G.graph)


def fci_adjacency(data: pd.DataFrame, *, alpha: float = .05, max_k: int = MAX_CONDITIONING_SIZE, indep_test: str = "fisherz") -> set[frozenset[str]]:
    """FCI skeleton, which removes edges PC keeps by also conditioning on Possible-D-SEP."""
    from causallearn.search.ConstraintBased.FCI import fci

    names = list(data.columns)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        graph, _ = fci(data.to_numpy(), independence_test_method=indep_test, alpha=alpha, depth=max_k, show_progress=False, verbose=False, node_names=names)
    return _pairs_from_matrix(names, graph.graph)


def ges_adjacency(data: pd.DataFrame, *, penalty: float = 1.0) -> set[frozenset[str]]:
    """GES adjacency under the BIC score. ``penalty`` scales the BIC complexity term."""
    from causallearn.search.ScoreBased.GES import ges

    names = list(data.columns)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = ges(data.to_numpy(), score_func="local_score_BIC", parameters={"lambda_value": penalty}, node_names=names)
    return _pairs_from_matrix(names, result["G"].graph)


def graphical_lasso_precision(covariance: np.ndarray, penalty: float, *, max_iter: int = 100, tol: float = 1e-5) -> np.ndarray:
    """Blockwise coordinate-descent graphical lasso (Friedman, Hastie and Tibshirani, 2008).

    Written out rather than taken from `sklearn.covariance.graphical_lasso` because that
    implementation does not return exact zeros: on a three-node chain at n=4,000 its
    off-diagonal precision entries stayed nonzero at every penalty on the path, so counting
    edges by ``|K_ij| > 0`` overcounted and EBIC selected an almost unpenalised, fully dense
    graph. Model selection here depends on the support being exactly identified, so the
    lasso subproblem must be solved by something that thresholds -- which is what the
    published algorithm does and what `sklearn.linear_model.Lasso` provides.
    """
    from sklearn.linear_model import Lasso

    p = covariance.shape[0]
    if penalty <= 0:
        return np.linalg.pinv(covariance)
    work = covariance + penalty * np.eye(p)
    betas = np.zeros((p, p))
    solver = Lasso(alpha=penalty / max(p - 1, 1), fit_intercept=False, max_iter=2000, tol=1e-6)
    for _ in range(max_iter):
        previous = work.copy()
        for column in range(p):
            rest = [index for index in range(p) if index != column]
            block = work[np.ix_(rest, rest)]
            # W11^{1/2} and its inverse turn the quadratic subproblem into a lasso fit.
            values, vectors = np.linalg.eigh(block)
            values = np.clip(values, 1e-10, None)
            root = vectors @ np.diag(np.sqrt(values)) @ vectors.T
            inverse_root = vectors @ np.diag(1 / np.sqrt(values)) @ vectors.T
            beta = solver.fit(root, inverse_root @ covariance[rest, column]).coef_
            betas[rest, column] = beta
            work[rest, column] = work[column, rest] = block @ beta
        if np.abs(work - previous).max() < tol:
            break
    precision = np.zeros((p, p))
    for column in range(p):
        rest = [index for index in range(p) if index != column]
        beta = betas[rest, column]
        precision[column, column] = 1 / max(work[column, column] - float(work[rest, column] @ beta), 1e-12)
        precision[rest, column] = -beta * precision[column, column]
    # The two triangles are computed independently, so symmetrise rather than assume.
    return (precision + precision.T) / 2


def constrained_mle_precision(covariance: np.ndarray, support: np.ndarray, *, max_iter: int = 100, tol: float = 1e-6) -> np.ndarray:
    """Unpenalised Gaussian graphical model MLE with ``precision[i, j] = 0`` off ``support``.

    Same blockwise iteration as the lasso fit, with the L1 subproblem replaced by ordinary
    least squares restricted to each node's neighbours.
    """
    p = covariance.shape[0]
    work = covariance.copy()
    betas = np.zeros((p, p))
    for _ in range(max_iter):
        previous = work.copy()
        for column in range(p):
            rest = [index for index in range(p) if index != column]
            neighbours = [position for position, index in enumerate(rest) if support[index, column]]
            beta = np.zeros(len(rest))
            if neighbours:
                block = work[np.ix_(rest, rest)][np.ix_(neighbours, neighbours)]
                target = covariance[rest, column][neighbours]
                beta[neighbours] = np.linalg.solve(block + 1e-10 * np.eye(len(neighbours)), target)
            betas[rest, column] = beta
            work[rest, column] = work[column, rest] = work[np.ix_(rest, rest)] @ beta
        if np.abs(work - previous).max() < tol:
            break
    precision = np.zeros((p, p))
    for column in range(p):
        rest = [index for index in range(p) if index != column]
        beta = betas[rest, column]
        precision[column, column] = 1 / max(work[column, column] - float(work[rest, column] @ beta), 1e-12)
        precision[rest, column] = -beta * precision[column, column]
    return (precision + precision.T) / 2


def glasso_path(correlation: np.ndarray, *, path_length: int = 100, ratio: float = .01, refit: bool = True) -> list[tuple[float, np.ndarray, int, float]]:
    """Fit the penalty path once: ``(penalty, precision, edges, log-likelihood)`` per point.

    Log-spaced from ``max|S_offdiag|`` down to ``ratio`` of it, as `qgraph` does. The path
    does not depend on ``gamma``, so it is computed once and scored for every ``gamma``.

    ``refit`` re-estimates each selected support by unpenalised maximum likelihood before
    scoring it, which is how Foygel and Drton define the criterion. It matters: scored on
    the penalised fit instead, the likelihood keeps improving as the penalty falls simply
    because the surviving edges are shrunk less, so EBIC decreases monotonically to the end
    of the path and selects a near-dense graph -- on a ten-node DAG at n=4,000 it chose 35
    edges against a true moral graph of 20. That is a comparison of shrinkage levels, not of
    models, and it would have handed this study a strawman baseline.
    """
    p = correlation.shape[0]
    upper = float(np.max(np.abs(correlation - np.eye(p))))
    if upper <= 0:
        return []
    points = []
    for penalty in np.geomspace(upper, upper * ratio, path_length):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                precision = graphical_lasso_precision(correlation, float(penalty))
                if refit:
                    support = np.abs(precision) > 0
                    np.fill_diagonal(support, False)
                    precision = constrained_mle_precision(correlation, support)
                    precision[~(support | np.eye(p, dtype=bool))] = 0.0
        except (FloatingPointError, ValueError, np.linalg.LinAlgError):
            continue
        sign, logdet = np.linalg.slogdet(precision)
        if sign <= 0:
            continue
        edges = int((np.abs(np.triu(precision, 1)) > 0).sum())
        points.append((float(penalty), precision, edges, float(logdet - np.trace(correlation @ precision))))
    return points


def ebic_glasso_path(correlation: np.ndarray, n: int, *, gamma: float = .5, path_length: int = 100, ratio: float = .01, points: list[tuple[float, np.ndarray, int, float]] | None = None) -> tuple[np.ndarray, float, pd.DataFrame]:
    """Select a graphical lasso penalty by EBIC and return the chosen precision matrix.

    ``EBIC = -2L + E*log(n) + 4*gamma*E*log(p)`` with ``L = (n/2)*(logdet(K) - trace(S K))``,
    following Foygel and Drton (2010). ``gamma = 0.5`` is the psychological-network default;
    ``gamma = 0`` reduces the criterion to ordinary BIC.
    """
    p = correlation.shape[0]
    points = glasso_path(correlation, path_length=path_length, ratio=ratio) if points is None else points
    if not points:
        return np.eye(p), 0.0, pd.DataFrame(columns=["penalty", "edges", "ebic"])
    rows, best, best_precision, best_penalty = [], np.inf, np.eye(p), points[0][0]
    for penalty, precision, edges, likelihood in points:
        criterion = -n * likelihood + edges * np.log(n) + 4 * gamma * edges * np.log(p)
        rows.append({"penalty": penalty, "edges": edges, "ebic": float(criterion)})
        if criterion < best:
            best, best_precision, best_penalty = criterion, precision, penalty
    return best_precision, best_penalty, pd.DataFrame(rows)


def _adjacency_from_precision(names: list[str], precision: np.ndarray) -> set[frozenset[str]]:
    return {
        frozenset((names[i], names[j]))
        for i in range(len(names))
        for j in range(i + 1, len(names))
        if precision[i, j] != 0
    }


def ebicglasso_adjacency(data: pd.DataFrame, *, gamma: float = .5, path_length: int = 100) -> set[frozenset[str]]:
    """Adjacency of the EBIC-selected Gaussian graphical model.

    Fitted to the correlation matrix, as `qgraph` does, so the result does not depend on the
    arbitrary scale of each variable.
    """
    correlation = np.corrcoef(data.to_numpy(), rowvar=False)
    precision, _, _ = ebic_glasso_path(correlation, len(data), gamma=gamma, path_length=path_length)
    return _adjacency_from_precision(list(data.columns), precision)


def ebicglasso_adjacency_by_gamma(data: pd.DataFrame, gammas: list[float], *, path_length: int = 100) -> dict[float, set[frozenset[str]]]:
    """Every ``gamma`` off one penalty path, which is the expensive part."""
    correlation = np.corrcoef(data.to_numpy(), rowvar=False)
    points = glasso_path(correlation, path_length=path_length)
    return {
        gamma: _adjacency_from_precision(list(data.columns), ebic_glasso_path(correlation, len(data), gamma=gamma, points=points)[0])
        for gamma in gammas
    }


def structural_adjacency(method: str, data: pd.DataFrame, *, setting: float, indep_test: str = "fisherz", max_k: int = MAX_CONDITIONING_SIZE) -> set[frozenset[str]]:
    """Dispatch to a baseline with its one tunable knob, so a study can trace its curve.

    ``setting`` is the test level for the constraint-based methods, the BIC penalty for GES,
    and the EBIC ``gamma`` for the graphical lasso. Sweeping it is what turns each baseline
    from a point into the false-prune/true-prune trade-off section 13.4 asks to compare.
    """
    if method == "pc":
        return pc_adjacency(data, alpha=setting, max_k=max_k, indep_test=indep_test)
    if method == "conservative_pc":
        return pc_adjacency(data, alpha=setting, max_k=max_k, indep_test=indep_test, conservative=True)
    if method == "fci":
        return fci_adjacency(data, alpha=setting, max_k=max_k, indep_test=indep_test)
    if method == "ges":
        return ges_adjacency(data, penalty=setting)
    if method == "ebicglasso":
        return ebicglasso_adjacency(data, gamma=setting)
    raise ValueError(f"unknown structural baseline: {method}")
