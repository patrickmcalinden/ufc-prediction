import os
import sys
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

# Add parent dir to path to import properly
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from model.features.elo_config import ELO_CONFIG
from model.features.elo import update_standard_elo, update_modified_elo


def run_elo_pipeline(incremental=False):
    """
    Compute and store Elo ratings for all completed fights.

    If incremental=True:
      - Only processes fights newer than the latest fight_id in elo_ratings
      - Seeds each fighter's starting rating from their most recent elo_ratings row
      - Appends new rows (no truncate)

    If incremental=False (default/legacy):
      - Truncates elo_ratings and replays everything from scratch
    """
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set in .env")
        return

    print(f"Connecting to database to run Elo pipeline (incremental={incremental})...")
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            ratings_std = {}
            ratings_mod = {}

            if incremental:
                # Find the latest fight_id already processed
                cur.execute("SELECT COALESCE(MAX(fight_id), 0) AS max_fid FROM elo_ratings")
                max_processed_fid = cur.fetchone()['max_fid']
                print(f"Incremental mode: last processed fight_id = {max_processed_fid}")

                # Seed ratings from the latest elo_ratings row per fighter
                cur.execute("""
                    SELECT DISTINCT ON (fighter_id)
                           fighter_id, elo_standard, elo_modified
                    FROM elo_ratings
                    ORDER BY fighter_id, rating_id DESC
                """)
                for row in cur.fetchall():
                    fid = row['fighter_id']
                    ratings_std[fid] = float(row['elo_standard'])
                    ratings_mod[fid] = float(row['elo_modified'])
                print(f"Seeded ratings for {len(ratings_std)} existing fighters.")

                # Only load NEW fights
                cur.execute("""
                    SELECT fight_id, fight_date, fighter_a_id, fighter_b_id, winner_id
                    FROM fights
                    WHERE winner_id IS NOT NULL AND fight_id > %s
                    ORDER BY fight_date ASC, fight_id ASC
                """, (max_processed_fid,))
                fights = cur.fetchall()

                if not fights:
                    print("No new fights to process — ELO is up to date.")
                    return
                print(f"Found {len(fights)} new fight(s) to process.")

            else:
                # Elo is chronologically path-dependent. 
                # We wipe the table to guarantee idempotency and no orphans.
                print("Wiping existing elo_ratings for clean chronological run...")
                cur.execute("TRUNCATE elo_ratings RESTART IDENTITY;")
                
                # Load all completed fights sorted chronologically
                cur.execute("""
                    SELECT fight_id, fight_date, fighter_a_id, fighter_b_id, winner_id 
                    FROM fights 
                    WHERE winner_id IS NOT NULL 
                    ORDER BY fight_date ASC, fight_id ASC
                """)
                fights = cur.fetchall()
                print(f"Loaded {len(fights)} completed fights.")

            elo_rows = []

            for fight in fights:
                fight_id = fight['fight_id']
                fight_date = fight['fight_date']
                a_id = fight['fighter_a_id']
                b_id = fight['fighter_b_id']
                winner_id = fight['winner_id']

                # Safety check against bad data
                if winner_id not in (a_id, b_id):
                    continue

                # Get pre-fight ratings
                a_std = ratings_std.get(a_id, ELO_CONFIG["starting_rating"])
                b_std = ratings_std.get(b_id, ELO_CONFIG["starting_rating"])
                a_mod = ratings_mod.get(a_id, ELO_CONFIG["starting_rating"])
                b_mod = ratings_mod.get(b_id, ELO_CONFIG["starting_rating"])

                pre_a_std, pre_b_std = a_std, b_std
                pre_a_mod, pre_b_mod = a_mod, b_mod

                # Calculate standard and modified Elo shifts
                if winner_id == a_id:
                    a_std, b_std = update_standard_elo(pre_a_std, pre_b_std, ELO_CONFIG["base_k"])
                    a_mod, b_mod = update_modified_elo(pre_a_mod, pre_b_mod, ELO_CONFIG)
                elif winner_id == b_id:
                    b_std, a_std = update_standard_elo(pre_b_std, pre_a_std, ELO_CONFIG["base_k"])
                    b_mod, a_mod = update_modified_elo(pre_b_mod, pre_a_mod, ELO_CONFIG)

                # Store post-fight global state
                ratings_std[a_id] = a_std
                ratings_std[b_id] = b_std
                ratings_mod[a_id] = a_mod
                ratings_mod[b_id] = b_mod

                # Stage Fighter A row
                elo_rows.append((
                    fight_id, a_id,
                    pre_a_std, a_std,
                    pre_a_mod, a_mod,
                    fight_date
                ))
                # Stage Fighter B row
                elo_rows.append((
                    fight_id, b_id,
                    pre_b_std, b_std,
                    pre_b_mod, b_mod,
                    fight_date
                ))

            # Batch insert into elo_ratings
            print("Inserting Elo ratings into database...")
            insert_query = """
                INSERT INTO elo_ratings (
                    fight_id, fighter_id, 
                    elo_standard_pre, elo_standard, 
                    elo_modified_pre, elo_modified,
                    rating_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            cur.executemany(insert_query, elo_rows)
            conn.commit()

            mode_label = "incrementally" if incremental else "from scratch"
            print(f"Successfully processed Elo ratings {mode_label} for {len(fights)} fights and {len(ratings_mod)} unique fighters.")

            # Sanity Check Output
            top_fighters = sorted(ratings_mod.items(), key=lambda item: item[1], reverse=True)[:10]
            print("\n--- TOP 10 FIGHTERS BY MODIFIED ELO ---")
            for rank, (fid, elo) in enumerate(top_fighters, 1):
                cur.execute("SELECT name FROM fighters WHERE fighter_id = %s", (fid,))
                res = cur.fetchone()
                name = res['name'] if res else fid
                print(f"{rank}. {name} - {elo:.1f}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Elo Pipeline")
    parser.add_argument("--full", action="store_true", help="Full rebuild (truncate + replay all)")
    args = parser.parse_args()
    run_elo_pipeline(incremental=not args.full)
