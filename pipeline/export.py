"""Write the JSON files the static site reads.

Outputs into site/public/data/:
    upcoming.json     — next event + locked predictions for it (one row
                        per (fight, model))
    performance.json  — { models: [...], by_model: { <name>: {totals, per_event,
                        calibration, timeseries} } }
    events.json       — list of deployed events (for the drilldown)
    snapshots/<id>.json — per-event detail with picks grouped by model
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from pipeline.db import connect
from pipeline.models import all_names
from pipeline.train import load_meta

log = logging.getLogger(__name__)

OUT_DIR = Path(__file__).resolve().parent.parent / "site" / "public" / "data"

# Picks on these fights never count toward the dashboard:
#   * cancelled fights (pulled from the card)
#   * fights that resolved without a winner — No Contest, Draws
# A fight is "void" if it falls into either bucket. The clauses below are
# spliced into every performance/snapshot query so void fights drop out of
# both the graded pool AND the n_pending count.
_VOID_FIGHT_SQL = (
    "f.is_cancelled = FALSE "
    "AND (f.winner_id IS NOT NULL OR f.method IS NULL)"
)


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


# ─────────────────────────────────── helpers


def _all_locked_model_versions(cur) -> list[str]:
    """All distinct model_versions that have ANY locked prediction on a
    deployed event. The performance dashboard groups by these — includes
    historical model_versions like 'v1' / 'v2' from before the registry
    existed, so historic comparisons are visible."""
    cur.execute(
        """
        SELECT DISTINCT model_version
          FROM predictions p
          JOIN events e ON e.event_id = p.event_id
         WHERE p.is_locked = TRUE
           AND e.deployed_at IS NOT NULL
         ORDER BY model_version
        """
    )
    return [r["model_version"] for r in cur.fetchall()]


def _models_for_event(cur, event_id: int) -> list[str]:
    """Model versions that have a locked prediction specifically for this
    event. Used by upcoming.json + per-event snapshots so the model tabs
    never include models that didn't pick this card."""
    cur.execute(
        """
        SELECT DISTINCT model_version
          FROM predictions
         WHERE event_id = %s AND is_locked = TRUE
         ORDER BY model_version
        """,
        (event_id,),
    )
    return [r["model_version"] for r in cur.fetchall()]


def _fights_for_event(cur, event_id: int) -> list[dict]:
    # Snapshot pages still render NC/Draw fights so the user can SEE the
    # outcome; only is_cancelled is hidden. The accuracy filters below are
    # the ones that drop NC/Draw from totals + n_pending.
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
    return cur.fetchall()


def _predictions_for_fight(cur, fight_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT prediction_id, model_version, predicted_winner_id, win_probability,
               snapshot_at, was_correct, actual_winner_id, graded_at
          FROM predictions
         WHERE fight_id = %s AND is_locked = TRUE
         ORDER BY model_version
        """,
        (fight_id,),
    )
    return cur.fetchall()


def _fighter_lookup(cur, ids: set[int]) -> dict[int, dict]:
    if not ids:
        return {}
    cur.execute(
        """
        SELECT fighter_id, name, nickname, weight_class,
               record_wins, record_losses, record_draws,
               current_elo_standard, current_elo_modified
          FROM fighters WHERE fighter_id = ANY(%s)
        """,
        (list(ids),),
    )
    return {f["fighter_id"]: f for f in cur.fetchall()}


def _build_fight_payload(fight: dict, fighters: dict[int, dict], preds: list[dict]) -> dict:
    return {
        "fight_id": fight["fight_id"],
        "card_order": fight.get("card_order"),
        "weight_class": fight.get("weight_class"),
        "is_title_fight": fight.get("is_title_fight"),
        "winner_id": fight.get("winner_id"),
        "method": fight.get("method"),
        "round": fight.get("round"),
        "fighter_a": fighters.get(fight["fighter_a_id"]),
        "fighter_b": fighters.get(fight["fighter_b_id"]),
        # All locked predictions across models — the site picks one to render
        # via the dashboard model selector. The "primary" prediction (for the
        # default model) is also exposed for back-compat.
        "predictions": preds,
        "prediction": preds[0] if preds else None,
    }


def _event_payload(cur, event: dict) -> dict:
    fights = _fights_for_event(cur, event["event_id"])
    fighter_ids = {f["fighter_a_id"] for f in fights} | {f["fighter_b_id"] for f in fights}
    fighters = _fighter_lookup(cur, fighter_ids)
    fight_payloads = []
    for f in fights:
        preds = _predictions_for_fight(cur, f["fight_id"])
        fight_payloads.append(_build_fight_payload(f, fighters, preds))
    return {"event": event, "fights": fight_payloads}


# ─────────────────────────────────── upcoming.json


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
        _write("upcoming.json", {"event": None, "fights": [], "models": [], "default_model": None})
        return
    payload = _event_payload(cur, event)
    payload["models"] = _models_for_event(cur, event["event_id"])
    payload["default_model"] = _default_model(payload["models"])
    _write("upcoming.json", payload)


def _default_model(versions: list[str]) -> str | None:
    """Pick which model the dashboard shows by default.

    Prefer a currently-registered model that has at least one graded pick.
    Fall back to any registered model, then to any version with graded
    picks, then to whatever exists. This means the user sees real numbers
    by default even when a fresh model has been added but hasn't run yet.
    """
    if not versions:
        return None
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT model_version, COUNT(*) FILTER (WHERE was_correct IS NOT NULL) AS graded
              FROM predictions p
              JOIN fights f ON f.fight_id = p.fight_id
              JOIN events e ON e.event_id = p.event_id
             WHERE p.is_locked
               AND e.deployed_at IS NOT NULL
               AND """ + _VOID_FIGHT_SQL + """
             GROUP BY model_version
            """
        )
        graded_counts = {r["model_version"]: r["graded"] for r in cur.fetchall()}

    registered = all_names()
    # 1. Registered model with graded data
    for n in registered:
        if n in versions and graded_counts.get(n, 0) > 0:
            return n
    # 2. Any version with graded data — prefer the most-graded
    graded_versions = [v for v in versions if graded_counts.get(v, 0) > 0]
    if graded_versions:
        return max(graded_versions, key=lambda v: graded_counts[v])
    # 3. Registered model (even if no graded data yet)
    for n in registered:
        if n in versions:
            return n
    # 4. Fallback
    return versions[-1]


