"""The section 13.4 gate decision, computed from stated rules rather than read off a plot.

Section 51 requires an explicit ``GO``, ``REDESIGN`` or ``STOP``. Section 13.4 lists the
conditions and section 44 criterion 3 gives the matching falsification. Both are prose, so
the thresholds below are an operationalisation; they are constants with reasons attached so
a reader can disagree with a number without having to reverse-engineer the decision.

The comparison rule is the part that matters. A method that prunes nothing has a perfect
false-prune rate and is useless, so neither axis means anything alone. An arm is only
credited as better than a baseline when it is better on **both** axes at once -- no more
false prunes and no fewer true prunes -- which is Pareto dominance and needs no exchange
rate between the two kinds of error.

The decision runs on the **practical-at-delta** scoring, because that is the estimand the
certificate makes a claim about, and it is applied identically to the baselines. The
graphical scoring is carried on every record so a reader can see both, and a verdict that
flips between them is reported rather than resolved silently -- if the answer depends on
which truth you accept, that is the finding.
"""

from __future__ import annotations

import pandas as pd

# Pruning less than this fraction of true nonedges is not "a useful fraction" in any
# reading of section 13.4: the output would be almost entirely unresolved.
USEFUL_PRUNE_FLOOR = .10
# A false-prune advantage smaller than this is not worth calling material at the
# replication counts these studies run at.
MATERIAL_MARGIN = .01
# Section 44 criterion 3 falsifies the programme if the method "cannot prune nearly as many
# true nonedges as PC/FCI while reducing false prunes". "Nearly as many" is operationalised
# as reaching at least this share of the baseline's pruning rate -- so a method that prunes
# 85% where PC prunes 100%, at a far lower error, is not falsified by it.
NEARLY_AS_MANY = .80
# Section 13.4 also requires that "learner failures do not dominate the results".
ABSTENTION_CEILING = .10


def _rates(row: pd.Series, scoring: str) -> tuple[float, float]:
    prefix = "practical_" if scoring == "practical" else ""
    return float(row[f"{prefix}false_prune_rate"]), float(row[f"{prefix}true_prune_rate"])


def _arm(summary: pd.DataFrame, method: str) -> pd.DataFrame:
    return summary[summary.method == method]


def dominated_baselines(summary: pd.DataFrame, renca_row: pd.Series, *, scoring: str = "practical") -> list[dict[str, object]]:
    """Baseline arms this method beats on both axes at once.

    Pareto dominance: no more false prunes, and no fewer true prunes. The margin applies to
    the false-prune axis, which is the one the certificate makes a claim about.
    """
    renca_false, renca_true = _rates(renca_row, scoring)
    dominated = []
    for _, row in summary[summary.method != "renca"].iterrows():
        false_rate, true_rate = _rates(row, scoring)
        if renca_false <= false_rate - MATERIAL_MARGIN and renca_true >= true_rate:
            dominated.append({
                "method": row.method,
                "setting": float(row.setting),
                "baseline_false_prune_rate": false_rate,
                "baseline_true_prune_rate": true_rate,
            })
    return dominated


def spec_criterion_baselines(summary: pd.DataFrame, renca_row: pd.Series, *, scoring: str = "practical") -> list[dict[str, object]]:
    """Baselines beaten on section 44 criterion 3's own terms.

    Strict Pareto dominance is the cleaner claim but is stricter than the specification.
    Criterion 3 falsifies the programme only when the method *both* prunes far fewer true
    nonedges *and* fails to reduce false prunes; trading a slice of pruning power for a much
    lower error rate is the intended behaviour, not a failure. This reports the arms where
    that trade is made: nearly as many true nonedges, materially fewer false prunes.
    """
    renca_false, renca_true = _rates(renca_row, scoring)
    beaten = []
    for _, row in summary[summary.method != "renca"].iterrows():
        false_rate, true_rate = _rates(row, scoring)
        if renca_true >= NEARLY_AS_MANY * true_rate and renca_false <= false_rate - MATERIAL_MARGIN:
            beaten.append({
                "method": row.method,
                "setting": float(row.setting),
                "baseline_false_prune_rate": false_rate,
                "baseline_true_prune_rate": true_rate,
                "pruning_retained": float(renca_true / true_rate) if true_rate else None,
                "false_prune_reduction": float(false_rate - renca_false),
            })
    return beaten


def matched_power_comparison(summary: pd.DataFrame, renca_row: pd.Series, *, scoring: str = "practical") -> dict[str, object]:
    """Compare against the best baseline arm that prunes at least as much as this method.

    This is the fair reading of section 44 criterion 3. A baseline tuned to prune far more
    will also false-prune more, and comparing against it would flatter the method; the
    question is whether, at matched pruning power, its false-prune rate is lower.
    """
    renca_false, renca_true = _rates(renca_row, scoring)
    baselines = summary[summary.method != "renca"]
    rates = [(_rates(row, scoring), row) for _, row in baselines.iterrows()]
    candidates = [(pair, row) for pair, row in rates if pair[1] >= renca_true]
    if not candidates:
        return {"exists": False, "note": "no baseline arm pruned as many true nonedges as this method"}
    (best_false, best_true), best = min(candidates, key=lambda item: item[0][0])
    return {
        "exists": True,
        "method": str(best.method),
        "setting": float(best.setting),
        "baseline_false_prune_rate": best_false,
        "baseline_true_prune_rate": best_true,
        "renca_is_better": bool(renca_false < best_false),
    }


