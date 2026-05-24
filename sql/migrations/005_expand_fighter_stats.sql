-- 005_expand_fighter_stats.sql
-- Expand the fighter_stats table with full ESPN per-fight stat columns.
-- The original table (from 001) had only 10 stat columns; ESPN provides ~37.

-- Drop the old (empty/unused) table and recreate with full column set
DROP TABLE IF EXISTS fighter_stats;

CREATE TABLE fighter_stats (
  stat_id                  SERIAL PRIMARY KEY,
  fight_id                 INT REFERENCES fights(fight_id),
  fighter_id               INT REFERENCES fighters(fighter_id),
  espn_event_id            VARCHAR(64),

  -- Aggregate Striking
  knockdowns               INT,
  sig_strikes_landed       INT,
  sig_strikes_attempted    INT,
  total_strikes_landed     INT,
  total_strikes_attempted  INT,

  -- Distance Striking
  sd_head_landed           INT,
  sd_head_attempted        INT,
  sd_body_landed           INT,
  sd_body_attempted        INT,
  sd_leg_landed            INT,
  sd_leg_attempted         INT,

  -- Clinch Striking
  sc_head_landed           INT,
  sc_head_attempted        INT,
  sc_body_landed           INT,
  sc_body_attempted        INT,
  sc_leg_landed            INT,
  sc_leg_attempted         INT,

  -- Ground Striking
  sg_head_landed           INT,
  sg_head_attempted        INT,
  sg_body_landed           INT,
  sg_body_attempted        INT,
  sg_leg_landed            INT,
  sg_leg_attempted         INT,

  -- Target Breakdown Percentages
  pct_head                 NUMERIC(5,2),
  pct_body                 NUMERIC(5,2),
  pct_leg                  NUMERIC(5,2),

  -- Grappling
  takedowns_landed         INT,
  takedowns_attempted      INT,
  takedown_slams           INT,
  takedown_accuracy        NUMERIC(5,2),
  slam_rate                NUMERIC(5,2),
  submissions              INT,
  reversals                INT,

  -- Positional Advances
  advances                 INT,
  advance_to_half_guard    INT,
  advance_to_back          INT,
  advance_to_mount         INT,
  advance_to_side          INT,

  created_at               TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE (fight_id, fighter_id)
);

CREATE INDEX idx_fighter_stats_fighter ON fighter_stats(fighter_id);
CREATE INDEX idx_fighter_stats_fight   ON fighter_stats(fight_id);