# ─────────────────────────────────── performance.json


def _performance_for_model(cur, model_version: str) -> dict:
    # Every query joins through fights with the _VOID_FIGHT_SQL guard so
    # picks on fights that were pulled from the card or resolved with no
    # winner (NC, Draw) never count as picks at all. Otherwise those rows
    # stay was_correct=NULL forever and inflate the "pending" count for
    # events that already happened.
    cur.execute(
        """
        SELECT COUNT(*) FILTER (WHERE was_correct IS NOT NULL) AS graded,
               COUNT(*) FILTER (WHERE was_correct = TRUE)      AS correct,
               COUNT(*) FILTER (WHERE was_correct = FALSE)     AS wrong,
               AVG(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END) FILTER (WHERE was_correct IS NOT NULL) AS accuracy,
               AVG(
                 -LN(GREATEST(LEAST(
                   CASE WHEN was_correct THEN win_probability ELSE 1 - win_probability END,
                 0.999), 0.001))
               ) FILTER (WHERE was_correct IS NOT NULL) AS log_loss
          FROM predictions p
          JOIN fights f ON f.fight_id = p.fight_id
          JOIN events e ON e.event_id = p.event_id
         WHERE p.is_locked = TRUE
           AND p.model_version = %s
           AND e.deployed_at IS NOT NULL
           AND """ + _VOID_FIGHT_SQL + """
        """,
        (model_version,),
    )
    totals = cur.fetchone()

    cur.execute(
        """
        SELECT e.event_id, e.name, e.event_date,
               COUNT(*) AS n_picks,
               COUNT(*) FILTER (WHERE p.was_correct = TRUE)  AS n_correct,
               COUNT(*) FILTER (WHERE p.was_correct = FALSE) AS n_wrong,
               COUNT(*) FILTER (WHERE p.was_correct IS NULL) AS n_pending
          FROM events e
          JOIN predictions p ON p.event_id = e.event_id
          JOIN fights f ON f.fight_id = p.fight_id
         WHERE p.is_locked = TRUE
           AND p.model_version = %s
           AND e.deployed_at IS NOT NULL
           AND """ + _VOID_FIGHT_SQL + """
         GROUP BY e.event_id, e.name, e.event_date
         ORDER BY e.event_date DESC
        """,
        (model_version,),
    )
    per_event = cur.fetchall()

    cur.execute(
        """
        WITH binned AS (
            SELECT
                LEAST(FLOOR((win_probability - 0.5) * 20)::int, 9) AS bin,
                was_correct::int AS correct_int
              FROM predictions p
              JOIN fights f ON f.fight_id = p.fight_id
              JOIN events e ON e.event_id = p.event_id
             WHERE p.is_locked = TRUE
               AND p.was_correct IS NOT NULL
               AND p.model_version = %s
               AND e.deployed_at IS NOT NULL
               AND """ + _VOID_FIGHT_SQL + """
        )
        SELECT bin,
               COUNT(*)                    AS n,
               AVG(correct_int)::float     AS actual_win_rate,
               0.5 + (bin + 0.5) / 20.0    AS bucket_center
          FROM binned
         GROUP BY bin
         ORDER BY bin
        """,
        (model_version,),
    )
    calibration = cur.fetchall()

    timeseries = []
    running_picks = 0
    running_correct = 0
    for e in sorted(per_event, key=lambda r: r["event_date"]):
        graded_in_event = e["n_correct"] + e["n_wrong"]
        if graded_in_event == 0:
            continue
        running_picks += graded_in_event
        running_correct += e["n_correct"]
        timeseries.append({
            "event_id": e["event_id"],
            "event_date": e["event_date"],
            "event_name": e["name"],
            "n_correct_so_far": running_correct,
            "n_picks_so_far": running_picks,
            "accuracy_so_far": running_correct / running_picks,
        })

    return {
        "totals": totals,
        "per_event": per_event,
        "calibration": calibration,
        "timeseries": timeseries,
        "meta": load_meta(model_version),  # None for historical model_versions
    }


def export_performance(cur) -> None:
    # The performance dashboard reports aggregate stats — it only makes
    # sense for models that have at least one graded pick. Models with
    # locked-but-ungraded picks still surface on the home/event pages.
    all_versions = _all_locked_model_versions(cur)
    by_model = {v: _performance_for_model(cur, v) for v in all_versions}
    graded_versions = [v for v in all_versions if by_model[v]["totals"]["graded"] > 0]
    payload = {
        "models": graded_versions,
        "default_model": _default_model(graded_versions),
        "by_model": {v: by_model[v] for v in graded_versions},
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
    payload = _event_payload(cur, event)
    payload["models"] = _models_for_event(cur, event_id)
    payload["default_model"] = _default_model(payload["models"])
    _write(f"snapshots/{event_id}.json", payload)


# ─────────────────────────────────── orchestrator


def export_all() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn, conn.cursor() as cur:
        export_upcoming(cur)
        export_performance(cur)
        export_events_index(cur)
        cur.execute("SELECT event_id FROM events WHERE deployed_at IS NOT NULL")
        for row in cur.fetchall():
            export_snapshot(cur, row["event_id"])
