"""Final holdout run for search 2026-09-25.

Search result: the only idea that cleared the bar was 002 (corner order).
003-007 were inconclusive (stop rule hit after 5), and 008 tuning found
nothing, so the finished model is v3 + d_corner with v3's settings.
Run once with --final against registered v3.
"""

from _leader import LEADER, add_leader_features

NAME = "final_search_2026_09"
HYPOTHESIS = "v3 + corner (the search leader) beats v3 on the held-out two years."
BASE = "v3"


def add_features(df, engine):
    return add_leader_features(df, engine)


CANDIDATES = {"v3_corner": {"features": LEADER["features"]}}
