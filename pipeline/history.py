"""Leak-free pre-fight features for the v3 model family.

Everything here derives from two tables with complete coverage:

  * `fights`   — built from ESPN's event schedule, so every UFC / DWCS bout is
                 present regardless of how long the fighters' careers lasted.
  * `fighters` — only date_of_birth is used (~96% populated).

`fighter_stats` is deliberately NOT used: it's only populated for fighters
who appeared on a recent card, so "has stats" is a proxy for "still active
today" — future information. That leak is what inflated v2's CV score.

One pass over the whole fights table produces pre-fight features for every
non-cancelled fight, completed or upcoming. Training takes the completed
rows; prediction looks up the upcoming ones by fight_id. Same code path for
both, so there's no train/serve skew.

Missingness is made symmetric: if a stat is unknown for either fighter, it's
set to NaN for both (and the diff). Otherwise "only one side is missing"
becomes a feature in itself — e.g. fighters without a scraped DOB lose
~85% of the time, which says something about scraping, not fighting.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from pipeline.db import sqlalchemy_url

# Tuned by a sweep over K / finish bonus / inactivity decay, scored on
# 2019+ log loss of the raw Elo win probability.
ELO3_CONFIG = {
    "start": 1500.0,
    "k": 64.0,
    "finish_bonus": 0.5,   # K multiplier bump for KO/TKO/Sub wins
    "decay": 0.2,          # per-year pull toward `start` after 1y inactive
}

# Per-fighter history stats. Each becomes a_<h>, b_<h>, d_<h> (= a - b).
HISTORY_STATS = [
    "n_prior",       # prior UFC/DWCS fights
    "win_pct",       # prior win rate (NaN on debut)
    "fin_rate",      # share of prior wins by KO/TKO/Sub (NaN with 0 wins)
    "koloss_prior",  # prior losses by KO/TKO
    "days_off",      # days since previous fight (NaN on debut)
    "streak",        # +n win streak / -n losing streak going in
    "last3",         # win rate over last 3 fights (NC/Draw = 0.5)
    "age",           # years, from date_of_birth
]

FEATURES_V3 = ["elo3_diff", *[f"{p}_{h}" for h in HISTORY_STATS for p in ("a", "b", "d")]]

_FIGHTS_SQL = """
SELECT fight_id, fight_date, fighter_a_id, fighter_b_id, winner_id, method,
       is_title_fight
  FROM fights
 WHERE NOT COALESCE(is_cancelled, FALSE)
   AND fighter_a_id IS NOT NULL AND fighter_b_id IS NOT NULL
 ORDER BY fight_date, fight_id
"""

_FINISH = r"KO|TKO|Sub"


def _is_finish(method) -> bool:
    return bool(method) and any(t in str(method) for t in ("KO", "Sub"))


def _elo3(F: pd.DataFrame, cfg: dict = ELO3_CONFIG) -> pd.Series:
    """Pre-fight (rating_a - rating_b) per fight_id under the tuned Elo."""
    start, K, bonus, decay = cfg["start"], cfg["k"], cfg["finish_bonus"], cfg["decay"]
    R: dict[int, float] = {}
    last: dict[int, pd.Timestamp] = {}
    out = {}
    for r in F.itertuples():
        a, b = r.fighter_a_id, r.fighter_b_id
        for f in (a, b):
            if decay and f in last:
                yrs = (r.fight_date - last[f]).days / 365.25
                if yrs > 1:
                    R[f] = start + (R.get(f, start) - start) * (1 - decay) ** (yrs - 1)
        ra, rb = R.get(a, start), R.get(b, start)
        out[r.fight_id] = ra - rb
        if pd.isna(r.winner_id):
            # Upcoming, NC or Draw: no rating change. Only move the
            # inactivity clock for fights that actually happened.
            if r.method is not None:
                last[a] = last[b] = r.fight_date
            continue
        s = 1.0 if r.winner_id == a else 0.0
        ea = 1 / (1 + 10 ** ((rb - ra) / 400))
        k = K * (1 + bonus * _is_finish(r.method))
        R[a] = ra + k * (s - ea)
        R[b] = rb + k * ((1 - s) - (1 - ea))
        last[a] = last[b] = r.fight_date
    return pd.Series(out, name="elo3_diff")


def _streak(won: pd.Series) -> pd.Series:
    out, c = [], 0
    for w in won.fillna(0.5):
        out.append(c)
        if w == 1:
            c = c + 1 if c >= 0 else 1
        elif w == 0:
            c = c - 1 if c <= 0 else -1
        else:
            c = 0
    return pd.Series(out, index=won.index)


def _per_fighter(F: pd.DataFrame, dob: pd.Series) -> pd.DataFrame:
    """One row per (fight_id, fighter) with that fighter's pre-fight history."""
    long = pd.concat([
        F.assign(fid=F.fighter_a_id),
        F.assign(fid=F.fighter_b_id),
    ])
    happened = long.winner_id.notna() | long.method.notna()
    long["won"] = np.where(long.winner_id.isna(), np.nan, (long.winner_id == long.fid).astype(float))
    m = long.method.fillna("")
    long["fin_win"] = ((long.won == 1) & m.str.contains(_FINISH)).astype(int)
    long["ko_loss"] = ((long.won == 0) & m.str.contains(r"KO|TKO")).astype(int)
    long["happened"] = happened.astype(int)
    long = long.sort_values(["fid", "fight_date", "fight_id"])

    g = long.groupby("fid", sort=False)
    prior = lambda col: g[col].transform(lambda s: s.cumsum().shift(1).fillna(0))  # noqa: E731
    long["n_prior"] = prior("happened")
    long["wins_prior"] = g["won"].transform(lambda s: s.fillna(0).cumsum().shift(1).fillna(0))
    long["fin_prior"] = prior("fin_win")
    long["koloss_prior"] = prior("ko_loss")
    # Only completed fights count toward layoff; an upcoming fight's
    # previous date is the fighter's last real fight.
    long["last_date"] = long.fight_date.where(long.happened == 1)
    long["days_off"] = (long.fight_date - g["last_date"].transform(lambda s: s.ffill().shift(1))).dt.days
    long["streak"] = g["won"].transform(_streak)
    long["last3"] = g["won"].transform(lambda s: s.fillna(0.5).shift(1).rolling(3, min_periods=1).mean())

    long["win_pct"] = np.where(long.n_prior > 0, long.wins_prior / long.n_prior.clip(lower=1), np.nan)
    long["fin_rate"] = np.where(long.wins_prior > 0, long.fin_prior / long.wins_prior.clip(lower=1), np.nan)
    long["age"] = (long.fight_date - long.fid.map(dob)).dt.days / 365.25
    return long[["fight_id", "fid", *HISTORY_STATS]]


