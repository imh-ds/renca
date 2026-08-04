"""Generate the deterministic, authorized synthetic Phase-1 pilot dataset."""

from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    rng = np.random.default_rng(20260802)
    n = 375  # The default 20/80 split leaves exactly 300 inference rows.
    common = rng.normal(size=n)
    data = pd.DataFrame(
        {
            "engagement": common + rng.normal(scale=0.7, size=n),
            "satisfaction": 0.65 * common + rng.normal(scale=0.8, size=n),
            "retention_intent": 0.35 * common + rng.normal(scale=0.9, size=n),
        }
    )
    data.to_csv(Path(__file__).with_name("phase1_calibrated_data.csv"), index=False)


if __name__ == "__main__":
    main()
