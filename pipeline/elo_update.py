"""Apply Elo updates after fights are graded.

Two operations, always run together via `update_elo()`:
  1. INCREMENTAL: replay any new completed fights into elo_ratings
  2. REFRESH:    sync fighters.current_elo_* from the latest elo_ratings rows

The denormalized current_elo_* columns are what the predictions page
joins against, so they MUST stay in sync after any Elo write.
"""

from __future__ import annotations

import logging

from pipeline.db import connect
from pipeline.elo import ELO_CONFIG, update_modified_elo, update_standard_elo

log = logging.getLogger(__name__)


def _incremental(cur, full_rebuild: bool = False) -> int:
    """Process any completed fights newer than the latest in elo_ratings.
    Returns the number of fights processed."""
    ratings_std: dict[int, float] = {}
    ratings_mod: dict[int, float] = {}

    if full_rebuild:
        log.warning("Full Elo rebuild — truncating elo_ratings")
        cur.execute("TRUNCATE elo_ratings RESTART IDENTITY")
        cur.execute(
            """
            SELECT fight_id, fight_date, fighter_a_id, fighter_b_id, winner_id
              FROM fights
             WHERE winner_id IS NOT NULL
             ORDER BY fight_date ASC, fight_id ASC
            """
        )
    else:
        cur.execute("SELECT COALESCE(MAX(fight_id), 0) AS max_fid FROM elo_ratings")
        max_fid = cur.fetchone()["max_fid"]
        log.info("Incremental Elo run — last processed fight_id = %s", max_fid)

        cur.execute(
            """
            SELECT DISTINCT ON (fighter_id)
                   fighter_id, elo_standard, elo_modified
              FROM elo_ratings
             ORDER BY fighter_id, rating_id DESC
            """
        )
        for r in cur.fetchall():
            ratings_std[r["fighter_id"]] = float(r["elo_standard"])
            ratings_mod[r["fighter_id"]] = float(r["elo_modified"])

        cur.execute(
            """
            SELECT fight_id, fight_date, fighter_a_id, fighter_b_id, winner_id
              FROM fights
             WHERE winner_id IS NOT NULL AND fight_id > %s
             ORDER BY fight_date ASC, fight_id ASC
            """,
            (max_fid,),
        )

    fights = cur.fetchall()
    if not fights:
        log.info("No new fights to Elo-rate")
        return 0

    rows = []
    for f in fights:
        a, b, w = f["fighter_a_id"], f["fighter_b_id"], f["winner_id"]
        if w not in (a, b):
            continue

        a_std = ratings_std.get(a, ELO_CONFIG["starting_rating"])
        b_std = ratings_std.get(b, ELO_CONFIG["starting_rating"])
        a_mod = ratings_mod.get(a, ELO_CONFIG["starting_rating"])
        b_mod = ratings_mod.get(b, ELO_CONFIG["starting_rating"])
        pre_a_std, pre_b_std, pre_a_mod, pre_b_mod = a_std, b_std, a_mod, b_mod

        if w == a:
            a_std, b_std = update_standard_elo(pre_a_std, pre_b_std, ELO_CONFIG["base_k"])
            a_mod, b_mod = update_modified_elo(pre_a_mod, pre_b_mod, ELO_CONFIG)
        else:
            b_std, a_std = update_standard_elo(pre_b_std, pre_a_std, ELO_CONFIG["base_k"])
            b_mod, a_mod = update_modified_elo(pre_b_mod, pre_a_mod, ELO_CONFIG)

        ratings_std[a], ratings_std[b] = a_std, b_std
        ratings_mod[a], ratings_mod[b] = a_mod, b_mod

        rows.append((f["fight_id"], a, pre_a_std, a_std, pre_a_mod, a_mod, f["fight_date"]))
        rows.append((f["fight_id"], b, pre_b_std, b_std, pre_b_mod, b_mod, f["fight_date"]))

    cur.executemany(
        """
        INSERT INTO elo_ratings (
            fight_id, fighter_id,
            elo_standard_pre, elo_standard,
            elo_modified_pre, elo_modified,
            rating_date
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        rows,
    )
    log.info("Inserted Elo rows for %d fights", len(fights))
    return len(fights)


def _refresh_current_elo(cur) -> int:
    """Sync fighters.current_elo_* from the latest elo_ratings row per fighter."""
    cur.execute(
        """
        WITH latest AS (
            SELECT DISTINCT ON (fighter_id)
                   fighter_id, elo_standard, elo_modified
              FROM elo_ratings
             ORDER BY fighter_id, rating_id DESC
        )
        UPDATE fighters f
           SET current_elo_standard = latest.elo_standard,
               current_elo_modified = latest.elo_modified,
               current_elo_updated_at = NOW()
          FROM latest
         WHERE latest.fighter_id = f.fighter_id
        """
    )
    return cur.rowcount


def update_elo(full_rebuild: bool = False) -> dict:
    """Incremental Elo run followed by current_elo refresh.

    This is what the post-event pipeline calls after grading is done.
    """
    with connect() as conn, conn.cursor() as cur:
        processed = _incremental(cur, full_rebuild=full_rebuild)
        refreshed = _refresh_current_elo(cur)
        conn.commit()
    log.info("Elo update done — %d fights processed, %d fighters refreshed", processed, refreshed)
    return {"fights_processed": processed, "fighters_refreshed": refreshed}
