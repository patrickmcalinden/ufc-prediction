# Experiments

One file per idea, numbered in order (`001_reach_height.py`,
`002_...`). Never renumber or reuse — the number is how
`model/EXPERIMENTS.md` refers to it.

```
python -m pipeline.experiment experiments/002_my_idea.py          # run
python -m pipeline.experiment experiments/002_my_idea.py --log    # run + append to the log
```

Nothing is written to the database or `model/artifacts/`.

## Template

```python
"""What this tests and why it might work."""

import pandas as pd

from pipeline.history import FEATURES_V3, add_pair

NAME = "my_idea"
HYPOTHESIS = "One sentence: the signal and why it should predict fights."
BASE = "v3"   # registered model to compare against (feature_set="v3")


def add_features(df, engine):
    """df is build_v3_frame(): one row per non-cancelled fight, completed
    and upcoming, with fighter_a_id / fighter_b_id / fight_date / label.
    Add columns using data from BEFORE each fight_date only."""
    stance = pd.read_sql_query("SELECT fighter_id, stance FROM fighters", engine).set_index("fighter_id").stance

    def southpaw(ids):
        s = ids.map(stance)
        return (s == "Southpaw").astype(float).where(s.notna())   # unknown stays NaN, not 0

    add_pair(df, "southpaw", southpaw(df.fighter_a_id), southpaw(df.fighter_b_id))
    return df   # adds a_southpaw, b_southpaw, d_southpaw


CANDIDATES = {
    "with_stance": {"features": FEATURES_V3 + ["a_southpaw", "b_southpaw", "d_southpaw"]},
    # "shallower": {"features": FEATURES_V3, "params": {"max_depth": 2}},
}
```

`params` overrides any `ModelConfig` field (`n_estimators`, `max_depth`,
`learning_rate`, `subsample`, `colsample_bytree`, `min_child_weight`).

For a single candidate, `FEATURES = [...]` (and optionally `PARAMS = {...}`)
works instead of `CANDIDATES`.

## Reading the output

```
model               acc  logloss   brier  Δlogloss  95% CI             yrs won  verdict
v3 (base)         0.613   0.6554  0.2318
masked            0.611   0.6547  0.2315   -0.0007  [-0.0028, +0.0013]   4/6    inconclusive
```

- **Δlogloss** — candidate minus base, averaged over the same fights.
  Negative is better.
- **95% CI** — paired bootstrap over fights. If it straddles 0, there's no
  evidence of a difference.
- **yrs won** — test years where the candidate's log loss beat the base.
- **verdict** — `better` (CI below 0 and ≥ 2/3 of years), `worse`,
  `inconclusive`, or `LEAK` (a feature's coverage predicts the winner —
  fix before anything else).
