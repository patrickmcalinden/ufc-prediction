"""
Backfill predictions for fights that joined the card after predict_upcoming
last ran (typically late replacements or new bouts added mid-week).

Uses the *pre-event* ELO stored in elo_ratings (elo_standard_pre /
elo_modified_pre) so the prediction reflects the model's state at the
time the fight would have been scheduled, not after-the-fact knowledge.

Usage:
    python -m model.backfill_predictions --fight-ids 10321 10323 10325
    python -m model.backfill_predictions --fight-ids 10321 --model-version v2
"""

import os
import sys
import argparse
import psycopg2
from psycopg2.extras import DictCursor
import pandas as pd
import xgboost as xgb
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.predict_upcoming import load_v2_stats


def load_pre_event_elo(cur, fighter_id, fight_id):
    """Return (elo_standard_pre, elo_modified_pre) for the fighter on the given fight.

    Prefers the elo_ratings row that the ELO pipeline wrote for this exact fight
    (which stores pre-fight values explicitly). Falls back to the most recent
    rating row with rating_id strictly less than that fight's row — i.e. the
    fighter's state going *into* the fight.
    """
    cur.execute(
        """
        SELECT elo_standard_pre, elo_modified_pre
          FROM elo_ratings
         WHERE fighter_id = %s AND fight_id = %s
         LIMIT 1
        """,
        (fighter_id, fight_id),
    )
    row = cur.fetchone()
    if row and row["elo_standard_pre"] is not None:
        return float(row["elo_standard_pre"]), float(row["elo_modified_pre"])

    # Fallback: latest rating strictly before this fight
    cur.execute(
        """
        SELECT elo_standard, elo_modified
          FROM elo_ratings
         WHERE fighter_id = %s
           AND rating_id < COALESCE(
                 (SELECT rating_id FROM elo_ratings WHERE fighter_id = %s AND fight_id = %s LIMIT 1),
                 (SELECT MAX(rating_id) FROM elo_ratings WHERE fighter_id = %s) + 1
               )
         ORDER BY rating_id DESC
         LIMIT 1
        """,
        (fighter_id, fighter_id, fight_id, fighter_id),
    )
    row = cur.fetchone()
    if row:
        return float(row["elo_standard"]), float(row["elo_modified"])
    return 1500.0, 1500.0


def backfill(fight_ids, model_version="v1"):
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
    db_url = os.environ.get('DATABASE_URL', 'postgresql://ufc_user:ufc_password@localhost:5432/ufc_predictor')

    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute(
        """
        SELECT f.fight_id, f.fighter_a_id, f.fighter_b_id, f.is_title_fight
          FROM fights f
         WHERE f.fight_id = ANY(%s)
           AND f.is_cancelled = FALSE
        """,
        (list(fight_ids),),
    )
    fights = cur.fetchall()
    if not fights:
        print("No matching fights to backfill.")
        return

    X_rows = []
    metadata = []
    for f in fights:
        elo_std_a, elo_mod_a = load_pre_event_elo(cur, f['fighter_a_id'], f['fight_id'])
        elo_std_b, elo_mod_b = load_pre_event_elo(cur, f['fighter_b_id'], f['fight_id'])

        row = {
            "elo_std_pre_a": elo_std_a,
            "elo_mod_pre_a": elo_mod_a,
            "elo_std_pre_b": elo_std_b,
            "elo_mod_pre_b": elo_mod_b,
            "elo_diff_std": elo_std_a - elo_std_b,
            "elo_diff_mod": elo_mod_a - elo_mod_b,
            "is_title_fight": int(1) if f['is_title_fight'] else int(0),
        }

        if model_version == "v2":
            stats_a = load_v2_stats(cur, f['fighter_a_id'])
            stats_b = load_v2_stats(cur, f['fighter_b_id'])
            row.update({
                "a_str_acc": stats_a['str_acc'], "a_str_vol": stats_a['str_vol'],
                "a_td_acc": stats_a['td_acc'], "a_grap_agg": stats_a['grap_agg'],
                "a_str_def": stats_a['str_def'],
                "b_str_acc": stats_b['str_acc'], "b_str_vol": stats_b['str_vol'],
                "b_td_acc": stats_b['td_acc'], "b_grap_agg": stats_b['grap_agg'],
                "b_str_def": stats_b['str_def'],
                "diff_str_acc": stats_a['str_acc'] - stats_b['str_acc'],
                "diff_str_vol": stats_a['str_vol'] - stats_b['str_vol'],
                "diff_td_acc": stats_a['td_acc'] - stats_b['td_acc'],
                "diff_grap_agg": stats_a['grap_agg'] - stats_b['grap_agg'],
                "diff_str_def": stats_a['str_def'] - stats_b['str_def'],
            })

        X_rows.append(row)
        metadata.append(f)

    if model_version == "v2":
        from model.training.train import FEATURES_V2
        df = pd.DataFrame(X_rows)[FEATURES_V2]
    else:
        from model.training.train import FEATURES_V1
        df = pd.DataFrame(X_rows)[FEATURES_V1]

    artifact_path = os.path.join(os.path.dirname(__file__), 'artifacts', f'xgb_{model_version}.json')
    model = xgb.XGBClassifier()
    model.load_model(artifact_path)
    probas = model.predict_proba(df)[:, 1]

    inserted = 0
    for i, f in enumerate(metadata):
        prob = float(probas[i])
        predicted_winner_id = f['fighter_a_id'] if prob > 0.50 else f['fighter_b_id']
        normalized_prob = prob if prob > 0.50 else (1 - prob)

        cur.execute(
            "DELETE FROM predictions WHERE fight_id = %s AND model_version = %s",
            (f['fight_id'], model_version),
        )
        cur.execute(
            """
            INSERT INTO predictions (fight_id, predicted_winner_id, win_probability, model_version)
            VALUES (%s, %s, %s, %s)
            """,
            (f['fight_id'], predicted_winner_id, normalized_prob, model_version),
        )
        inserted += 1
        print(f"  fight {f['fight_id']} ({model_version}): predicted {predicted_winner_id} @ {normalized_prob:.3f}")

    conn.commit()
    print(f"Backfilled {inserted} prediction(s) for model {model_version}.")
    cur.close()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill predictions for late-add fights using pre-event ELO")
    parser.add_argument("--fight-ids", type=int, nargs="+", required=True, help="Fight IDs to backfill")
    parser.add_argument("--model-version", default="all", help="v1, v2, or 'all' (default: all)")
    args = parser.parse_args()

    versions = ["v1", "v2"] if args.model_version == "all" else [args.model_version]
    for v in versions:
        print(f"\n=== Backfilling with model {v} ===")
        backfill(args.fight_ids, model_version=v)
