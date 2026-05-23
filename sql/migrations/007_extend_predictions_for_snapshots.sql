-- 007_extend_predictions_for_snapshots.sql
-- Extend predictions to support immutable pre-event snapshots that the
-- performance dashboard reads. See REWRITE_PLAN.md §4.

ALTER TABLE predictions ADD COLUMN IF NOT EXISTS event_id INT REFERENCES events(event_id);
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS snapshot_at TIMESTAMPTZ;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS graded_at TIMESTAMPTZ;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS model_artifact VARCHAR(128);

-- Backfill event_id for any existing predictions
UPDATE predictions p
   SET event_id = f.event_id
  FROM fights f
 WHERE p.fight_id = f.fight_id
   AND p.event_id IS NULL;

-- Backfill graded_at for any already-graded rows
UPDATE predictions
   SET graded_at = created_at
 WHERE was_correct IS NOT NULL
   AND graded_at IS NULL;

-- One locked prediction per fight per model version
CREATE UNIQUE INDEX IF NOT EXISTS ux_predictions_locked
  ON predictions (fight_id, model_version)
  WHERE is_locked = TRUE;

CREATE INDEX IF NOT EXISTS idx_predictions_event ON predictions(event_id);
