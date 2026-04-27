import psycopg
from psycopg.rows import dict_row

conn = psycopg.connect('postgresql://ufc_user:ufc_password@localhost:5432/ufc_predictor', row_factory=dict_row)
cur = conn.cursor()

# Check tonight's event fights
cur.execute("""
    SELECT f.fight_id, f.fight_date, f.winner_id, f.method,
           fa.name as fighter_a, fb.name as fighter_b,
           e.name as event_name
    FROM fights f
    JOIN fighters fa ON fa.fighter_id = f.fighter_a_id
    JOIN fighters fb ON fb.fighter_id = f.fighter_b_id
    JOIN events e ON e.event_id = f.event_id
    WHERE f.fight_date >= '2026-04-25'
    ORDER BY f.fight_date, f.fight_id
""")
for row in cur.fetchall():
    w = row["winner_id"] if row["winner_id"] else "NULL"
    m = row["method"] if row["method"] else "--"
    print(f"fight_id={row['fight_id']} | {row['fight_date']} | winner={w} | {m}")
    print(f"  {row['fighter_a']} vs {row['fighter_b']} | {row['event_name']}")

conn.close()
