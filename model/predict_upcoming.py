import os
import sys
import pandas as pd
import psycopg2
from psycopg2.extras import DictCursor
import xgboost as xgb
from dotenv import load_dotenv

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FEATURES = [
    "elo_std_pre_a", "elo_mod_pre_a", "elo_std_pre_b", "elo_mod_pre_b",
    "elo_diff_std", "elo_diff_mod",
    "wins_a", "losses_a", "wins_b", "losses_b",
    "is_title_fight"
]

def load_latest_elo(cur, fighter_id):
    cur.execute("""
        SELECT elo_standard, elo_modified 
        FROM elo_ratings 
        WHERE fighter_id = %s 
        ORDER BY rating_id DESC 
        LIMIT 1
    """, (fighter_id,))
    res = cur.fetchone()
    if res:
        return res['elo_standard'], res['elo_modified']
    return 1500.0, 1500.0  # Safe defaults

def load_v2_stats(cur, fighter_id):
    """Calculates the historical offensive and defensive stats for a single fighter."""
    cur.execute("""
        SELECT 
            COALESCE(SUM(sig_strikes_landed), 0) as sig_str_landed,
            COALESCE(SUM(sig_strikes_attempted), 0) as sig_str_att,
            COALESCE(SUM(takedowns_landed), 0) as td_landed,
            COALESCE(SUM(takedowns_attempted), 0) as td_att,
            COALESCE(SUM(advances + submissions), 0) as grap_agg,
            COUNT(DISTINCT fight_id) as hist_fights
        FROM fighter_stats
        WHERE fighter_id = %s
    """, (fighter_id,))
    off = cur.fetchone()
    
    cur.execute("""
        SELECT COALESCE(SUM(opp_fs.sig_strikes_landed), 0) as sig_str_absorbed
        FROM fighter_stats opp_fs
        JOIN fights past_f ON opp_fs.fight_id = past_f.fight_id
        WHERE opp_fs.fighter_id != %s 
        AND (past_f.fighter_a_id = %s OR past_f.fighter_b_id = %s)
    """, (fighter_id, fighter_id, fighter_id))
    def_stats = cur.fetchone()

    fights = off['hist_fights'] if off['hist_fights'] > 0 else 1 # Avoid division by zero
    
    return {
        "str_acc": off['sig_str_landed'] / off['sig_str_att'] if off['sig_str_att'] > 0 else 0.0,
        "str_vol": off['sig_str_landed'] / fights,
        "td_acc": off['td_landed'] / off['td_att'] if off['td_att'] > 0 else 0.0,
        "grap_agg": off['grap_agg'] / fights,
        "str_def": def_stats['sig_str_absorbed'] / fights
    }

