"""Feature matrix used for both training and prediction.

Features per fight (positional A/B):
  * Elo: pre-fight standard + modified, plus differentials
  * Historical aggregates derived from fighter_stats, scoped to past fights only

For training we also mirror the dataset (swap A/B, invert deltas) to
remove positional bias.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from pipeline.db import sqlalchemy_url
from pipeline.elo import ELO_CONFIG

FEATURES = [
    "elo_std_pre_a", "elo_mod_pre_a", "elo_std_pre_b", "elo_mod_pre_b",
    "elo_diff_std", "elo_diff_mod",
    "is_title_fight",
    "a_str_acc", "a_str_vol", "a_td_acc", "a_grap_agg", "a_str_def",
    "b_str_acc", "b_str_vol", "b_td_acc", "b_grap_agg", "b_str_def",
    "diff_str_acc", "diff_str_vol", "diff_td_acc", "diff_grap_agg", "diff_str_def",
]

# Historical aggregates: for each fight, sum each stat over all PRIOR fights
# the given fighter participated in (strict <). Defensive stats sum what
# OPPONENTS landed on this fighter in those prior fights.
_HISTORICAL_SQL = """
SELECT
    f.fight_id,
    f.fight_date,
    f.fighter_a_id,
    f.fighter_b_id,
    f.winner_id,
    f.is_title_fight,
    ea.elo_standard_pre AS elo_std_pre_a,
    ea.elo_modified_pre AS elo_mod_pre_a,
    eb.elo_standard_pre AS elo_std_pre_b,
    eb.elo_modified_pre AS elo_mod_pre_b,

    -- Fighter A offensive history (totals — divided into rates below)
    (SELECT SUM(sig_strikes_landed)    FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_a_id AND pf.fight_date < f.fight_date) AS a_sig_str_landed,
    (SELECT SUM(sig_strikes_attempted) FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_a_id AND pf.fight_date < f.fight_date) AS a_sig_str_att,
    (SELECT SUM(takedowns_landed)      FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_a_id AND pf.fight_date < f.fight_date) AS a_td_landed,
    (SELECT SUM(takedowns_attempted)   FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_a_id AND pf.fight_date < f.fight_date) AS a_td_att,
    (SELECT SUM(advances + submissions) FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_a_id AND pf.fight_date < f.fight_date) AS a_grappling_agg,
    (SELECT COUNT(DISTINCT pf.fight_id) FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_a_id AND pf.fight_date < f.fight_date) AS a_hist_fights,

    -- Fighter A defensive history (what opponents landed on them)
    (SELECT SUM(opp_fs.sig_strikes_landed) FROM fighter_stats opp_fs JOIN fights pf ON opp_fs.fight_id = pf.fight_id
       WHERE pf.fight_date < f.fight_date
         AND opp_fs.fighter_id != f.fighter_a_id
         AND (pf.fighter_a_id = f.fighter_a_id OR pf.fighter_b_id = f.fighter_a_id)) AS a_sig_str_absorbed,

    -- Fighter B offensive history
    (SELECT SUM(sig_strikes_landed)    FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_b_id AND pf.fight_date < f.fight_date) AS b_sig_str_landed,
    (SELECT SUM(sig_strikes_attempted) FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_b_id AND pf.fight_date < f.fight_date) AS b_sig_str_att,
    (SELECT SUM(takedowns_landed)      FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_b_id AND pf.fight_date < f.fight_date) AS b_td_landed,
    (SELECT SUM(takedowns_attempted)   FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_b_id AND pf.fight_date < f.fight_date) AS b_td_att,
    (SELECT SUM(advances + submissions) FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_b_id AND pf.fight_date < f.fight_date) AS b_grappling_agg,
    (SELECT COUNT(DISTINCT pf.fight_id) FROM fighter_stats fs JOIN fights pf ON fs.fight_id = pf.fight_id
       WHERE fs.fighter_id = f.fighter_b_id AND pf.fight_date < f.fight_date) AS b_hist_fights,

    -- Fighter B defensive history
    (SELECT SUM(opp_fs.sig_strikes_landed) FROM fighter_stats opp_fs JOIN fights pf ON opp_fs.fight_id = pf.fight_id
       WHERE pf.fight_date < f.fight_date
         AND opp_fs.fighter_id != f.fighter_b_id
         AND (pf.fighter_a_id = f.fighter_b_id OR pf.fighter_b_id = f.fighter_b_id)) AS b_sig_str_absorbed

