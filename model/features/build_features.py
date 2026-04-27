import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

def build_feature_matrix() -> pd.DataFrame:
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set in .env")
        
    # We enforce pure psycopg compatibility for pandas sqlalchemy interface
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://")
    engine = create_engine(db_url)

    query = """
    SELECT
        f.fight_id,
        f.fight_date,
        f.fighter_a_id,
        f.fighter_b_id,
        f.winner_id,
        ea.elo_standard_pre   AS elo_std_pre_a,
        ea.elo_modified_pre   AS elo_mod_pre_a,
        eb.elo_standard_pre   AS elo_std_pre_b,
        eb.elo_modified_pre   AS elo_mod_pre_b,
        f.is_title_fight
    FROM fights f
    JOIN elo_ratings ea ON ea.fight_id = f.fight_id AND ea.fighter_id = f.fighter_a_id
    JOIN elo_ratings eb ON eb.fight_id = f.fight_id AND eb.fighter_id = f.fighter_b_id
    WHERE f.winner_id IS NOT NULL
    ORDER BY f.fight_date ASC
    """
    
    print("Executing master feature SQL query...")
    df = pd.read_sql_query(query, engine)
    
    print(f"Extracted feature matrix of shape {df.shape}")
    
    # Calculate feature deltas
    df["elo_diff_std"] = df["elo_std_pre_a"] - df["elo_std_pre_b"]
    df["elo_diff_mod"] = df["elo_mod_pre_a"] - df["elo_mod_pre_b"]
    
    # Construct binary label: 1 if A wins, else 0
    df["label"] = (df["winner_id"] == df["fighter_a_id"]).astype(int)
    
    # Mirror dataset so positional bias (A vs B) does not skew the model
    print("Constructing mirrored dataset...")
    df_mirrored = df.copy()
    
    # Swap A and B features
    swap_pairs = [
        ('fighter_a_id', 'fighter_b_id'),
        ('elo_std_pre_a', 'elo_std_pre_b'),
        ('elo_mod_pre_a', 'elo_mod_pre_b'),
    ]
    
    for a_feat, b_feat in swap_pairs:
        temp = df_mirrored[a_feat].copy()
        df_mirrored[a_feat] = df_mirrored[b_feat]
        df_mirrored[b_feat] = temp

    # Invert differentials and recalculate mirrored label
    df_mirrored["elo_diff_std"] = -df_mirrored["elo_diff_std"]
    df_mirrored["elo_diff_mod"] = -df_mirrored["elo_diff_mod"]
    df_mirrored["label"] = (df_mirrored["winner_id"] == df_mirrored["fighter_a_id"]).astype(int)

    # Append mirrored rows and dynamically sort by date to re-serialize data temporally
    df_combined = pd.concat([df, df_mirrored], ignore_index=True)
    df_combined = df_combined.sort_values(by="fight_date").reset_index(drop=True)
    
    # Asserts validity
    assert df_combined.isnull().sum().sum() == 0, "Feature matrix contains NaN values"
    
    print(f"Final symmetric feature matrix shape: {df_combined.shape}")
    return df_combined

if __name__ == "__main__":
    df = build_feature_matrix()
    print("Sample:\n", df.head())