def run_predictions(model_version="v1"):
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
    db_url = os.environ.get('DATABASE_URL', 'postgresql://ufc_user:ufc_password@localhost:5432/ufc_predictor')
    
    print("Connecting to live Postgres analytics pipeline...")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=DictCursor)
    
    # Find all upcoming and recent fights (last 60 days) to backfill leaderboard data
    cur.execute("""
        SELECT f.fight_id, f.fighter_a_id, f.fighter_b_id, f.is_title_fight
        FROM fights f
        JOIN events e ON f.event_id = e.event_id
        WHERE e.event_date >= CURRENT_DATE - INTERVAL '60 days'
          AND f.fighter_a_id IS NOT NULL 
          AND f.fighter_b_id IS NOT NULL
          AND f.is_cancelled = FALSE
    """)
    upcoming_fights = cur.fetchall()
    
    if not upcoming_fights:
        print("No upcoming events logged inside the framework instance.")
        return

    print(f"Loaded {len(upcoming_fights)} upcoming fight vectors. Structuring parameter dataframes...")
    
    X_rows = []
    metadata = []
    
    for fight in upcoming_fights:
        # Extract features
        elo_std_a, elo_mod_a = load_latest_elo(cur, fight['fighter_a_id'])
        elo_std_b, elo_mod_b = load_latest_elo(cur, fight['fighter_b_id'])
        
        row = {
            "elo_std_pre_a": float(elo_std_a),
            "elo_mod_pre_a": float(elo_mod_a),
            "elo_std_pre_b": float(elo_std_b),
            "elo_mod_pre_b": float(elo_mod_b),
            "elo_diff_std": float(elo_std_a) - float(elo_std_b),
            "elo_diff_mod": float(elo_mod_a) - float(elo_mod_b),
            "is_title_fight": int(1) if fight['is_title_fight'] else int(0)
        }
        
        if model_version == "v2":
            stats_a = load_v2_stats(cur, fight['fighter_a_id'])
            stats_b = load_v2_stats(cur, fight['fighter_b_id'])
            row.update({
                "a_str_acc": stats_a['str_acc'],
                "a_str_vol": stats_a['str_vol'],
                "a_td_acc": stats_a['td_acc'],
                "a_grap_agg": stats_a['grap_agg'],
                "a_str_def": stats_a['str_def'],
                
                "b_str_acc": stats_b['str_acc'],
                "b_str_vol": stats_b['str_vol'],
                "b_td_acc": stats_b['td_acc'],
                "b_grap_agg": stats_b['grap_agg'],
                "b_str_def": stats_b['str_def'],
                
                "diff_str_acc": stats_a['str_acc'] - stats_b['str_acc'],
                "diff_str_vol": stats_a['str_vol'] - stats_b['str_vol'],
                "diff_td_acc": stats_a['td_acc'] - stats_b['td_acc'],
                "diff_grap_agg": stats_a['grap_agg'] - stats_b['grap_agg'],
                "diff_str_def": stats_a['str_def'] - stats_b['str_def']
            })
            
        X_rows.append(row)
        metadata.append(fight)
        
    if model_version == "v2":
        from model.training.train import FEATURES_V2
        df = pd.DataFrame(X_rows)[FEATURES_V2]
    else:
        from model.training.train import FEATURES_V1
        df = pd.DataFrame(X_rows)[FEATURES_V1]
    
    # Evaluate bounds via XGBoost Binary model
    artifact_path = os.path.join(os.path.dirname(__file__), 'artifacts', f'xgb_{model_version}.json')
    if not os.path.exists(artifact_path):
        print(f"CRITICAL: Failed to locate XGBoost model bin at {artifact_path}")
        return
        
    print(f"Loading {model_version} surrogate into memory...")
    model = xgb.XGBClassifier()
    model.load_model(artifact_path)
    
    print("Initiating mass predict_proba vectors...")
    probas = model.predict_proba(df)[:, 1]
    
    # Store results safely wiping old duplicates
    for i, fight in enumerate(metadata):
        prob = float(probas[i])
        # Win probabilities reflect Fighter A's probability. Let's map who specifically wins mathematically:
        predicted_winner_id = fight['fighter_a_id'] if prob > 0.50 else fight['fighter_b_id']
        # Normalized confidence for specific winner
        normalized_prob = prob if prob > 0.50 else (1 - prob)
        
        cur.execute("DELETE FROM predictions WHERE fight_id = %s AND model_version = %s", (fight['fight_id'], model_version))
        cur.execute("""
            INSERT INTO predictions (fight_id, predicted_winner_id, win_probability, model_version)
            VALUES (%s, %s, %s, %s)
        """, (fight['fight_id'], predicted_winner_id, normalized_prob, model_version))
        
    conn.commit()
    print(f"XGBoost predictions perfectly deployed and structured into PostgreSQL ({len(upcoming_fights)} matches).")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run UFC fight predictions")
    parser.add_argument("--model-version", default="v1", help="Model version to use (default: v1)")
    args = parser.parse_args()
    run_predictions(model_version=args.model_version)