FROM fights f
JOIN elo_ratings ea ON ea.fight_id = f.fight_id AND ea.fighter_id = f.fighter_a_id
JOIN elo_ratings eb ON eb.fight_id = f.fight_id AND eb.fighter_id = f.fighter_b_id
"""


def _derive_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Compute rate features from raw historical totals. Mutates and returns df."""
    df = df.fillna(0)
    df["elo_diff_std"] = df["elo_std_pre_a"] - df["elo_std_pre_b"]
    df["elo_diff_mod"] = df["elo_mod_pre_a"] - df["elo_mod_pre_b"]

    def safe_div(num, den):
        return (num / den).replace([np.inf, -np.inf], np.nan).fillna(0)

    df["a_str_acc"]  = safe_div(df["a_sig_str_landed"], df["a_sig_str_att"])
    df["a_str_vol"]  = safe_div(df["a_sig_str_landed"], df["a_hist_fights"])
    df["a_td_acc"]   = safe_div(df["a_td_landed"], df["a_td_att"])
    df["a_grap_agg"] = safe_div(df["a_grappling_agg"], df["a_hist_fights"])
    df["a_str_def"]  = safe_div(df["a_sig_str_absorbed"], df["a_hist_fights"])

    df["b_str_acc"]  = safe_div(df["b_sig_str_landed"], df["b_sig_str_att"])
    df["b_str_vol"]  = safe_div(df["b_sig_str_landed"], df["b_hist_fights"])
    df["b_td_acc"]   = safe_div(df["b_td_landed"], df["b_td_att"])
    df["b_grap_agg"] = safe_div(df["b_grappling_agg"], df["b_hist_fights"])
    df["b_str_def"]  = safe_div(df["b_sig_str_absorbed"], df["b_hist_fights"])

    df["diff_str_acc"]  = df["a_str_acc"]  - df["b_str_acc"]
    df["diff_str_vol"]  = df["a_str_vol"]  - df["b_str_vol"]
    df["diff_td_acc"]   = df["a_td_acc"]   - df["b_td_acc"]
    df["diff_grap_agg"] = df["a_grap_agg"] - df["b_grap_agg"]
    df["diff_str_def"]  = df["a_str_def"]  - df["b_str_def"]
    return df


def build_training_matrix() -> pd.DataFrame:
    """Returns the symmetric (mirrored) feature matrix for training."""
    engine = create_engine(sqlalchemy_url())
    df = pd.read_sql_query(_HISTORICAL_SQL, engine)
    df = _derive_rates(df)
    df = df[df["winner_id"].notnull() & (df["winner_id"] != 0)].copy()
    df["label"] = (df["winner_id"] == df["fighter_a_id"]).astype(int)

    mirror = df.copy()
    swap_pairs = [
        ("fighter_a_id", "fighter_b_id"),
        ("elo_std_pre_a", "elo_std_pre_b"),
        ("elo_mod_pre_a", "elo_mod_pre_b"),
        ("a_str_acc", "b_str_acc"),
        ("a_str_vol", "b_str_vol"),
        ("a_td_acc", "b_td_acc"),
        ("a_grap_agg", "b_grap_agg"),
        ("a_str_def", "b_str_def"),
    ]
    for a, b in swap_pairs:
        mirror[a], mirror[b] = df[b], df[a]
    for col in ("elo_diff_std", "elo_diff_mod",
                "diff_str_acc", "diff_str_vol", "diff_td_acc",
                "diff_grap_agg", "diff_str_def"):
        mirror[col] = -mirror[col]
    mirror["label"] = (mirror["winner_id"] == mirror["fighter_a_id"]).astype(int)

    out = pd.concat([df, mirror], ignore_index=True).sort_values("fight_date").reset_index(drop=True)
    return out


