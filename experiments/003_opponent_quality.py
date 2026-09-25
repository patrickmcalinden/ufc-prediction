"""Who you beat, not just how often: strength of schedule and quality wins.

Win rate treats a win over a debutant like a win over a contender. Using
each opponent's pre-fight tuned-Elo rating:

  sos        — mean opponent rating over prior fights
  qual_win   — mean rating of opponents beaten (NaN with no wins)
  best_win   — highest-rated opponent beaten
  momentum   — own rating now minus rating 3 fights ago
"""

import _lab
from _leader import LEADER, add_leader_features

NAME = "opponent_quality"
HYPOTHESIS = "Opponent-adjusted records (SoS, quality of wins, Elo momentum) add signal beyond win rate."
BASE = LEADER


def add_features(df, engine):
    df = add_leader_features(df, engine)
    L = _lab.fights_long(engine)
    beaten = L.opp_elo.where(L.won == 1)
    _lab.attach(df, L, "sos", _lab.prior_mean(L, L.opp_elo.where(L.happened == 1)))
    _lab.attach(df, L, "qual_win", _lab.prior_mean(L, beaten))
    _lab.attach(df, L, "best_win", beaten.groupby(L.fid).transform(lambda s: s.shift(1).cummax()))
    _lab.attach(df, L, "momentum", L.elo - L.groupby("fid").elo.shift(3))
    return df


def _abd(*names):
    return [f"{p}_{n}" for n in names for p in "abd"]


F = LEADER["features"]
CANDIDATES = {
    "sos": {"features": F + _abd("sos")},
    "quality_wins": {"features": F + _abd("qual_win", "best_win")},
    "momentum": {"features": F + _abd("momentum")},
    "all": {"features": F + _abd("sos", "qual_win", "best_win", "momentum")},
}
