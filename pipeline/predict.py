"""Generate locked predictions for an upcoming event, per named model.

For each named model in pipeline.models.MODELS, this writes one snapshot
row to `predictions` per fight, with `model_version = model.name`. The
unique index ux_predictions_locked (fight_id, model_version) prevents
duplicates; ON CONFLICT DO NOTHING is the safe default, --force replaces.

Also stamps events.deployed_at on the first locked snapshot for the event.
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from pipeline.db import connect
from pipeline.features import features_for_existing_fight, features_for_fight
from pipeline.models import MODELS, get as get_model
from pipeline.train import _artifact_path, load as load_model

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


def _predict_for_model(cur, event: dict, fights: list[dict], feature_rows: list[dict],
                       model_name: str, force: bool) -> int:
    cfg = get_model(model_name)
    model = load_model(model_name)

    X = pd.DataFrame(feature_rows)[cfg.features]
    probas_a = model.predict_proba(X)[:, 1]

    if force:
        cur.execute(
            "DELETE FROM predictions WHERE event_id = %s AND model_version = %s AND is_locked = TRUE",
            (event["event_id"], model_name),
        )

    inserted = 0
    for fight, row, p_a in zip(fights, feature_rows, probas_a):
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
                model_name,
                _artifact_path(model_name).name,
                json.dumps({k: row[k] for k in cfg.features}),
            ),
        )
        inserted += cur.rowcount

    return inserted


def predict_event(
    event_id: int | None = None,
    models: list[str] | None = None,
    force: bool = False,
) -> dict:
    """Generate locked snapshots for one event, across one or more named models.

    Args:
        event_id: explicit event_id; if None, picks the next upcoming event.
        models: list of model names; defaults to every registered model.
        force: replace any existing locked snapshots for this event +
            model_version (per model).

    Returns summary dict.
    """
    model_names = models or list(MODELS)

    with connect() as conn, conn.cursor() as cur:
        event = _resolve_event(cur, event_id)
        if not event:
            log.warning("No upcoming event found to predict")
            return {"event": None, "by_model": {}}

        log.info("Predicting event %s — %s (%s) | models=%s",
                 event["event_id"], event["name"], event["event_date"], model_names)

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
            return {"event": event["event_id"], "by_model": {}}

        # Build the full feature row once per fight — every model takes a
        # subset of the same dict, so there's no point repeating the DB work.
        feature_rows = [
            features_for_fight(cur, f["fighter_a_id"], f["fighter_b_id"], f["is_title_fight"])
            for f in fights
        ]

        results: dict[str, int] = {}
        for name in model_names:
            try:
                results[name] = _predict_for_model(cur, event, fights, feature_rows, name, force)
                log.info("[%s] Inserted %d locked prediction(s)", name, results[name])
            except FileNotFoundError as e:
                log.warning("[%s] Skipped — %s", name, e)
                results[name] = 0

        # Mark event as deployed — anchor for the grader and dashboard filter
        cur.execute(
            "UPDATE events SET deployed_at = COALESCE(deployed_at, NOW()) WHERE event_id = %s",
            (event["event_id"],),
        )
        conn.commit()

    return {
        "event": dict(event),
        "fights": len(fights),
        "by_model": results,
    }


def predict_missing(models: list[str] | None = None) -> dict:
    """Backfill locked predictions for fights on deployed events that don't yet
    have one for a given model.

    Use case: a card mutated after the pre-event lock (late add, short-notice
    replacement). Those fights end up in `fights` but never in `predictions`.
    This fills the gap so every fight on every deployed event has a pick for
    every registered model.

    Features come from `features_for_existing_fight`, which uses stored
    pre-Elo + date-filtered historical stats for already-completed fights and
    falls back to current Elo for not-yet-fought rows. Either way, what we
    record is honest about the information available before the bell, so
    backfilled picks don't poison accuracy stats.
    """
    model_names = models or list(MODELS)
    summary: dict[str, int] = {}

    with connect() as conn, conn.cursor() as cur:
        for name in model_names:
            try:
                cfg = get_model(name)
                model = load_model(name)
            except FileNotFoundError as e:
                log.warning("[%s] Skipped — %s", name, e)
                summary[name] = 0
                continue

            cur.execute(
                """
                SELECT f.fight_id, f.event_id
                  FROM fights f
                  JOIN events e ON e.event_id = f.event_id
                 WHERE e.deployed_at IS NOT NULL
                   AND f.is_cancelled = FALSE
                   AND f.fighter_a_id IS NOT NULL
                   AND f.fighter_b_id IS NOT NULL
                   AND NOT EXISTS (
                         SELECT 1 FROM predictions p
                          WHERE p.fight_id = f.fight_id
                            AND p.model_version = %s
                            AND p.is_locked = TRUE
                       )
                """,
                (name,),
            )
            missing = cur.fetchall()
            if not missing:
                summary[name] = 0
                continue

            log.info("[%s] backfilling %d missing locked prediction(s)", name, len(missing))

            count = 0
            for row in missing:
                fight_id = row["fight_id"]
                event_id = row["event_id"]
                features = features_for_existing_fight(cur, fight_id)
                X = pd.DataFrame([features])[cfg.features]
                p_a = float(model.predict_proba(X)[:, 1][0])

                cur.execute(
                    "SELECT fighter_a_id, fighter_b_id FROM fights WHERE fight_id = %s",
                    (fight_id,),
                )
                f = cur.fetchone()
                winner_id = f["fighter_a_id"] if p_a >= 0.5 else f["fighter_b_id"]
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
                        fight_id, event_id, winner_id, conf, name,
                        _artifact_path(name).name,
                        json.dumps({k: features[k] for k in cfg.features}),
                    ),
                )
                count += cur.rowcount
            summary[name] = count

        conn.commit()

    log.info("predict_missing done: %s", summary)
    return summary
