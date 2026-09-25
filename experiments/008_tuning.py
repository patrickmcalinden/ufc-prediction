"""Hyperparameter tuning on the search leader (v3 features + corner).

Features stopped improving (5 experiments without a 'better' after 002),
so per the search protocol this is the tuning step: a small grid around
v3's settings (depth 3, 400 trees, lr 0.03, min_child_weight 5).
"""

from _leader import LEADER, add_leader_features

NAME = "tuning"
HYPOTHESIS = "Different depth / learning rate / regularisation improves the leader."
BASE = LEADER


def add_features(df, engine):
    return add_leader_features(df, engine)


F = LEADER["features"]
CANDIDATES = {
    "depth2": {"features": F, "params": {"max_depth": 2, "n_estimators": 600}},
    "depth4": {"features": F, "params": {"max_depth": 4, "n_estimators": 300}},
    "slow": {"features": F, "params": {"learning_rate": 0.015, "n_estimators": 800}},
    "reg": {"features": F, "params": {"min_child_weight": 20, "subsample": 0.7, "colsample_bytree": 0.6}},
    "depth2_reg": {"features": F, "params": {"max_depth": 2, "n_estimators": 600, "min_child_weight": 20,
                                              "colsample_bytree": 0.6}},
}
