"""How well does the estimator recover each SHAPE of relationship, at true theta = 0.05?"""
import warnings, math, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from concurrent.futures import ProcessPoolExecutor
from renca.models import NodeSpec, VimpSpec
from renca.screening import SplitManifest
from renca.vimp import fit_crossfitted_vimp

SPEC = VimpSpec(forest_trees=10, learner_library_version="v3_nested_blend")
NODE = NodeSpec(node_id="y", outcome_type="continuous", loss="squared", delta=.05)

def man(n, k=5):
    p = list(range(n))
    return SplitManifest(schema_version="1.7.0", analysis_id="dddb2c74-2a57-4561-8afc-2c56e086674b", seed=11,
                         selection_fraction=.2, inference_folds=k, sampling_unit="iid", selection_row_positions=[],
                         inference_row_positions=p, inference_fold_by_row_position={r: r % k for r in p},
                         stratification_columns=[], input_order_sha256="f")

# every shape standardised to mean 0, variance 1 so true theta is identical across them
SHAPES = {
    "linear  (no bend)":        (lambda x: x, 0),
    "exponential decay":        (lambda x: (np.exp(-x) - math.exp(.5)) / math.sqrt(math.e * (math.e - 1)), 0),
    "parabola (1 turn)":        (lambda x: (x**2 - 1) / math.sqrt(2), 1),
    "cubic    (2 turns)":       (lambda x: (x**3 - 3 * x) / math.sqrt(6), 2),
    "sin(1x)  (2 turns)":       (lambda x: np.sin(x) / math.sqrt((1 - math.exp(-2)) / 2), 2),
    "sin(2x)  (4 turns)":       (lambda x: np.sin(2 * x) / math.sqrt((1 - math.exp(-8)) / 2), 4),
    "sin(4x)  (8 turns)":       (lambda x: np.sin(4 * x) / math.sqrt((1 - math.exp(-32)) / 2), 8),
}

def one(a):
    name, seed = a
    fn, _ = SHAPES[name]
    sig = math.sqrt(.05 / .95 * 2)
    rng = np.random.default_rng(seed)
    z, x, e = rng.normal(size=(3, 300))
    y = z + sig * fn(x) + e
    est = fit_crossfitted_vimp(pd.DataFrame({"z": z, "x": x, "y": y}), "y", "x", ["z"], NODE, man(300), SPEC)
    return (name, est.theta_hat, est.se_theta, (est.theta_hat - .05) / est.se_theta if est.se_theta else None)

if __name__ == "__main__":
    items = [(n, s) for n in SHAPES for s in range(150)]
    with ProcessPoolExecutor(max_workers=16) as pool:
        rows = list(pool.map(one, items))
    d = pd.DataFrame(rows, columns=["shape", "theta", "se", "stud"]).dropna()
    print("True theta = 0.05 for EVERY shape. Current safety threshold is -5.14.")
    print("%-22s %6s %12s %14s %16s" % ("shape", "turns", "theta found", "% of truth seen", "threshold needed"))
    for name in SHAPES:
        g = d[d.shape_ if False else d["shape"] == name]
        print("%-22s %6d %12.4f %14.0f%% %16.2f" % (name, SHAPES[name][1], g.theta.median(), 100 * g.theta.median() / .05, g.stud.quantile(.04)))
