import pandas as pd
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

def build_feature_matrix_v2() -> pd.DataFrame:
    """
    Builds the feature matrix for the V2 model.
    Includes V1 baseline features (ELO) + historical averages derived from fighter_stats.
    """
    load_dotenv()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set in .env")
        
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://")
    engine = create_engine(db_url)

    # The query builds historical averages for fighter A and fighter B
    # by aggregating all fights prior to the current fight_date.
    query = """
    WITH historical_stats AS (
        SELECT 
            f.fight_id,
            f.fight_date,
            f.fighter_a_id,
            f.fighter_b_id,
            f.winner_id,
            f.is_title_fight,
            ea.elo_standard_pre AS elo_std_pre_a,
            ea.elo_modified_pre AS elo_mod_pre_a,
            eb.elo_standard_pre AS elo_std_pre_b,
            eb.elo_modified_pre AS elo_mod_pre_b,
            
            -- Fighter A Historical Offense
            (SELECT SUM(sig_strikes_landed) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_a_id AND past_f.fight_date < f.fight_date) as a_sig_str_landed,
            (SELECT SUM(sig_strikes_attempted) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_a_id AND past_f.fight_date < f.fight_date) as a_sig_str_att,
            (SELECT SUM(takedowns_landed) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_a_id AND past_f.fight_date < f.fight_date) as a_td_landed,
            (SELECT SUM(takedowns_attempted) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_a_id AND past_f.fight_date < f.fight_date) as a_td_att,
            (SELECT SUM(advances + submissions) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_a_id AND past_f.fight_date < f.fight_date) as a_grappling_agg,
            (SELECT COUNT(DISTINCT past_f.fight_id) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_a_id AND past_f.fight_date < f.fight_date) as a_hist_fights,
            
            -- Fighter A Historical Defense (what opponents landed on them)
            (SELECT SUM(opp_fs.sig_strikes_landed) FROM fighter_stats opp_fs JOIN fights past_f ON opp_fs.fight_id = past_f.fight_id WHERE past_f.fight_date < f.fight_date AND opp_fs.fighter_id != f.fighter_a_id AND (past_f.fighter_a_id = f.fighter_a_id OR past_f.fighter_b_id = f.fighter_a_id)) as a_sig_str_absorbed,

            -- Fighter B Historical Offense
            (SELECT SUM(sig_strikes_landed) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_b_id AND past_f.fight_date < f.fight_date) as b_sig_str_landed,
            (SELECT SUM(sig_strikes_attempted) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_b_id AND past_f.fight_date < f.fight_date) as b_sig_str_att,
            (SELECT SUM(takedowns_landed) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_b_id AND past_f.fight_date < f.fight_date) as b_td_landed,
            (SELECT SUM(takedowns_attempted) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_b_id AND past_f.fight_date < f.fight_date) as b_td_att,
            (SELECT SUM(advances + submissions) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_b_id AND past_f.fight_date < f.fight_date) as b_grappling_agg,
            (SELECT COUNT(DISTINCT past_f.fight_id) FROM fighter_stats fs JOIN fights past_f ON fs.fight_id = past_f.fight_id WHERE fs.fighter_id = f.fighter_b_id AND past_f.fight_date < f.fight_date) as b_hist_fights,
            
            -- Fighter B Historical Defense
            (SELECT SUM(opp_fs.sig_strikes_landed) FROM fighter_stats opp_fs JOIN fights past_f ON opp_fs.fight_id = past_f.fight_id WHERE past_f.fight_date < f.fight_date AND opp_fs.fighter_id != f.fighter_b_id AND (past_f.fighter_a_id = f.fighter_b_id OR past_f.fighter_b_id = f.fighter_b_id)) as b_sig_str_absorbed

        FROM fights f
        JOIN elo_ratings ea ON ea.fight_id = f.fight_id AND ea.fighter_id = f.fighter_a_id
        JOIN elo_ratings eb ON eb.fight_id = f.fight_id AND eb.fighter_id = f.fighter_b_id
        -- For training, only look at completed fights. For predictions, we look at all
        -- We will filter winner_id later depending on if we are predicting or training
    )
    SELECT * FROM historical_stats
    """
    
    print("Executing V2 feature SQL query (this might take a moment due to subqueries)...")
    df = pd.read_sql_query(query, engine)
    print(f"Extracted raw data of shape {df.shape}")

    # Safely handle nulls from fighters with 0 prior fights
    df.fillna(0, inplace=True)

    # -- Calculate V1 features --
    df["elo_diff_std"] = df["elo_std_pre_a"] - df["elo_std_pre_b"]
    df["elo_diff_mod"] = df["elo_mod_pre_a"] - df["elo_mod_pre_b"]
    
    # -- Calculate V2 features (Averages and Percentages) --
    
    import numpy as np
    
    # Fighter A
    df["a_str_acc"] = (df["a_sig_str_landed"] / df["a_sig_str_att"]).replace([np.inf, -np.inf], np.nan).fillna(0)
    df["a_str_vol"] = (df["a_sig_str_landed"] / df["a_hist_fights"]).replace([np.inf, -np.inf], np.nan).fillna(0)
    df["a_td_acc"] = (df["a_td_landed"] / df["a_td_att"]).replace([np.inf, -np.inf], np.nan).fillna(0)
    df["a_grap_agg"] = (df["a_grappling_agg"] / df["a_hist_fights"]).replace([np.inf, -np.inf], np.nan).fillna(0)
    df["a_str_def"] = (df["a_sig_str_absorbed"] / df["a_hist_fights"]).replace([np.inf, -np.inf], np.nan).fillna(0)

    # Fighter B
    df["b_str_acc"] = (df["b_sig_str_landed"] / df["b_sig_str_att"]).replace([np.inf, -np.inf], np.nan).fillna(0)
    df["b_str_vol"] = (df["b_sig_str_landed"] / df["b_hist_fights"]).replace([np.inf, -np.inf], np.nan).fillna(0)
    df["b_td_acc"] = (df["b_td_landed"] / df["b_td_att"]).replace([np.inf, -np.inf], np.nan).fillna(0)
    df["b_grap_agg"] = (df["b_grappling_agg"] / df["b_hist_fights"]).replace([np.inf, -np.inf], np.nan).fillna(0)
    df["b_str_def"] = (df["b_sig_str_absorbed"] / df["b_hist_fights"]).replace([np.inf, -np.inf], np.nan).fillna(0)

    # Feature differentials
    df["diff_str_acc"] = df["a_str_acc"] - df["b_str_acc"]
    df["diff_str_vol"] = df["a_str_vol"] - df["b_str_vol"]
    df["diff_td_acc"] = df["a_td_acc"] - df["b_td_acc"]
    df["diff_grap_agg"] = df["a_grap_agg"] - df["b_grap_agg"]
    df["diff_str_def"] = df["a_str_def"] - df["b_str_def"]

    return df

