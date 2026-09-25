"""Shared helpers for experiment files. Not imported by production code.

`fights_long(engine)` — one row per (fight, fighter) for every non-cancelled
fight, chronological, with the fighter's and opponent's pre-fight tuned-Elo
rating, outcome, method, finish round/time and fight length in seconds.

`prior_sum` / `prior_mean` — per-fighter cumulative stats over fights
strictly BEFORE the current one (shifted by one), so every derived feature
is pre-fight by construction.

`attach(df, long, name, values)` — map a per-(fight, fighter) Series onto
the v3 frame as a_<name>, b_<name>, d_<name> via history.add_pair
(symmetric missingness by default).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.history import ELO3_CONFIG, _is_finish, add_pair

_SQL = """
SELECT fight_id, fight_date, fighter_a_id, fighter_b_id, winner_id, method,
       round, time, weight_class, is_title_fight
  FROM fights
 WHERE NOT COALESCE(is_cancelled, FALSE)
   AND fighter_a_id IS NOT NULL AND fighter_b_id IS NOT NULL
 ORDER BY fight_date, fight_id
"""


def _secs(t) -> float:
    try:
        m, s = str(t).split(":")
        return int(m) * 60 + int(s)
    except (ValueError, AttributeError):
        return np.nan


def elo_pre(F: pd.DataFrame, cfg: dict = ELO3_CONFIG) -> pd.DataFrame:
    """Pre-fight ratings (ra, rb) per fight_id — same maths as history._elo3."""
    start, K, bonus, decay = cfg["start"], cfg["k"], cfg["finish_bonus"], cfg["decay"]
    R, last, rows = {}, {}, []
    for r in F.itertuples():
        a, b = r.fighter_a_id, r.fighter_b_id
        for f in (a, b):
            if decay and f in last:
                yrs = (r.fight_date - last[f]).days / 365.25
                if yrs > 1:
                    R[f] = start + (R.get(f, start) - start) * (1 - decay) ** (yrs - 1)
        ra, rb = R.get(a, start), R.get(b, start)
        rows.append((r.fight_id, ra, rb))
        if pd.isna(r.winner_id):
            if r.method is not None:
                last[a] = last[b] = r.fight_date
            continue
        s = 1.0 if r.winner_id == a else 0.0
        ea = 1 / (1 + 10 ** ((rb - ra) / 400))
        k = K * (1 + bonus * _is_finish(r.method))
        R[a] = ra + k * (s - ea)
        R[b] = rb + k * ((1 - s) - (1 - ea))
        last[a] = last[b] = r.fight_date
    return pd.DataFrame(rows, columns=["fight_id", "ra", "rb"]).set_index("fight_id")


def load_fights(engine) -> pd.DataFrame:
    F = pd.read_sql_query(_SQL, engine)
    F["fight_date"] = pd.to_datetime(F.fight_date)
    F["secs"] = np.where(F["round"].notna(), (F["round"] - 1) * 300 + F["time"].map(_secs), np.nan)
    return F


def fights_long(engine, F: pd.DataFrame | None = None) -> pd.DataFrame:
    F = load_fights(engine) if F is None else F
    E = elo_pre(F)
    F = F.join(E, on="fight_id")
    a = F.assign(fid=F.fighter_a_id, opp=F.fighter_b_id, elo=F.ra, opp_elo=F.rb)
    b = F.assign(fid=F.fighter_b_id, opp=F.fighter_a_id, elo=F.rb, opp_elo=F.ra)
    L = pd.concat([a, b], ignore_index=True)
    L["happened"] = (L.winner_id.notna() | L.method.notna()).astype(int)
    L["won"] = np.where(L.winner_id.isna(), np.nan, (L.winner_id == L.fid).astype(float))
    m = L.method.fillna("")
    L["ko"] = m.str.contains(r"KO|TKO")
    L["sub"] = m.str.contains("Sub")
    L["dec"] = m.str.contains("Dec")
    return L.sort_values(["fid", "fight_date", "fight_id"]).reset_index(drop=True)


def prior_sum(L: pd.DataFrame, values: pd.Series) -> pd.Series:
    """Sum of `values` over each fighter's earlier fights (NaN treated as 0)."""
    v = pd.Series(values, index=L.index).fillna(0)
    return v.groupby(L.fid).transform(lambda s: s.cumsum().shift(1).fillna(0))


def prior_mean(L: pd.DataFrame, values: pd.Series, window: int | None = None) -> pd.Series:
    """Mean of `values` over earlier fights, skipping NaN; NaN if none."""
    v = pd.Series(values, index=L.index, dtype=float)
    g = v.groupby(L.fid)
    if window:
        return g.transform(lambda s: s.shift(1).rolling(window, min_periods=1).mean())
    num = g.transform(lambda s: s.fillna(0).cumsum().shift(1))
    den = v.notna().astype(float).groupby(L.fid).transform(lambda s: s.cumsum().shift(1))
    return (num / den).where(den > 0)


def ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    return (num / den).where(den > 0)


def attach(df: pd.DataFrame, L: pd.DataFrame, name: str, values: pd.Series, symmetric: bool = True) -> list[str]:
    """Put a per-(fight, fighter) value onto the v3 frame; returns the 3 column names."""
    s = pd.Series(values.to_numpy(), index=pd.MultiIndex.from_arrays([L.fight_id, L.fid]))
    s = s[~s.index.duplicated()]
    a = pd.Series(list(zip(df.fight_id, df.fighter_a_id))).map(s)
    b = pd.Series(list(zip(df.fight_id, df.fighter_b_id))).map(s)
    add_pair(df, name, a.to_numpy(), b.to_numpy(), symmetric=symmetric)
    return [f"a_{name}", f"b_{name}", f"d_{name}"]