def build_v3_frame(engine=None) -> pd.DataFrame:
    """Pre-fight v3 features for every non-cancelled fight (completed + upcoming).

    Columns: fight_id, fight_date, fighter_a_id, fighter_b_id, winner_id,
    is_title_fight, label (NaN unless a/b won), plus FEATURES_V3.
    """
    engine = engine or create_engine(sqlalchemy_url())
    F = pd.read_sql_query(_FIGHTS_SQL, engine)
    F["fight_date"] = pd.to_datetime(F.fight_date)
    fx = pd.read_sql_query("SELECT fighter_id, date_of_birth FROM fighters", engine)
    dob = pd.to_datetime(fx.set_index("fighter_id").date_of_birth)

    hist = _per_fighter(F, dob)
    out = F.copy()
    for side in ("a", "b"):
        h = hist.rename(columns={s: f"{side}_{s}" for s in HISTORY_STATS})
        out = out.merge(h, left_on=["fight_id", f"fighter_{side}_id"], right_on=["fight_id", "fid"], how="left")
        out = out.drop(columns="fid")

    for s in HISTORY_STATS:
        add_pair(out, s, out[f"a_{s}"], out[f"b_{s}"])

    out["elo3_diff"] = out.fight_id.map(_elo3(F))
    decided = out.winner_id.notna() & out.winner_id.isin(pd.concat([out.fighter_a_id, out.fighter_b_id]))
    out["label"] = np.where(decided, (out.winner_id == out.fighter_a_id).astype(float), np.nan)
    return out


def add_pair(df: pd.DataFrame, stat: str, a, b, symmetric: bool = True) -> pd.DataFrame:
    """Set a_<stat>, b_<stat>, d_<stat> on df (in place; also returned).

    symmetric=True blanks both sides when either is missing, so coverage
    can't become a signal. Only turn it off to demonstrate a leak.
    """
    a = pd.Series(a, index=df.index, dtype=float)
    b = pd.Series(b, index=df.index, dtype=float)
    if symmetric:
        either = a.isna() | b.isna()
        a, b = a.mask(either), b.mask(either)
    df[f"a_{stat}"], df[f"b_{stat}"] = a, b
    df[f"d_{stat}"] = a - b
    return df


def mirror(df: pd.DataFrame) -> pd.DataFrame:
    """Append the A/B-swapped copy of df so the model can't learn corner order."""
    m = df.copy()
    for c in df.columns:
        if c.startswith("a_") and f"b_{c[2:]}" in df:
            m[c], m[f"b_{c[2:]}"] = df[f"b_{c[2:]}"], df[c]
        elif c.startswith("d_") or c == "elo3_diff":
            m[c] = -df[c]
    m["fighter_a_id"], m["fighter_b_id"] = df["fighter_b_id"], df["fighter_a_id"]
    m["label"] = 1 - df["label"]
    return pd.concat([df, m], ignore_index=True)