# ─── Prediction-time feature lookup (single fight) ──────────────────────


def _latest_elo(cur, fighter_id: int) -> tuple[float, float]:
    """Use denormalized current_elo_* if populated, else fall back to defaults."""
    cur.execute(
        "SELECT current_elo_standard AS s, current_elo_modified AS m FROM fighters WHERE fighter_id = %s",
        (fighter_id,),
    )
    row = cur.fetchone()
    if row and row["s"] is not None and row["m"] is not None:
        return float(row["s"]), float(row["m"])
    return ELO_CONFIG["starting_rating"], ELO_CONFIG["starting_rating"]


def _historical_stats(cur, fighter_id: int) -> dict:
    cur.execute(
        """
        SELECT
            COALESCE(SUM(sig_strikes_landed), 0)    AS sig_str_landed,
            COALESCE(SUM(sig_strikes_attempted), 0) AS sig_str_att,
            COALESCE(SUM(takedowns_landed), 0)      AS td_landed,
            COALESCE(SUM(takedowns_attempted), 0)   AS td_att,
            COALESCE(SUM(advances + submissions), 0) AS grap_agg,
            COUNT(DISTINCT fight_id)                AS hist_fights
          FROM fighter_stats WHERE fighter_id = %s
        """,
        (fighter_id,),
    )
    off = cur.fetchone()
    cur.execute(
        """
        SELECT COALESCE(SUM(opp_fs.sig_strikes_landed), 0) AS sig_str_absorbed
          FROM fighter_stats opp_fs
          JOIN fights pf ON opp_fs.fight_id = pf.fight_id
         WHERE opp_fs.fighter_id != %s
           AND (pf.fighter_a_id = %s OR pf.fighter_b_id = %s)
        """,
        (fighter_id, fighter_id, fighter_id),
    )
    dfn = cur.fetchone()

    fights = max(int(off["hist_fights"]), 1)
    return {
        "str_acc": (float(off["sig_str_landed"]) / float(off["sig_str_att"])) if off["sig_str_att"] else 0.0,
        "str_vol": float(off["sig_str_landed"]) / fights,
        "td_acc":  (float(off["td_landed"]) / float(off["td_att"])) if off["td_att"] else 0.0,
        "grap_agg": float(off["grap_agg"]) / fights,
        "str_def": float(dfn["sig_str_absorbed"]) / fights,
    }


def features_for_fight(cur, fighter_a_id: int, fighter_b_id: int, is_title_fight: bool) -> dict:
    """Build one feature row using current Elo + historical stats. Used by predict.py."""
    a_std, a_mod = _latest_elo(cur, fighter_a_id)
    b_std, b_mod = _latest_elo(cur, fighter_b_id)
    sa = _historical_stats(cur, fighter_a_id)
    sb = _historical_stats(cur, fighter_b_id)
    return {
        "elo_std_pre_a": a_std, "elo_mod_pre_a": a_mod,
        "elo_std_pre_b": b_std, "elo_mod_pre_b": b_mod,
        "elo_diff_std": a_std - b_std,
        "elo_diff_mod": a_mod - b_mod,
        "is_title_fight": int(bool(is_title_fight)),
        "a_str_acc": sa["str_acc"], "a_str_vol": sa["str_vol"],
        "a_td_acc": sa["td_acc"], "a_grap_agg": sa["grap_agg"], "a_str_def": sa["str_def"],
        "b_str_acc": sb["str_acc"], "b_str_vol": sb["str_vol"],
        "b_td_acc": sb["td_acc"], "b_grap_agg": sb["grap_agg"], "b_str_def": sb["str_def"],
        "diff_str_acc": sa["str_acc"] - sb["str_acc"],
        "diff_str_vol": sa["str_vol"] - sb["str_vol"],
        "diff_td_acc": sa["td_acc"] - sb["td_acc"],
        "diff_grap_agg": sa["grap_agg"] - sb["grap_agg"],
        "diff_str_def": sa["str_def"] - sb["str_def"],
    }
