"""Striking and grappling rates from fighter_stats — 2018+ fights only.

fighter_stats was backfilled on 2026-09-25 for every fighter with a fight
since 2018-01-01, and the weekly job adds everyone on each new card, so
2018+ fights have stats for BOTH fighters regardless of how their careers
went. Earlier rows exist only for fighters whose careers reached 2018 —
survivorship — so they're dropped here.

Per fighter, over prior 2018+ fights with stats, per minute of cage time:

  slpm       sig strikes landed / min          sapm     absorbed / min
  str_acc    landed / attempted                str_def  1 - opp landed / opp attempted
  td15       takedowns landed / 15 min         td_acc   landed / attempted
  td_def     1 - opp td landed / opp td att    kd15     knockdowns / 15 min
  sub15      submission attempts / 15 min      adv15    positional advances / 15 min
  gnd_share  share of sig strikes landed on the ground

`coverage` (not a model input) reports how complete 2018+ stats are.
"""

import numpy as np
import pandas as pd

import _lab
from _leader import LEADER, add_leader_features

NAME = "striking_grappling"
HYPOTHESIS = "Per-minute striking/grappling rates (2018+ stats, full coverage) add signal beyond record-based history."
BASE = LEADER
STATS_FROM = "2018-01-01"

_SQL = f"""
SELECT s.fight_id, s.fighter_id AS fid,
       s.sig_strikes_landed AS sl, s.sig_strikes_attempted AS sa,
       s.knockdowns AS kd, s.takedowns_landed AS tl, s.takedowns_attempted AS ta,
       s.submissions AS sub_att, s.advances AS adv,
       COALESCE(s.sg_head_landed, 0) + COALESCE(s.sg_body_landed, 0) + COALESCE(s.sg_leg_landed, 0) AS gl
  FROM fighter_stats s JOIN fights f USING (fight_id)
 WHERE f.fight_date >= '{STATS_FROM}'
"""


def add_features(df, engine):
    df = add_leader_features(df, engine)
    L = _lab.fights_long(engine)
    S = pd.read_sql_query(_SQL, engine)
    opp = S.rename(columns={c: f"o_{c}" for c in S.columns if c not in ("fight_id",)}).rename(columns={"o_fid": "opp"})
    L = L.merge(S, on=["fight_id", "fid"], how="left").merge(opp, on=["fight_id", "opp"], how="left")
    # A fight counts only if both sides have stats and a known length.
    ok = L.sl.notna() & L.o_sl.notna() & L.secs.gt(0)
    mins = (L.secs / 60).where(ok)

    def ps(col):
        return _lab.prior_sum(L, L[col].where(ok))

    m = _lab.prior_sum(L, mins)
    m = m.where(m > 0)
    per_min = lambda col: ps(col) / m          # noqa: E731
    per15 = lambda col: ps(col) / m * 15       # noqa: E731
    feats = {
        "slpm": per_min("sl"), "sapm": per_min("o_sl"),
        "str_acc": _lab.ratio(ps("sl"), ps("sa")), "str_def": 1 - _lab.ratio(ps("o_sl"), ps("o_sa")),
        "td15": per15("tl"), "td_acc": _lab.ratio(ps("tl"), ps("ta")),
        "td_def": 1 - _lab.ratio(ps("o_tl"), ps("o_ta")), "kd15": per15("kd"),
        "sub15": per15("sub_att"), "adv15": per15("adv"),
        "gnd_share": _lab.ratio(ps("gl"), ps("sl")),
    }
    for name, v in feats.items():
        _lab.attach(df, L, name, v)

    # Coverage report for decided 2018+ fights.
    both = L.assign(ok=ok).groupby("fight_id").ok.all()
    recent = df[(df.fight_date >= STATS_FROM) & df.label.notna()]
    print(f"[007] 2018+ decided fights with stats for both fighters: "
          f"{both.reindex(recent.fight_id).fillna(False).mean():.1%} of {len(recent)}")
    return df


def _abd(*names):
    return [f"{p}_{n}" for n in names for p in "abd"]


F = LEADER["features"]
STRIKE = ("slpm", "sapm", "str_acc", "str_def", "kd15")
GRAPPLE = ("td15", "td_acc", "td_def", "sub15", "adv15", "gnd_share")
CANDIDATES = {
    "striking": {"features": F + _abd(*STRIKE)},
    "grappling": {"features": F + _abd(*GRAPPLE)},
    "all": {"features": F + _abd(*STRIKE, *GRAPPLE)},
    "diffs_only": {"features": F + [f"d_{n}" for n in (*STRIKE, *GRAPPLE)]},
}
