"""Current search leader, used as BASE by later experiments. Update when an
idea is kept (and re-run as a combination)."""

from pipeline.history import FEATURES_V3

LEADER = {
    "name": "leader",
    "features": FEATURES_V3 + ["d_corner"],   # 002 corner
    "params": {},
}


def add_leader_features(df, engine):
    df["d_corner"] = 1.0
    return df
