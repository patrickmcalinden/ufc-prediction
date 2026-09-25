"""Does a reach / height advantage add signal on top of v3?

reach_cm and height_cm come from fighter profiles and are only ~51-57%
populated, and *which* fighters have them isn't random: when only one
fighter's reach is known, that fighter wins ~44%. So:

  raw     — one-sided missingness kept. Expect the leak check to flag it.
  masked  — both sides blanked when either is missing (history.add_pair
            default). The honest test.
"""

import pandas as pd

from pipeline.history import FEATURES_V3, add_pair

NAME = "reach_height"
HYPOTHESIS = "Reach and height advantage add signal on top of v3."
BASE = "v3"


def add_features(df, engine):
    fx = pd.read_sql_query("SELECT fighter_id, reach_cm, height_cm FROM fighters", engine).set_index("fighter_id")
    for col in ("reach_cm", "height_cm"):
        a = df.fighter_a_id.map(fx[col]).astype(float)
        b = df.fighter_b_id.map(fx[col]).astype(float)
        add_pair(df, f"{col}_raw", a, b, symmetric=False)
        add_pair(df, col, a, b)
    return df


_PHYS = ["reach_cm", "height_cm"]
CANDIDATES = {
    "raw": {"features": FEATURES_V3 + [f"{p}_{c}_raw" for c in _PHYS for p in "abd"]},
    "masked": {"features": FEATURES_V3 + [f"{p}_{c}" for c in _PHYS for p in "abd"]},
    "masked_diff": {"features": FEATURES_V3 + [f"d_{c}" for c in _PHYS]},
}
