"""Model registry.

Each entry defines a named family of model (e.g. "elo_only", "elo_stats").
The pipeline trains and predicts per-model: every named model gets its own
artifact file, its own metadata sidecar, and its own set of rows in the
predictions table (model_version = the family name).

Add a new model by appending to MODELS. The dashboard groups automatically
by model_version, so new models show up without UI changes.
"""

from __future__ import annotations

from dataclasses import dataclass


# Base Elo-only feature set: just the 6 Elo features + title flag.
FEATURES_ELO = [
    "elo_std_pre_a", "elo_mod_pre_a",
    "elo_std_pre_b", "elo_mod_pre_b",
    "elo_diff_std", "elo_diff_mod",
    "is_title_fight",
]

# Full feature set: Elo + historical striking + grappling.
FEATURES_FULL = [
    *FEATURES_ELO,
    "a_str_acc", "a_str_vol", "a_td_acc", "a_grap_agg", "a_str_def",
    "b_str_acc", "b_str_vol", "b_td_acc", "b_grap_agg", "b_str_def",
    "diff_str_acc", "diff_str_vol", "diff_td_acc", "diff_grap_agg", "diff_str_def",
]


@dataclass(frozen=True)
class ModelConfig:
    name: str
    description: str
    features: list[str]
    # XGBoost hyperparameters
    n_estimators: int = 300
    max_depth: int = 6
    learning_rate: float = 0.02
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    random_state: int = 42


MODELS: dict[str, ModelConfig] = {
    "elo_only": ModelConfig(
        name="elo_only",
        description="Baseline: pre-fight Elo ratings (standard + modified) and title-fight flag only.",
        features=FEATURES_ELO,
        max_depth=4,
        learning_rate=0.05,
    ),
    "elo_stats": ModelConfig(
        name="elo_stats",
        description="Elo + historical striking accuracy/volume/defense, takedown accuracy, and grappling aggression.",
        features=FEATURES_FULL,
        max_depth=6,
        learning_rate=0.02,
    ),
}


def get(name: str) -> ModelConfig:
    if name not in MODELS:
        raise KeyError(f"Unknown model '{name}'. Known: {sorted(MODELS)}")
    return MODELS[name]


def all_names() -> list[str]:
    return list(MODELS)
