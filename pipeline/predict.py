"""Generate locked predictions for an upcoming event and write them to
`predictions` with is_locked=TRUE. Also stamps events.deployed_at.

Snapshots are sacred: the unique index ux_predictions_locked prevents
double-inserts for (fight_id, model_version). ON CONFLICT DO NOTHING is
the safe default; pass force=True to replace.
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from pipeline.db import connect
from pipeline.features import FEATURES, features_for_fight
from pipeline.train import ARTIFACT_PATH, current_model_version, load as load_model

log = logging.getLogger(__name__)


def _resolve_event(cur, event_id: int | None) -> dict | None:
    """If event_id is given, fetch it. Otherwise pick the next upcoming
    non-cancelled event that has at least one un-decided fight."""
    if event_id is not None:
        cur.execute(
            "SELECT event_id, espn_event_id, name, event_date FROM events WHERE event_id = %s",
            (event_id,),
        )
        return cur.fetchone()

    cur.execute(
        """
        SELECT e.event_id, e.espn_event_id, e.name, e.event_date
          FROM events e
         WHERE e.event_date >= CURRENT_DATE
           AND EXISTS (
                 SELECT 1 FROM fights f
                  WHERE f.event_id = e.event_id
                    AND f.is_cancelled = FALSE
                    AND f.winner_id IS NULL
               )
         ORDER BY e.event_date ASC
         LIMIT 1
        """
    )
    return cur.fetchone()


def predict_event(event_id: int | None = None, model_version: str | None = None, force: bool = False) -> dict:
    """Generate locked snapshots for one event.

    Args:
        event_id: explicit event_id; if None, picks the next upcoming event.
        model_version: tag stored on each prediction row. Defaults to the
            artifact filename when not given.
        force: replace any existing locked snapshots for this event +
            model_version.

    Returns summary dict.
    """
    model = load_model()
    model_version = model_version or current_model_version()

    with connect() as conn, conn.cursor() as cur:
        event = _resolve_event(cur, event_id)
        if not event:
            log.warning("No upcoming event found to predict")
            return {"event": None, "predictions": 0}

        log.info("Predicting event %s — %s (%s)", event["event_id"], event["name"], event["event_date"])

        cur.execute(
            """
            SELECT fight_id, fighter_a_id, fighter_b_id, is_title_fight
              FROM fights
             WHERE event_id = %s
               AND is_cancelled = FALSE
               AND fighter_a_id IS NOT NULL
               AND fighter_b_id IS NOT NULL
            """,
            (event["event_id"],),
        )
        fights = cur.fetchall()
        if not fights:
            log.warning("Event %s has no eligible fights", event["event_id"])
            return {"event": event["event_id"], "predictions": 0}

        # Build feature matrix in one go, then batch-predict
        rows = [features_for_fight(cur, f["fighter_a_id"], f["fighter_b_id"], f["is_title_fight"]) for f in fights]
        X = pd.DataFrame(rows)[FEATURES]
        probas_a = model.predict_proba(X)[:, 1]

        if force:
            cur.execute(
                "DELETE FROM predictions WHERE event_id = %s AND model_version = %s AND is_locked = TRUE",
                (event["event_id"], model_version),
            )

        inserted = 0
        for fight, row, p_a in zip(fights, rows, probas_a):
            p_a = float(p_a)
            winner_id = fight["fighter_a_id"] if p_a >= 0.5 else fight["fighter_b_id"]
            conf = p_a if p_a >= 0.5 else (1.0 - p_a)

            cur.execute(
                """
                INSERT INTO predictions (
                    fight_id, event_id, predicted_winner_id, win_probability,
                    model_version, model_artifact, features_snapshot,
                    snapshot_at, is_locked
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), TRUE
                )
                ON CONFLICT (fight_id, model_version) WHERE is_locked
                    DO NOTHING
                """,
                (
                    fight["fight_id"],
                    event["event_id"],
                    winner_id,
                    conf,
                    model_version,
                    ARTIFACT_PATH.name,
                    json.dumps(row),
                ),
            )
            inserted += cur.rowcount

        # Mark event as deployed — anchor for the grader and dashboard filter
        cur.execute(
            "UPDATE events SET deployed_at = COALESCE(deployed_at, NOW()) WHERE event_id = %s",
            (event["event_id"],),
        )
        conn.commit()

    log.info("Inserted %d locked prediction(s) for event %s", inserted, event["event_id"])
    return {
        "event": dict(event),
        "model_version": model_version,
        "fights": len(fights),
        "inserted": inserted,
    }
