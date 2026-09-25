"""How fighters win and lose, not just whether.

v3 has finish_rate (share of wins by KO/sub) and KO losses. This splits it
out per fight, over each fighter's prior fights:

  ko_win_r / sub_win_r / dec_win_r   — share of fights won by each method
  ko_loss_r / sub_loss_r             — share of fights lost by each method
  finished_r                         — share of fights lost inside the distance
"""

import _lab
from _leader import LEADER, add_leader_features

NAME = "method_profile"
HYPOTHESIS = "Per-method win/loss rates (power, submissions, durability) add signal beyond finish rate."
BASE = LEADER


def add_features(df, engine):
    df = add_leader_features(df, engine)
    L = _lab.fights_long(engine)
    n = _lab.prior_sum(L, L.happened)
    won, lost = L.won == 1, L.won == 0
    rates = {
        "ko_win_r": won & L.ko, "sub_win_r": won & L["sub"], "dec_win_r": won & L.dec,
        "ko_loss_r": lost & L.ko, "sub_loss_r": lost & L["sub"], "finished_r": lost & (L.ko | L["sub"]),
    }
    for name, hit in rates.items():
        _lab.attach(df, L, name, _lab.ratio(_lab.prior_sum(L, hit.astype(float)), n))
    return df


def _abd(*names):
    return [f"{p}_{n}" for n in names for p in "abd"]


F = LEADER["features"]
CANDIDATES = {
    "win_methods": {"features": F + _abd("ko_win_r", "sub_win_r", "dec_win_r")},
    "loss_methods": {"features": F + _abd("ko_loss_r", "sub_loss_r", "finished_r")},
    "all": {"features": F + _abd("ko_win_r", "sub_win_r", "dec_win_r", "ko_loss_r", "sub_loss_r", "finished_r")},
}
