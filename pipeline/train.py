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

import pandas as pd
import xgboost as xgb

from pipeline import evaluate
from pipeline.features import build_legacy_frame, legacy_mirror, legacy_presence_view
from pipeline.history import build_v3_frame, mirror as v3_mirror
from pipeline.models import ModelConfig, all_names, get

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
        min_child_weight=cfg.min_child_weight,
        eval_metric="logloss",
        random_state=cfg.random_state,
    )


class LeakCheckFailed(RuntimeError):
    pass


def _frames(cfg: ModelConfig, cache: dict) -> tuple[pd.DataFrame, pd.DataFrame, callable]:
    """(training frame, leak-check view, mirror fn) for a model's feature set.

    Training frame: one row per decided fight, not mirrored.
    Leak-check view: same rows with "no data" as NaN.
    """
    if cfg.feature_set not in cache:
        if cfg.feature_set == "legacy":
            df = build_legacy_frame()
            cache["legacy"] = (df, legacy_presence_view(df), legacy_mirror)
        elif cfg.feature_set == "v3":
            df = build_v3_frame()
            df = df[df["label"].notna()].sort_values("fight_date").reset_index(drop=True)
            df["label"] = df["label"].astype(int)
            cache["v3"] = (df, df, v3_mirror)
        else:
            raise ValueError(f"Unknown feature_set {cfg.feature_set!r}")
    return cache[cfg.feature_set]


def train_one(name: str, _cache: dict | None = None) -> dict:
    cfg = get(name)
    cache = {} if _cache is None else _cache
    log.info("[%s] Training (feature_set=%s)", name, cfg.feature_set)

    df, presence, mirror = _frames(cfg, cache)

    leak = evaluate.leak_check(presence, cfg.features)
    if not leak["passed"]:
        msg = f"[{name}] leak check FAILED: {leak['flagged']}"
        if not cfg.known_leak:
            raise LeakCheckFailed(msg + " — fix the features or set known_leak on the model")
        log.warning(msg + " (known_leak — continuing)")

    # For a leaky model, also score it on just the fights where no flagged
    # feature is one-sided. That's the honest estimate for live use.
    clean = None
    if leak["flagged"]:
        clean = pd.Series(True, index=presence.index)
        for f in leak["flagged"]:
            a, b = f"a_{f['feature']}", f"b_{f['feature']}"
            clean &= ~(presence[a].notna() ^ presence[b].notna())

    log.info("[%s] Walk-forward backtest on %d fights", name, len(df))
    ev = evaluate.walk_forward(df, cfg.features, lambda: _build_classifier(cfg), mirror, clean_mask=clean)
    log.info("[%s] Backtest %s: acc=%.3f logloss=%.3f brier=%.3f",
             name, ev["test_years"], ev["accuracy"], ev["logloss"], ev["brier"])
    if "clean_subset" in ev:
        log.info("[%s]   clean subset: acc=%.3f logloss=%.3f n=%d", name,
                 ev["clean_subset"]["accuracy"], ev["clean_subset"]["logloss"], ev["clean_subset"]["n"])

    full = mirror(df)
    model = _build_classifier(cfg)
    model.fit(full[cfg.features], full["label"])
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    art_path = _artifact_path(name)
    model.save_model(art_path)

    meta = {
        "model_version": cfg.name,
        "model_artifact": art_path.name,
        "description": cfg.description,
        "feature_set": cfg.feature_set,
        "trained_at": datetime.now().isoformat(),
        "evaluation": ev,
        "leak_check": leak,
        "n_samples": int(full.shape[0]),
        "features": list(cfg.features),
    }
    with open(_meta_path(name), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    log.info("[%s] Saved artifact + sidecar", name)
    return meta


def train_all(only: list[str] | None = None) -> list[dict]:
    """Train every registered model (or a filtered subset). Returns list of metadata dicts."""
    names = only or all_names()
    cache: dict = {}
    return [train_one(n, cache) for n in names]