def best_baseline_pruning(summary: pd.DataFrame, *, scoring: str = "practical") -> dict[str, object]:
    """The most true nonedges each baseline pruned, at any setting."""
    column = "practical_true_prune_rate" if scoring == "practical" else "true_prune_rate"
    return {
        str(method): float(group[column].max())
        for method, group in summary[summary.method != "renca"].groupby("method")
    }


def evaluate_region(summary: pd.DataFrame, *, alpha: float = .05, scoring: str = "practical") -> list[dict[str, object]]:
    """Assess every (family, n, delta) cell against the section 13.4 conditions.

    Cells are keyed by ``reference_delta`` so each baseline arm is compared against the
    method at the same resolution the baseline was relabelled for.
    """
    assessments = []
    keys = [name for name in ("family", "edge_strength", "n", "reference_delta") if name in summary]
    for key, cell in summary.groupby(keys):
        labels = dict(zip(keys, key))
        for _, renca_row in _arm(cell, "renca").iterrows():
            false_rate, true_rate = _rates(renca_row, scoring)
            dominated = dominated_baselines(cell, renca_row, scoring=scoring)
            spec_beaten = spec_criterion_baselines(cell, renca_row, scoring=scoring)
            prefix = "practical_" if scoring == "practical" else ""
            upper = float(renca_row[f"{prefix}familywise_upper_bound"])
            assessments.append({
                "family": labels["family"],
                "edge_strength": labels.get("edge_strength", "realistic"),
                "n": int(labels["n"]),
                "delta": float(renca_row.setting),
                "scoring": scoring,
                "false_prune_rate": false_rate,
                "true_prune_rate": true_rate,
                "graphical_false_prune_rate": float(renca_row.false_prune_rate),
                "graphical_true_prune_rate": float(renca_row.true_prune_rate),
                "familywise_error_rate": float(renca_row[f"{prefix}familywise_error_rate"]),
                "familywise_upper_bound": upper,
                "familywise_controlled": bool(upper <= alpha),
                "prunes_a_useful_fraction": bool(true_rate >= USEFUL_PRUNE_FLOOR),
                "dominated_baseline_arms": dominated,
                "dominates_a_baseline": bool(dominated),
                "spec_criterion_baseline_arms": spec_beaten,
                "beats_a_baseline_on_the_spec_criterion": bool(spec_beaten),
                "matched_power_comparison": matched_power_comparison(cell, renca_row, scoring=scoring),
                "best_baseline_true_prune_rate": best_baseline_pruning(cell, scoring=scoring),
            })
    return assessments


def _decide(regions: list[dict[str, object]], *, alpha: float) -> tuple[str, str, list[dict[str, object]]]:
    """Section 13.4's conditions, taken in the order that makes each failure diagnostic."""
    passing = [
        region for region in regions
        if region["familywise_controlled"] and region["prunes_a_useful_fraction"] and region["beats_a_baseline_on_the_spec_criterion"]
    ]
    controlled = [region for region in regions if region["familywise_controlled"]]
    if not controlled:
        return "STOP", "familywise false pruning exceeded alpha in every region, which is section 44 criterion 1", passing
    if passing:
        dominating = sum(1 for region in passing if region["dominates_a_baseline"])
        strength = f"{dominating} of them by strict Pareto dominance" if dominating else "none by strict Pareto dominance, all by the weaker section 44 criterion 3 trade"
        return "GO", f"{len(passing)} of {len(regions)} regions control familywise error, prune a useful fraction, and beat a baseline; {strength}", passing
    if any(region["prunes_a_useful_fraction"] for region in controlled):
        return "REDESIGN", "error is controlled and pruning is useful, but no region prunes nearly as many true nonedges as a baseline while reducing false prunes, which is section 44 criterion 3", passing
    return "REDESIGN", f"error is controlled but no region pruned {USEFUL_PRUNE_FLOOR:.0%} of true nonedges, so the output is mostly unresolved", passing


def gate_verdict(summary: pd.DataFrame, *, alpha: float = .05) -> dict[str, object]:
    """Turn the per-cell assessments into one GO / REDESIGN / STOP decision.

    ``GO`` needs a single region where every condition holds at once -- section 13.4 says
    "in at least one realistic operating region", not on average across them.

    The decision is taken on the practical-at-delta scoring and *also* computed on the
    graphical scoring. When the two disagree the verdict is reported as contingent rather
    than resolved in this method's favour.
    """
    regions = evaluate_region(summary, alpha=alpha, scoring="practical")
    if not regions:
        return {"verdict": "STOP", "reason": "no arm of this method was scored, so the gate cannot be assessed", "regions": []}
    verdict, reason, passing = _decide(regions, alpha=alpha)
    graphical_regions = evaluate_region(summary, alpha=alpha, scoring="graphical")
    graphical_verdict, graphical_reason, _ = _decide(graphical_regions, alpha=alpha)
    return {
        "verdict": verdict,
        "reason": reason,
        "scoring": "practical_at_delta",
        "graphical_verdict": graphical_verdict,
        "graphical_reason": graphical_reason,
        # A verdict that survives only under one definition of truth is a weaker result than
        # one that holds under both, and saying so is the point of carrying two.
        "verdict_depends_on_scoring": bool(verdict != graphical_verdict),
        "alpha": alpha,
        "useful_prune_floor": USEFUL_PRUNE_FLOOR,
        "material_margin": MATERIAL_MARGIN,
        "nearly_as_many": NEARLY_AS_MANY,
        "regions_assessed": len(regions),
        "regions_passing": len(passing),
        # Section 13.4's fifth condition -- that the threshold is substantively
        # interpretable -- is a judgement about the application, not a measurable quantity.
        "requires_human_signoff": ["practical threshold is substantively interpretable"],
        "regions": regions,
        "graphical_regions": graphical_regions,
    }
