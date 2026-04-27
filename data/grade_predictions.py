"""
Grade ungraded predictions by comparing predicted_winner_id against the
actual fight winner_id.

Usage:
    python -m data.grade_predictions            # grade all pending
    python -m data.grade_predictions --dry-run   # preview without writing

Can also be triggered via the API: POST /predictions/grade
"""

import logging
import sys
import os
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.loaders.postgres_loader import PostgresLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def grade_predictions(db_url=None, dry_run=False):
    """
    Find all predictions where was_correct IS NULL, look up the corresponding
    fight's winner_id, and set was_correct + actual_winner_id accordingly.

    Returns a summary dict: { graded, correct, wrong, skipped, already_graded }
    """
    loader = PostgresLoader(db_url=db_url)
    summary = {"graded": 0, "correct": 0, "wrong": 0, "skipped": 0, "already_graded": 0}

    with loader.get_connection() as conn:
        with conn.cursor() as cur:
            # Count already-graded predictions for context
            cur.execute("SELECT COUNT(*) AS cnt FROM predictions WHERE was_correct IS NOT NULL")
            summary["already_graded"] = cur.fetchone()["cnt"]

            # Fetch ungraded predictions joined with their fight's winner
            cur.execute("""
                SELECT p.prediction_id,
                       p.predicted_winner_id,
                       p.fight_id,
                       f.winner_id
                  FROM predictions p
                  JOIN fights f ON f.fight_id = p.fight_id
                 WHERE p.was_correct IS NULL
            """)
            rows = cur.fetchall()

            if not rows:
                logging.info("No ungraded predictions found — nothing to do.")
                return summary

            logging.info(f"Found {len(rows)} ungraded prediction(s) to evaluate.")

            for row in rows:
                winner_id = row["winner_id"]

                if winner_id is None:
                    # Fight hasn't happened yet (or result not scraped)
                    summary["skipped"] += 1
                    continue

                is_correct = row["predicted_winner_id"] == winner_id

                if dry_run:
                    verdict = "CORRECT" if is_correct else "WRONG"
                    logging.info(
                        f"  [DRY RUN] prediction {row['prediction_id']}: "
                        f"predicted={row['predicted_winner_id']} actual={winner_id} → {verdict}"
                    )
                else:
                    cur.execute(
                        """
                        UPDATE predictions
                           SET was_correct = %(was_correct)s,
                               actual_winner_id = %(actual_winner_id)s
                         WHERE prediction_id = %(prediction_id)s
                        """,
                        {
                            "was_correct": is_correct,
                            "actual_winner_id": winner_id,
                            "prediction_id": row["prediction_id"],
                        },
                    )

                summary["graded"] += 1
                if is_correct:
                    summary["correct"] += 1
                else:
                    summary["wrong"] += 1

            if not dry_run:
                conn.commit()
                logging.info(f"Committed {summary['graded']} grade(s) to database.")

    logging.info(
        f"Grading complete — {summary['graded']} graded "
        f"({summary['correct']} correct, {summary['wrong']} wrong), "
        f"{summary['skipped']} skipped (fight not yet decided), "
        f"{summary['already_graded']} previously graded."
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grade UFC fight predictions")
    parser.add_argument("--dry-run", action="store_true", help="Preview grades without writing to DB")
    args = parser.parse_args()
    grade_predictions(dry_run=args.dry_run)
