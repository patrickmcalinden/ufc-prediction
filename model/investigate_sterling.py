import psycopg2
from psycopg2.extras import DictCursor

def investigate():
    conn = psycopg2.connect('postgresql://ufc_user:ufc_password@localhost:5432/ufc_predictor')
    cur = conn.cursor(cursor_factory=DictCursor)

    cur.execute("""
        SELECT e.event_name, e.event_date, f.fight_id, 
               fa.name as fa_name, fa.fighter_id as fa_id,
               fb.name as fb_name, fb.fighter_id as fb_id,
               f.winner_id,
               p1.predicted_winner_id as v1_pred, p1.win_probability as v1_prob,
               p2.predicted_winner_id as v2_pred, p2.win_probability as v2_prob
        FROM fights f 
        JOIN events e ON f.event_id = e.event_id
        JOIN fighters fa ON f.fighter_a_id = fa.fighter_id 
        JOIN fighters fb ON f.fighter_b_id = fb.fighter_id 
        LEFT JOIN predictions p1 ON f.fight_id = p1.fight_id AND p1.model_version = 'v1' 
        LEFT JOIN predictions p2 ON f.fight_id = p2.fight_id AND p2.model_version = 'v2' 
        WHERE (fa.name ILIKE '%Sterling%' OR fb.name ILIKE '%Sterling%' 
               OR fa.name ILIKE '%Zalal%' OR fb.name ILIKE '%Zalal%')
          AND e.event_date >= CURRENT_DATE - INTERVAL '60 days'
    """)
    res = cur.fetchall()
    for r in res:
        print(dict(r))

    # We also want to see their stats to understand why V2 chose the way it did.
    for r in res:
        fa_id = r['fa_id']
        fb_id = r['fb_id']
        
        for fid in (fa_id, fb_id):
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
            """, (fid,))
            off = cur.fetchone()
            
            cur.execute("""
                SELECT COALESCE(SUM(opp_fs.sig_strikes_landed), 0) as sig_str_absorbed
                FROM fighter_stats opp_fs
                JOIN fights past_f ON opp_fs.fight_id = past_f.fight_id
                WHERE opp_fs.fighter_id != %s 
                AND (past_f.fighter_a_id = %s OR past_f.fighter_b_id = %s)
            """, (fid, fid, fid))
            def_stats = cur.fetchone()

            fights = off['hist_fights'] if off['hist_fights'] > 0 else 1
            
            print(f"Stats for Fighter ID {fid}:")
            print(f"  str_acc: {off['sig_str_landed'] / off['sig_str_att'] if off['sig_str_att'] > 0 else 0.0:.3f}")
            print(f"  str_vol: {off['sig_str_landed'] / fights:.3f}")
            print(f"  td_acc: {off['td_landed'] / off['td_att'] if off['td_att'] > 0 else 0.0:.3f}")
            print(f"  grap_agg: {off['grap_agg'] / fights:.3f}")
            print(f"  str_def: {def_stats['sig_str_absorbed'] / fights:.3f}")

if __name__ == "__main__":
    investigate()
