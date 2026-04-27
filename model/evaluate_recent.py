import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime

def evaluate():
    conn = psycopg2.connect('postgresql://ufc_user:ufc_password@localhost:5432/ufc_predictor')
    cur = conn.cursor(cursor_factory=DictCursor)

    # Get recent completed fights
    cur.execute("""
        SELECT e.name as event_name, e.event_date, f.fight_id, f.winner_id,
               p1.predicted_winner_id as v1_pred, p1.win_probability as v1_prob,
               p2.predicted_winner_id as v2_pred, p2.win_probability as v2_prob,
               fa.name as fighter_a, fb.name as fighter_b
        FROM fights f
        JOIN events e ON f.event_id = e.event_id
        JOIN fighters fa ON f.fighter_a_id = fa.fighter_id
        JOIN fighters fb ON f.fighter_b_id = fb.fighter_id
        LEFT JOIN predictions p1 ON f.fight_id = p1.fight_id AND p1.model_version = 'v1'
        LEFT JOIN predictions p2 ON f.fight_id = p2.fight_id AND p2.model_version = 'v2'
        WHERE e.event_date >= CURRENT_DATE - INTERVAL '60 days' 
          AND e.event_date < CURRENT_DATE
          AND f.winner_id IS NOT NULL
        ORDER BY e.event_date DESC
    """)
    res = cur.fetchall()

    if not res:
        print("No completed fights in the last 60 days.")
    else:
        print(f"\n--- Evaluation on Last 60 Days ({len(res)} Fights) ---")
        v1_correct = sum(1 for r in res if r['winner_id'] == r['v1_pred'])
        v2_correct = sum(1 for r in res if r['winner_id'] == r['v2_pred'])
        print(f"V1 Accuracy: {v1_correct}/{len(res)} ({v1_correct/len(res)*100:.1f}%)")
        print(f"V2 Accuracy: {v2_correct}/{len(res)} ({v2_correct/len(res)*100:.1f}%)")

    # Get upcoming fights
    cur.execute("""
        SELECT e.name as event_name, e.event_date, f.fight_id,
               p1.predicted_winner_id as v1_pred, p1.win_probability as v1_prob,
               p2.predicted_winner_id as v2_pred, p2.win_probability as v2_prob,
               fa.name as fighter_a, fb.name as fighter_b,
               fa.fighter_id as fa_id, fb.fighter_id as fb_id
        FROM fights f
        JOIN events e ON f.event_id = e.event_id
        JOIN fighters fa ON f.fighter_a_id = fa.fighter_id
        JOIN fighters fb ON f.fighter_b_id = fb.fighter_id
        LEFT JOIN predictions p1 ON f.fight_id = p1.fight_id AND p1.model_version = 'v1'
        LEFT JOIN predictions p2 ON f.fight_id = p2.fight_id AND p2.model_version = 'v2'
        WHERE e.event_date >= CURRENT_DATE
          AND f.is_cancelled = FALSE
        ORDER BY e.event_date ASC
        LIMIT 10
    """)
    upcoming = cur.fetchall()
    
    if upcoming:
        print(f"\n--- Predictions for Upcoming Event: {upcoming[0]['event_name']} ---")
        for r in upcoming:
            v1_winner = r['fighter_a'] if r['v1_pred'] == r['fa_id'] else r['fighter_b']
            v2_winner = r['fighter_a'] if r['v2_pred'] == r['fa_id'] else r['fighter_b']
            
            # Formatted output
            print(f"{r['fighter_a']} vs {r['fighter_b']}")
            print(f"  V1: {v1_winner} ({r['v1_prob']*100:.1f}%)")
            print(f"  V2: {v2_winner} ({r['v2_prob']*100:.1f}%)")
            if v1_winner != v2_winner:
                print(f"  *** MODELS DISAGREE ***")
            print()

if __name__ == "__main__":
    evaluate()
