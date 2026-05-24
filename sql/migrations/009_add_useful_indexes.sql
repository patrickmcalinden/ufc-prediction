-- 009_add_useful_indexes.sql
-- Indexes the pipeline and export queries actually hit.

CREATE INDEX IF NOT EXISTS idx_fights_fight_date ON fights(fight_date);
CREATE INDEX IF NOT EXISTS idx_fights_event ON fights(event_id);
CREATE INDEX IF NOT EXISTS idx_elo_ratings_fighter_recent
  ON elo_ratings(fighter_id, rating_id DESC);
