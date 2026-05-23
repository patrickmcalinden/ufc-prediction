"""Train XGBoost on the symmetric feature matrix. Save one canonical artifact.

The artifact filename is fixed (`xgb_current.json`). Each train run also
writes a sidecar `xgb_current.meta.json` recording the timestamp-based
`model_version` and CV metrics, so predict.py can attribute a snapshot
to the exact model that produced it (and so --skip-train remains
idempotent: it reads the existing model_version rather than inventing one).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import xgboost as xgb
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import TimeSeriesSplit

from pipeline.features import FEATURES, build_training_matrix

log = logging.getLogger(__name__)

ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "model" / "artifacts" / "xgb_current.json"
META_PATH = ARTIFACT_PATH.with_suffix(".meta.json")


def current_model_version() -> str:
    """Read model_version from sidecar; fall back to artifact stem."""
    if META_PATH.exists():
        with open(META_PATH, encoding="utf-8") as fh:
            return json.load(fh)["model_version"]
    return ARTIFACT_PATH.stem


def _build_model() -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.02,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
    )


def train() -> dict:
    """Train, save artifact, return summary dict including model_version."""
    df = build_training_matrix()
    X = df[FEATURES]
    y = df["label"]
    log.info("Training matrix shape: %s", X.shape)

    # 5-fold time-series CV for honest metrics
    tscv = TimeSeriesSplit(n_splits=5)
    accs, losses = [], []
    for fold, (tr, va) in enumerate(tscv.split(X), 1):
        m = _build_model()
        m.fit(X.iloc[tr], y.iloc[tr])
        preds = m.predict(X.iloc[va])
        proba = m.predict_proba(X.iloc[va])[:, 1]
        accs.append(accuracy_score(y.iloc[va], preds))
        losses.append(log_loss(y.iloc[va], proba))
        log.info("  fold %d: acc=%.3f logloss=%.3f", fold, accs[-1], losses[-1])
    mean_acc = sum(accs) / len(accs)
    mean_logloss = sum(losses) / len(losses)
    log.info("Mean CV acc=%.3f logloss=%.3f", mean_acc, mean_logloss)

    # Fit production model on all data
    model = _build_model()
    model.fit(X, y)
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(ARTIFACT_PATH)
    log.info("Saved artifact → %s", ARTIFACT_PATH)

    model_version = f"xgb_{datetime.now().strftime('%Y%m%d_%H%M')}"
    meta = {
        "model_version": model_version,
        "model_artifact": ARTIFACT_PATH.name,
        "trained_at": datetime.now().isoformat(),
        "cv_accuracy": mean_acc,
        "cv_logloss": mean_logloss,
        "n_samples": int(X.shape[0]),
        "features": list(FEATURES),
    }
    with open(META_PATH, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    log.info("Saved sidecar → %s", META_PATH)
    return meta


def load() -> xgb.XGBClassifier:
    if not ARTIFACT_PATH.exists():
        raise FileNotFoundError(
            f"No trained model at {ARTIFACT_PATH}. Run `python -m pipeline.run --pre-event` first."
        )
    m = xgb.XGBClassifier()
    m.load_model(ARTIFACT_PATH)
    return m
