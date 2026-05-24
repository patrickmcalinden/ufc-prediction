"""Train XGBoost per registered model.

Each named model in pipeline.models has its own artifact + sidecar:
    model/artifacts/xgb_<name>.json       — the model
    model/artifacts/xgb_<name>.meta.json  — model_version + CV metrics

model_version is just the model name. snapshot_at distinguishes retrains.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import xgboost as xgb
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import TimeSeriesSplit

from pipeline.features import build_training_matrix
from pipeline.models import MODELS, ModelConfig, get

log = logging.getLogger(__name__)

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "model" / "artifacts"


def _artifact_path(name: str) -> Path:
    return ARTIFACT_DIR / f"xgb_{name}.json"


def _meta_path(name: str) -> Path:
    return ARTIFACT_DIR / f"xgb_{name}.meta.json"


def current_model_version(name: str) -> str:
    """For a named model, the version is just the model name.

    Provided for symmetry with the old single-model API.
    """
    return name


def load_meta(name: str) -> dict | None:
    p = _meta_path(name)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def load(name: str) -> xgb.XGBClassifier:
    p = _artifact_path(name)
    if not p.exists():
        raise FileNotFoundError(
            f"No trained artifact for model '{name}' at {p}. "
            f"Run `python -m pipeline.run --pre-event --model {name}` first."
        )
    m = xgb.XGBClassifier()
    m.load_model(p)
    return m


def _build_classifier(cfg: ModelConfig) -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=cfg.n_estimators,
        max_depth=cfg.max_depth,
        learning_rate=cfg.learning_rate,
        subsample=cfg.subsample,
        colsample_bytree=cfg.colsample_bytree,
        eval_metric="logloss",
        random_state=cfg.random_state,
    )


def train_one(name: str) -> dict:
    cfg = get(name)
    log.info("[%s] Training", name)

    df = build_training_matrix()
    X = df[cfg.features]
    y = df["label"]
    log.info("[%s] Training matrix shape: %s (features=%d)", name, X.shape, len(cfg.features))

    tscv = TimeSeriesSplit(n_splits=5)
    accs, losses = [], []
    for fold, (tr, va) in enumerate(tscv.split(X), 1):
        m = _build_classifier(cfg)
        m.fit(X.iloc[tr], y.iloc[tr])
        preds = m.predict(X.iloc[va])
        proba = m.predict_proba(X.iloc[va])[:, 1]
        accs.append(accuracy_score(y.iloc[va], preds))
        losses.append(log_loss(y.iloc[va], proba))
        log.info("[%s]   fold %d: acc=%.3f logloss=%.3f", name, fold, accs[-1], losses[-1])
    mean_acc = sum(accs) / len(accs)
    mean_logloss = sum(losses) / len(losses)
    log.info("[%s] Mean CV acc=%.3f logloss=%.3f", name, mean_acc, mean_logloss)

    model = _build_classifier(cfg)
    model.fit(X, y)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    art_path = _artifact_path(name)
    model.save_model(art_path)

    meta = {
        "model_version": cfg.name,
        "model_artifact": art_path.name,
        "description": cfg.description,
        "trained_at": datetime.now().isoformat(),
        "cv_accuracy": mean_acc,
        "cv_logloss": mean_logloss,
        "n_samples": int(X.shape[0]),
        "features": list(cfg.features),
    }
    with open(_meta_path(name), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    log.info("[%s] Saved artifact + sidecar (cv_acc=%.3f, cv_logloss=%.3f)", name, mean_acc, mean_logloss)
    return meta


def train_all(only: list[str] | None = None) -> list[dict]:
    """Train every registered model (or a filtered subset). Returns list of metadata dicts."""
    names = only or list(MODELS)
    return [train_one(n) for n in names]
