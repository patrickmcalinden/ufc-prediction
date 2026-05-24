"""Grade locked predictions for deployed events whose fights now have winners.

Idempotent: only touches rows where was_correct IS NULL.
"""

from __future__ import annotations

import logging

from pipeline.db import connect

log = logging.getLogger(__name__)


def grade_predictions(dry_run: bool = False) -> dict:
    summary = {"graded": 0, "correct": 0, "wrong": 0, "skipped_no_winner": 0}

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.prediction_id,
                   p.predicted_winner_id,
                   p.fight_id,
                   f.winner_id
              FROM predictions p
              JOIN fights f ON f.fight_id = p.fight_id
              JOIN events e ON e.event_id = f.event_id
             WHERE p.was_correct IS NULL
               AND p.is_locked = TRUE
               AND e.deployed_at IS NOT NULL
            """
        )
        rows = cur.fetchall()

        if not rows:
            log.info("No ungraded locked predictions on deployed events.")
            return summary

        log.info("Found %d ungraded prediction(s)", len(rows))

        for r in rows:
            winner = r["winner_id"]
            if winner is None:
                summary["skipped_no_winner"] += 1
                continue
            is_correct = r["predicted_winner_id"] == winner
            if dry_run:
                log.info("  [dry] %s: pred=%s actual=%s → %s",
                         r["prediction_id"], r["predicted_winner_id"], winner,
                         "CORRECT" if is_correct else "WRONG")
            else:
                cur.execute(
                    """
                    UPDATE predictions
                       SET was_correct = %s,
                           actual_winner_id = %s,
                           graded_at = NOW()
                     WHERE prediction_id = %s
                    """,
                    (is_correct, winner, r["prediction_id"]),
                )
            summary["graded"] += 1
            summary["correct" if is_correct else "wrong"] += 1

        if not dry_run:
            conn.commit()

    log.info("Grading done: %s", summary)
    return summary
