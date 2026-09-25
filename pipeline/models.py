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

from pipeline.history import FEATURES_V3


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
    # Which feature builder feeds this model:
    #   "legacy" — pipeline.features (elo_ratings + fighter_stats)
    #   "v3"     — pipeline.history (fights table + tuned Elo)
    feature_set: str = "legacy"
    # Retired models keep their graded history on the dashboard but are no
    # longer trained, and no longer lock or backfill picks.
    retired: bool = False
    # Training refuses a model that fails evaluate.leak_check unless this is
    # set. Only for grandfathered models kept around for the live record.
    known_leak: bool = False
    # XGBoost hyperparameters
    n_estimators: int = 300
    max_depth: int = 6
    learning_rate: float = 0.02
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_weight: float = 1.0
    random_state: int = 42


MODELS: dict[str, ModelConfig] = {
    "v1": ModelConfig(
        name="v1",
        description="Baseline: pre-fight Elo ratings (standard + modified) and title-fight flag only.",
        features=FEATURES_ELO,
        max_depth=4,
        learning_rate=0.05,
    ),
    "v2": ModelConfig(
        name="v2",
        description="Elo + historical striking accuracy/volume/defense, takedown accuracy, and grappling aggression.",
        features=FEATURES_FULL,
        max_depth=6,
        learning_rate=0.02,
        # fighter_stats only covers fighters active on recent cards, so
        # stats *coverage* predicts the winner. Kept running for the
        # side-by-side with v3; see pipeline/evaluate.py.
        known_leak=True,
    ),
    "v3": ModelConfig(
        name="v3",
        description="Tuned Elo + fight history (experience, win rate, finish rate, KO losses, layoff, streak, recent form, age). No fighter_stats.",
        features=FEATURES_V3,
        feature_set="v3",
        n_estimators=400,
        max_depth=3,
        learning_rate=0.03,
        min_child_weight=5,
    ),
}


def get(name: str) -> ModelConfig:
    if name not in MODELS:
        raise KeyError(f"Unknown model '{name}'. Known: {sorted(MODELS)}")
    return MODELS[name]


def all_names() -> list[str]:
    """Active models: the ones that get trained and lock picks."""
    return [n for n, m in MODELS.items() if not m.retired]


def is_retired(name: str) -> bool:
    """True for registry entries marked retired. Unknown (historical)
    model_versions count as retired too — nothing produces them any more."""
    return name not in MODELS or MODELS[name].retired
