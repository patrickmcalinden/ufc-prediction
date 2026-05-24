-- 008_add_current_elo_to_fighters.sql
-- Denormalize each fighter's current Elo so the predictions page can join
-- in O(1) instead of doing DISTINCT ON over elo_ratings per fighter.
-- Refreshed by pipeline.elo_update after every incremental Elo run.

ALTER TABLE fighters ADD COLUMN IF NOT EXISTS current_elo_standard NUMERIC(8,2);
ALTER TABLE fighters ADD COLUMN IF NOT EXISTS current_elo_modified NUMERIC(8,2);
ALTER TABLE fighters ADD COLUMN IF NOT EXISTS current_elo_updated_at TIMESTAMPTZ;

-- One-time backfill from the latest elo_ratings row per fighter
WITH latest AS (
    SELECT DISTINCT ON (fighter_id)
           fighter_id, elo_standard, elo_modified
      FROM elo_ratings
     ORDER BY fighter_id, rating_id DESC
)
UPDATE fighters f
   SET current_elo_standard = latest.elo_standard,
       current_elo_modified = latest.elo_modified,
       current_elo_updated_at = NOW()
  FROM latest
 WHERE latest.fighter_id = f.fighter_id;
