import os
import sys
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import log_loss, accuracy_score
import xgboost as xgb

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from model.features.build_features import build_feature_matrix
from model.features.build_features_v2 import get_v2_training_matrix

FEATURES_V1 = [
    "elo_std_pre_a", "elo_mod_pre_a", "elo_std_pre_b", "elo_mod_pre_b",
    "elo_diff_std", "elo_diff_mod",
    "is_title_fight"
]

FEATURES_V2 = [
    "elo_std_pre_a", "elo_mod_pre_a", "elo_std_pre_b", "elo_mod_pre_b",
    "elo_diff_std", "elo_diff_mod",
    "is_title_fight",
    "a_str_acc", "a_str_vol", "a_td_acc", "a_grap_agg", "a_str_def",
    "b_str_acc", "b_str_vol", "b_td_acc", "b_grap_agg", "b_str_def",
    "diff_str_acc", "diff_str_vol", "diff_td_acc", "diff_grap_agg", "diff_str_def"
]

def train(model_version: str = "v1"):
    print(f"Starting training for {model_version.upper()}...")
    
    if model_version == "v2":
        df = get_v2_training_matrix()
        X = df[FEATURES_V2]
    else:
        df = build_feature_matrix()
        X = df[FEATURES_V1]
        
    y = df["label"]

    if model_version == "v2":
        max_depth = 6
        learning_rate = 0.02
    else:
        max_depth = 4
        learning_rate = 0.05

    tscv = TimeSeriesSplit(n_splits=5)
    fold_accuracies, fold_loglosses = [], []

    print("\n--- Training Output with TimeSeriesSplit ---")
    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        m = xgb.XGBClassifier(
            n_estimators=300, 
            max_depth=max_depth, 
            learning_rate=learning_rate,
            subsample=0.8, 
            colsample_bytree=0.8,
            eval_metric="logloss",
            # Ensure safe reproducibility
            random_state=42
        )
        m.fit(X_train, y_train)
        
        preds = m.predict(X_val)
        proba = m.predict_proba(X_val)[:, 1]
        
        fold_accuracies.append(accuracy_score(y_val, preds))
        fold_loglosses.append(log_loss(y_val, proba))
        print(f"Fold {fold+1} - validation accuracy: {fold_accuracies[-1]:.3f}, log-loss: {fold_loglosses[-1]:.3f}")

    mean_acc = sum(fold_accuracies) / len(fold_accuracies)
    mean_logloss = sum(fold_loglosses) / len(fold_loglosses)
    
    print(f"\nMean accuracy: {mean_acc:.3f}")
    print(f"Mean log-loss: {mean_logloss:.3f}")

    print("\nTraining final production surrogate model on full entire dataset...")
    final_model = xgb.XGBClassifier(
        n_estimators=300, max_depth=max_depth, learning_rate=learning_rate,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="logloss", random_state=42
    )
    final_model.fit(X, y)
    
    print("\nFeature Importances:")
    importances = final_model.feature_importances_
    features = X.columns
    for f, imp in sorted(zip(features, importances), key=lambda x: x[1], reverse=True):
        print(f"{f}: {imp:.4f}")
    
    artifact_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "artifacts")
    os.makedirs(artifact_dir, exist_ok=True)
    out_path = os.path.join(artifact_dir, f"xgb_{model_version}.json")
    
    final_model.save_model(out_path)
    print(f"Algorithm successfully compressed and saved: {out_path}")
    return final_model

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train UFC prediction model")
    parser.add_argument("--model-version", default="v1", help="Model version label (default: v1)")
    args = parser.parse_args()
    train(model_version=args.model_version)
