-- 010_backfill_locked_snapshots.sql
-- Treat any pre-existing prediction belonging to a deployed event as a
-- locked snapshot, so historical performance data survives the rewrite.
-- Predictions on non-deployed events stay unlocked (backtest data).

UPDATE predictions p
   SET is_locked = TRUE,
       snapshot_at = COALESCE(snapshot_at, created_at)
  FROM events e
 WHERE p.event_id = e.event_id
   AND e.deployed_at IS NOT NULL
   AND p.is_locked = FALSE;
