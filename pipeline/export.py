"""Write the JSON files the static site reads.

Outputs into site/public/data/:
    upcoming.json     — next event + locked predictions for it
    performance.json  — aggregates for the dashboard
    events.json       — list of deployed events (for the drilldown)
    snapshots/<id>.json — per-event detail with picks + (if graded) results
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from pipeline.db import connect

log = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent.parent / "site" / "public" / "data"


class _Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def _write(filename: str, payload) -> None:
    path = OUT_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, cls=_Encoder, ensure_ascii=False, indent=2)
    log.info("wrote %s (%d bytes)", path.relative_to(OUT_DIR.parent.parent), path.stat().st_size)


# ─────────────────────────────────── upcoming.json


def _fight_payload(cur, fight: dict) -> dict:
    """Common shape used in upcoming + snapshot detail."""
    cur.execute(
        """
        SELECT fighter_id, name, nickname, weight_class,
               record_wins, record_losses, record_draws,
               current_elo_standard, current_elo_modified
          FROM fighters WHERE fighter_id IN (%s, %s)
        """,
        (fight["fighter_a_id"], fight["fighter_b_id"]),
    )
    fighters = {f["fighter_id"]: f for f in cur.fetchall()}
    a = fighters.get(fight["fighter_a_id"])
    b = fighters.get(fight["fighter_b_id"])

    cur.execute(
        """
        SELECT prediction_id, predicted_winner_id, win_probability,
               model_version, snapshot_at, was_correct, actual_winner_id, graded_at
          FROM predictions
         WHERE fight_id = %s AND is_locked = TRUE
         ORDER BY snapshot_at DESC
         LIMIT 1
        """,
        (fight["fight_id"],),
    )
    pred = cur.fetchone()

    return {
        "fight_id": fight["fight_id"],
        "card_order": fight.get("card_order"),
        "weight_class": fight.get("weight_class"),
        "is_title_fight": fight.get("is_title_fight"),
        "winner_id": fight.get("winner_id"),
        "method": fight.get("method"),
        "round": fight.get("round"),
        "fighter_a": a,
        "fighter_b": b,
        "prediction": pred,
    }


def export_upcoming(cur) -> None:
    """Next deployed-or-imminent event + its locked predictions."""
    cur.execute(
        """
        SELECT event_id, espn_event_id, name, location, event_date, deployed_at
          FROM events
         WHERE event_date >= CURRENT_DATE
           AND EXISTS (
                 SELECT 1 FROM predictions p
                  WHERE p.event_id = events.event_id
                    AND p.is_locked = TRUE
               )
         ORDER BY event_date ASC
         LIMIT 1
        """
    )
    event = cur.fetchone()
    if not event:
        log.info("No upcoming event with locked predictions — writing empty upcoming.json")
        _write("upcoming.json", {"event": None, "fights": []})
        return

    cur.execute(
        """
        SELECT fight_id, fighter_a_id, fighter_b_id, winner_id,
               method, round, time, weight_class, is_title_fight, card_order
          FROM fights
         WHERE event_id = %s AND is_cancelled = FALSE
         ORDER BY card_order ASC NULLS LAST, fight_id ASC
        """,
        (event["event_id"],),
    )
    fights = cur.fetchall()
    payload = {
        "event": event,
        "fights": [_fight_payload(cur, f) for f in fights],
    }
    _write("upcoming.json", payload)


# ─────────────────────────────────── performance.json


def export_performance(cur) -> None:
    """Aggregate stats for the dashboard. Only counts locked picks on
    deployed events that have been graded."""
    cur.execute(
        """
        SELECT COUNT(*) FILTER (WHERE was_correct IS NOT NULL) AS graded,
               COUNT(*) FILTER (WHERE was_correct = TRUE)      AS correct,
               COUNT(*) FILTER (WHERE was_correct = FALSE)     AS wrong,
               AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END) FILTER (WHERE was_correct IS NOT NULL) AS accuracy
          FROM predictions p
          JOIN events e ON e.event_id = p.event_id
         WHERE p.is_locked = TRUE
           AND e.deployed_at IS NOT NULL
        """
    )
    totals = cur.fetchone()

    # Per-event breakdown for the drilldown table
    cur.execute(
        """
        SELECT e.event_id, e.name, e.event_date,
               COUNT(*) AS n_picks,
               COUNT(*) FILTER (WHERE p.was_correct = TRUE)  AS n_correct,
               COUNT(*) FILTER (WHERE p.was_correct = FALSE) AS n_wrong,
               COUNT(*) FILTER (WHERE p.was_correct IS NULL) AS n_pending
          FROM events e
          JOIN predictions p ON p.event_id = e.event_id
         WHERE p.is_locked = TRUE
           AND e.deployed_at IS NOT NULL
         GROUP BY e.event_id, e.name, e.event_date
         ORDER BY e.event_date DESC
        """
    )
    per_event = cur.fetchall()

    # Calibration: bucket predicted probabilities into 10 bins, compare
    # to actual win rate. Probabilities are stored as winner-side confidence
    # (>= 0.5), so all rows live in [0.5, 1.0].
    cur.execute(
        """
        WITH binned AS (
            SELECT
                LEAST(FLOOR((win_probability - 0.5) * 20)::int, 9) AS bin,
                was_correct::int AS correct_int
              FROM predictions p
              JOIN events e ON e.event_id = p.event_id
             WHERE p.is_locked = TRUE
               AND p.was_correct IS NOT NULL
               AND e.deployed_at IS NOT NULL
        )
        SELECT bin,
               COUNT(*)                    AS n,
               AVG(correct_int)::float     AS actual_win_rate,
               0.5 + (bin + 0.5) / 20.0    AS bucket_center
          FROM binned
         GROUP BY bin
         ORDER BY bin
        """
    )
    calibration = cur.fetchall()

    payload = {
        "totals": totals,
        "per_event": per_event,
        "calibration": calibration,
    }
    _write("performance.json", payload)


# ─────────────────────────────────── events.json + snapshots


def export_events_index(cur) -> None:
    cur.execute(
        """
        SELECT event_id, espn_event_id, name, location, event_date, deployed_at
          FROM events
         WHERE deployed_at IS NOT NULL
         ORDER BY event_date DESC
        """
    )
    _write("events.json", cur.fetchall())


def export_snapshot(cur, event_id: int) -> None:
    cur.execute(
        "SELECT event_id, espn_event_id, name, location, event_date, deployed_at FROM events WHERE event_id = %s",
        (event_id,),
    )
    event = cur.fetchone()
    if not event:
        return
    cur.execute(
        """
        SELECT fight_id, fighter_a_id, fighter_b_id, winner_id,
               method, round, time, weight_class, is_title_fight, card_order
          FROM fights
         WHERE event_id = %s AND is_cancelled = FALSE
         ORDER BY card_order ASC NULLS LAST, fight_id ASC
        """,
        (event_id,),
    )
    fights = cur.fetchall()
    payload = {
        "event": event,
        "fights": [_fight_payload(cur, f) for f in fights],
    }
    _write(f"snapshots/{event_id}.json", payload)


# ─────────────────────────────────── orchestrator


def export_all() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn, conn.cursor() as cur:
        export_upcoming(cur)
        export_performance(cur)
        export_events_index(cur)
        # Write per-event snapshots for all deployed events
        cur.execute("SELECT event_id FROM events WHERE deployed_at IS NOT NULL")
        for row in cur.fetchall():
            export_snapshot(cur, row["event_id"])
