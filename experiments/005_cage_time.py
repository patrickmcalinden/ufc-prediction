"""Depth of experience: cage time, five-round and title experience, DWCS route.

n_prior counts fights; it doesn't separate a 15-fight veteran of
three-round prelims from someone with five title fights. Over prior fights:

  cage_min     — total minutes fought
  avg_len      — mean fight length (minutes)
  distance_r   — share of fights that went to a decision
  five_rd      — fights that went past round 3
  title_n      — prior title fights
  dwcs         — has a prior Dana White's Contender Series fight (1/0)
"""

import pandas as pd

import _lab
from _leader import LEADER, add_leader_features

NAME = "cage_time"
HYPOTHESIS = "Cage time, five-round/title experience and the DWCS route add signal beyond fight count."
BASE = LEADER


def add_features(df, engine):
    df = add_leader_features(df, engine)
    L = _lab.fights_long(engine)
    ev = pd.read_sql_query(
        "SELECT f.fight_id, e.name ILIKE '%%contender%%' AS dwcs FROM fights f JOIN events e USING (event_id)", engine
    ).set_index("fight_id").dwcs
    mins = L.secs / 60
    _lab.attach(df, L, "cage_min", _lab.prior_sum(L, mins))
    _lab.attach(df, L, "avg_len", _lab.prior_mean(L, mins.where(L.happened == 1)))
    _lab.attach(df, L, "distance_r", _lab.ratio(_lab.prior_sum(L, L.dec.astype(float)), _lab.prior_sum(L, L.happened)))
    _lab.attach(df, L, "five_rd", _lab.prior_sum(L, (L["round"] > 3).astype(float)))
    _lab.attach(df, L, "title_n", _lab.prior_sum(L, L.is_title_fight.fillna(False).astype(float)))
    _lab.attach(df, L, "dwcs", (_lab.prior_sum(L, L.fight_id.map(ev).fillna(False).astype(float)) > 0).astype(float))
    return df


def _abd(*names):
    return [f"{p}_{n}" for n in names for p in "abd"]


F = LEADER["features"]
CANDIDATES = {
    "cage": {"features": F + _abd("cage_min", "avg_len", "distance_r")},
    "big_fights": {"features": F + _abd("five_rd", "title_n")},
    "dwcs": {"features": F + _abd("dwcs")},
    "all": {"features": F + _abd("cage_min", "avg_len", "distance_r", "five_rd", "title_n", "dwcs")},
}
