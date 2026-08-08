"""What does each learner-library change buy, and what does it cost?

Runs the real cross-fitted estimator. The cubic variant upgrades the polynomial member
from degree 2 to degree 3; the forest variant only changes VimpSpec fields that already
exist. Both are therefore genuine configuration changes, not a parallel implementation.
"""
import math, time, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

OUT = Path(__file__).with_name("library_test_results.parquet")
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures

import renca.vimp.estimate as est_mod
from renca.models import NodeSpec, VimpSpec
from renca.screening import SplitManifest
from renca.vimp import fit_crossfitted_vimp

NODE = NodeSpec(node_id="y", outcome_type="continuous", loss="squared", delta=.05)
SIG = math.sqrt(.05 / .95 * 2)

SHAPES = {
    "linear":   lambda x: x,
    "parabola": lambda x: (x**2 - 1) / math.sqrt(2),
    "cubic":    lambda x: (x**3 - 3 * x) / math.sqrt(6),
    "sin(2x)":  lambda x: np.sin(2 * x) / math.sqrt((1 - math.exp(-8)) / 2),
    "NONEDGE":  None,          # true theta = 0; measures the precision cost
}

CONFIGS = {
    "current  (deg2, 10 trees)":  (2, VimpSpec(forest_trees=10,  forest_max_depth=5,  learner_library_version="v3_nested_blend")),
    "cubic    (deg3, 10 trees)":  (3, VimpSpec(forest_trees=10,  forest_max_depth=5,  learner_library_version="v3_nested_blend")),
    "forest   (deg2, 200 deep)":  (2, VimpSpec(forest_trees=200, forest_max_depth=15, learner_library_version="v3_nested_blend")),
    "both     (deg3, 200 deep)":  (3, VimpSpec(forest_trees=200, forest_max_depth=15, learner_library_version="v3_nested_blend")),
}


def _patched(degree):
    def _fit_predict(name, train, valid, target, features, binary, spec, seed):
        y = train[target].to_numpy()
        if name == "ridge":
            return Ridge(alpha=spec.ridge_alpha).fit(train[features], y).predict(valid[features])
        if name == "quadratic_ridge":
            return make_pipeline(PolynomialFeatures(degree=degree, include_bias=False), Ridge(alpha=spec.ridge_alpha)).fit(train[features], y).predict(valid[features])
        return RandomForestRegressor(n_estimators=spec.forest_trees, max_depth=spec.forest_max_depth, random_state=seed).fit(train[features], y).predict(valid[features])
    return _fit_predict


def man(n=300, k=5):
    p = list(range(n))
    return SplitManifest(schema_version="1.7.0", analysis_id="dddb2c74-2a57-4561-8afc-2c56e086674b", seed=11,
                         selection_fraction=.2, inference_folds=k, sampling_unit="iid", selection_row_positions=[],
                         inference_row_positions=p, inference_fold_by_row_position={r: r % k for r in p},
                         stratification_columns=[], input_order_sha256="f")


def one(a):
    config, shape, seed = a
    degree, spec = CONFIGS[config]
    est_mod._fit_predict = _patched(degree)
    rng = np.random.default_rng(seed)
    z, x, e = rng.normal(size=(3, 300))
    y = z + e if SHAPES[shape] is None else z + SIG * SHAPES[shape](x) + e
    start = time.perf_counter()
    r = fit_crossfitted_vimp(pd.DataFrame({"z": z, "x": x, "y": y}), "y", "x", ["z"], NODE, man(), spec)
    return (config, shape, r.theta_hat, r.se_theta, time.perf_counter() - start)


if __name__ == "__main__":
    items = [(c, s, i) for c in CONFIGS for s in SHAPES for i in range(40)]
    with ProcessPoolExecutor(max_workers=16) as pool:
        rows = list(pool.map(one, items))
    d = pd.DataFrame(rows, columns=["config", "form", "theta", "se", "secs"]).dropna(subset=["theta"])
    d.to_parquet(OUT)  # persist before reporting so a print bug cannot waste the compute

    print("RECOVERY: median theta found, as % of the true 0.05")
    print("%-27s %9s %9s %9s %9s" % ("library", "linear", "parabola", "cubic", "sin(2x)"))
    for c in CONFIGS:
        g = d[d.config == c]
        vals = [100 * g[g.form == s].theta.median() / .05 for s in ("linear", "parabola", "cubic", "sin(2x)")]
        print("%-27s %8.0f%% %8.0f%% %8.0f%% %8.0f%%" % (c, *vals))

    print()
    print("COST: precision on a true nonedge, and runtime")
    base_se = d[(d.config == list(CONFIGS)[0]) & (d.form == "NONEDGE")].se.median()
    base_t = d[d.config == list(CONFIGS)[0]].secs.median()
    print("%-27s %10s %14s %12s %12s" % ("library", "se", "vs current", "secs/run", "vs current"))
    for c in CONFIGS:
        g = d[d.config == c]
        se = g[g.form == "NONEDGE"].se.median(); t = g.secs.median()
        print("%-27s %10.5f %13.0f%% %12.2f %11.1fx" % (c, se, 100 * se / base_se, t, t / base_t))