def get_v2_training_matrix():
    """Returns the matrix filtered for training and mirrored"""
    df = build_feature_matrix_v2()
    
    # Only keep completed fights for training
    df = df[df['winner_id'].notnull() & (df['winner_id'] != 0)].copy()
    
    df["label"] = (df["winner_id"] == df["fighter_a_id"]).astype(int)
    
    print("Constructing mirrored dataset...")
    df_mirrored = df.copy()
    
    swap_pairs = [
        ('fighter_a_id', 'fighter_b_id'),
        ('elo_std_pre_a', 'elo_std_pre_b'),
        ('elo_mod_pre_a', 'elo_mod_pre_b'),
        ('a_str_acc', 'b_str_acc'),
        ('a_str_vol', 'b_str_vol'),
        ('a_td_acc', 'b_td_acc'),
        ('a_grap_agg', 'b_grap_agg'),
        ('a_str_def', 'b_str_def'),
    ]
    
    for a_feat, b_feat in swap_pairs:
        temp = df_mirrored[a_feat].copy()
        df_mirrored[a_feat] = df_mirrored[b_feat]
        df_mirrored[b_feat] = temp

    df_mirrored["elo_diff_std"] = -df_mirrored["elo_diff_std"]
    df_mirrored["elo_diff_mod"] = -df_mirrored["elo_diff_mod"]
    df_mirrored["diff_str_acc"] = -df_mirrored["diff_str_acc"]
    df_mirrored["diff_str_vol"] = -df_mirrored["diff_str_vol"]
    df_mirrored["diff_td_acc"] = -df_mirrored["diff_td_acc"]
    df_mirrored["diff_grap_agg"] = -df_mirrored["diff_grap_agg"]
    df_mirrored["diff_str_def"] = -df_mirrored["diff_str_def"]

    df_mirrored["label"] = (df_mirrored["winner_id"] == df_mirrored["fighter_a_id"]).astype(int)

    df_combined = pd.concat([df, df_mirrored], ignore_index=True)
    df_combined = df_combined.sort_values(by="fight_date").reset_index(drop=True)
    
    print(f"Final symmetric V2 feature matrix shape: {df_combined.shape}")
    return df_combined

if __name__ == "__main__":
    df = get_v2_training_matrix()
    print("Sample:\n", df[['fight_id', 'a_str_vol', 'b_str_vol', 'diff_str_vol', 'label']].head(10))
