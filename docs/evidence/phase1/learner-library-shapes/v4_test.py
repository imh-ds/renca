"""v3 vs v4 (cubic member ADDED) vs the flawed degree-2-replaced-by-degree-3 variant."""
import math, time, warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures
from sklearn.ensemble import RandomForestRegressor

import renca.vimp.estimate as est_mod
from renca.models import NodeSpec, VimpSpec
from renca.screening import SplitManifest
from renca.vimp import fit_crossfitted_vimp

OUT = Path(__file__).with_name("v4_test_results.parquet")
NODE = NodeSpec(node_id="y", outcome_type="continuous", loss="squared", delta=.05)
SIG = math.sqrt(.05 / .95 * 2)
SHAPES = {
    "linear":   lambda x: x,
    "parabola": lambda x: (x**2 - 1) / math.sqrt(2),
    "cubic":    lambda x: (x**3 - 3 * x) / math.sqrt(6),
    "sin(2x)":  lambda x: np.sin(2 * x) / math.sqrt((1 - math.exp(-8)) / 2),
    "NONEDGE":  None,
}
V3 = VimpSpec(forest_trees=10, forest_max_depth=5, learner_library_version="v3_nested_blend")
V4 = VimpSpec(forest_trees=10, forest_max_depth=5, learner_library_version="v4_cubic_blend")
CONFIGS = {"v3 current (3 members)": V3, "v4 cubic ADDED (4 members)": V4, "flawed: deg2 REPLACED": V3}

_ORIGINAL = est_mod._fit_predict

def _replaced(name, train, valid, target, features, binary, spec, seed):
    y = train[target].to_numpy()
    if name == "ridge":
        return Ridge(alpha=spec.ridge_alpha).fit(train[features], y).predict(valid[features])
    if name == "quadratic_ridge":
        return make_pipeline(PolynomialFeatures(degree=3, include_bias=False), Ridge(alpha=spec.ridge_alpha)).fit(train[features], y).predict(valid[features])
    return RandomForestRegressor(n_estimators=spec.forest_trees, max_depth=spec.forest_max_depth, random_state=seed).fit(train[features], y).predict(valid[features])

def man(n=300, k=5):
    p = list(range(n))
    return SplitManifest(schema_version="1.7.0", analysis_id="dddb2c74-2a57-4561-8afc-2c56e086674b", seed=11,
                         selection_fraction=.2, inference_folds=k, sampling_unit="iid", selection_row_positions=[],
                         inference_row_positions=p, inference_fold_by_row_position={r: r % k for r in p},
                         stratification_columns=[], input_order_sha256="f")

def one(a):
    config, form, seed = a
    est_mod._fit_predict = _replaced if config.startswith("flawed") else _ORIGINAL
    rng = np.random.default_rng(seed)
    z, x, e = rng.normal(size=(3, 300))
    y = z + e if SHAPES[form] is None else z + SIG * SHAPES[form](x) + e
    start = time.perf_counter()
    r = fit_crossfitted_vimp(pd.DataFrame({"z": z, "x": x, "y": y}), "y", "x", ["z"], NODE, man(), CONFIGS[config])
    weights = {k.replace("blend_weight_", ""): v for k, v in r.nuisance_diagnostic["folds"]["0"]["full_risks"].items() if k.startswith("blend_weight_")}
    return (config, form, r.theta_hat, r.se_theta, time.perf_counter() - start, weights.get("quadratic_ridge"), weights.get("cubic_ridge"))

if __name__ == "__main__":
    items = [(c, f, i) for c in CONFIGS for f in SHAPES for i in range(40)]
    with ProcessPoolExecutor(max_workers=16) as pool:
        rows = list(pool.map(one, items))
    d = pd.DataFrame(rows, columns=["config", "form", "theta", "se", "secs", "w_quad", "w_cubic"]).dropna(subset=["theta"])
    d.to_parquet(OUT)
    print("RECOVERY: median theta as %% of the true 0.05")
    print("%-28s %9s %9s %9s %9s" % ("library", "linear", "parabola", "cubic", "sin(2x)"))
    for c in CONFIGS:
        g = d[d.config == c]
        print("%-28s %8.0f%% %8.0f%% %8.0f%% %8.0f%%" % (c, *[100 * g[g.form == f].theta.median() / .05 for f in ("linear", "parabola", "cubic", "sin(2x)")]))
    print()
    base = d[(d.config == "v3 current (3 members)")]
    bse, bt = base[base.form == "NONEDGE"].se.median(), base.secs.median()
    print("COST")
    print("%-28s %10s %12s %11s %12s" % ("library", "se", "vs v3", "secs/run", "vs v3"))
    for c in CONFIGS:
        g = d[d.config == c]
        print("%-28s %10.5f %11.0f%% %11.2f %11.1fx" % (c, g[g.form == "NONEDGE"].se.median(), 100 * g[g.form == "NONEDGE"].se.median() / bse, g.secs.median(), g.secs.median() / bt))
    print()
    print("v4 blend weights (median), showing it selects per shape:")
    g = d[d.config == "v4 cubic ADDED (4 members)"]
    print("%-12s %14s %14s" % ("shape", "quadratic", "cubic"))
    for f in ("linear", "parabola", "cubic", "sin(2x)"):
        s = g[g.form == f]
        print("%-12s %14.3f %14.3f" % (f, s.w_quad.median(), s.w_cubic.median()))
