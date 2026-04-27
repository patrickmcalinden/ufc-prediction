# SKILL: XGBoost Model Training & Evaluation

## Purpose
Build, train, evaluate, and serialize the XGBoost binary classifier that predicts UFC fight outcomes and outputs win probabilities.

## Files It Owns
```
model/
├── features/
│   └── build_features.py   # Assembles the feature matrix from the database
├── training/
│   └── train.py            # XGBoost training + cross-validation
├── evaluation/
│   └── evaluate.py         # Accuracy, log-loss, calibration
└── artifacts/
    └── xgb_v1.json         # Saved model (versioned, never overwrite)
```

## Key Libraries
- `xgboost` — the model
- `pandas` — feature matrix assembly
- `scikit-learn` — TimeSeriesSplit, metrics, preprocessing
- `joblib` — optional secondary serialization
- `matplotlib` — calibration curve visualization (local only, not served)

## Patterns

### Feature Matrix Assembly
```python
# One row = one fight from fighter_a's perspective
# Both fighters appear as fighter_a across the full dataset (flip rows)
def build_feature_matrix(db_session) -> pd.DataFrame:
    query = """
    SELECT
        f.fight_id,
        f.fight_date,
        f.fighter_a_id,
        f.fighter_b_id,
        f.winner_id,
        ea.elo_standard_pre   AS elo_std_pre_a,
        ea.elo_modified_pre   AS elo_mod_pre_a,
        eb.elo_standard_pre   AS elo_std_pre_b,
        eb.elo_modified_pre   AS elo_mod_pre_b,
        fa.record_wins        AS wins_a,
        fa.record_losses      AS losses_a,
        fb.record_wins        AS wins_b,
        fb.record_losses      AS losses_b,
        f.is_title_fight
    FROM fights f
    JOIN elo_ratings ea ON ea.fight_id = f.fight_id AND ea.fighter_id = f.fighter_a_id
    JOIN elo_ratings eb ON eb.fight_id = f.fight_id AND eb.fighter_id = f.fighter_b_id
    JOIN fighters fa ON fa.fighter_id = f.fighter_a_id
    JOIN fighters fb ON fb.fighter_id = f.fighter_b_id
    WHERE f.winner_id IS NOT NULL
    ORDER BY f.fight_date ASC
    """
    df = pd.read_sql(query, db_session.bind)
    df["elo_diff_std"] = df["elo_std_pre_a"] - df["elo_std_pre_b"]
    df["elo_diff_mod"] = df["elo_mod_pre_a"] - df["elo_mod_pre_b"]
    df["label"] = (df["winner_id"] == df["fighter_a_id"]).astype(int)
    # Assert no NaN before returning
    assert df.isnull().sum().sum() == 0, "Feature matrix contains NaN values"
    return df
```

### Training with TimeSeriesSplit
```python
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import log_loss, accuracy_score
import xgboost as xgb

FEATURES = [
    "elo_std_pre_a", "elo_mod_pre_a", "elo_std_pre_b", "elo_mod_pre_b",
    "elo_diff_std", "elo_diff_mod",
    "wins_a", "losses_a", "wins_b", "losses_b",
    "is_title_fight"
]

def train(df: pd.DataFrame, model_version: str = "v1") -> xgb.XGBClassifier:
    X = df[FEATURES]
    y = df["label"]

    tscv = TimeSeriesSplit(n_splits=5)
    fold_accuracies, fold_loglosses = [], []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        m = xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05,
                               subsample=0.8, colsample_bytree=0.8,
                               eval_metric="logloss", verbosity=0)
        m.fit(X_train, y_train)
        preds = m.predict(X_val)
        proba = m.predict_proba(X_val)[:, 1]
        fold_accuracies.append(accuracy_score(y_val, preds))
        fold_loglosses.append(log_loss(y_val, proba))
        print(f"Fold {fold+1} — accuracy: {fold_accuracies[-1]:.3f}, log-loss: {fold_loglosses[-1]:.3f}")

    print(f"Mean accuracy: {sum(fold_accuracies)/len(fold_accuracies):.3f}")
    print(f"Mean log-loss: {sum(fold_loglosses)/len(fold_loglosses):.3f}")

    # Final fit on all data
    final_model = xgb.XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05,
                                     subsample=0.8, colsample_bytree=0.8,
                                     eval_metric="logloss", verbosity=0)
    final_model.fit(X, y)
    final_model.save_model(f"model/artifacts/xgb_{model_version}.json")
    print(f"Model saved: model/artifacts/xgb_{model_version}.json")
    return final_model
```

### Prediction (used by the API)
```python
def predict_fight(
    model: xgb.XGBClassifier,
    features: dict
) -> tuple[int, float]:
    """Returns (predicted_label, win_probability_for_fighter_a)"""
    import numpy as np
    X = np.array([[features[f] for f in FEATURES]])
    label = int(model.predict(X)[0])
    prob = float(model.predict_proba(X)[0][1])
    return label, prob
```

## Gotchas
- **Never use random KFold.** TimeSeriesSplit is mandatory. Random splits leak future fight outcomes into training.
- The feature matrix NaN assertion will fail if Elo ratings have not been computed for all fights first. Run the Elo pipeline (Phase 3) before training.
- Both fighters must appear as `fighter_a` across the dataset to avoid the model learning a positional bias. The `build_features.py` script should include a step that creates mirrored rows with labels flipped.
- Model artifact filenames must be versioned: `xgb_v1.json`, `xgb_v2.json`. Never overwrite a previous version.
- The `FEATURES` list in `train.py` and `predict_fight()` must be identical and in the same order. Define it once in a shared constants file.

## LLM Instructions
- See spec Section 8 for the full feature list and model design decisions.
- See spec Section 7 for Elo feature derivation.
- Always use `TimeSeriesSplit` — this is non-negotiable. Do not suggest random splits.
- Store the full feature vector used for each prediction in `predictions.features_snapshot` (JSONB column) for debugging.
- When saving a new model version, update `MODEL_ARTIFACT_PATH` in `.env` and `.env.example`.

## Status
NOT STARTED
