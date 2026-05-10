-- Mark which events the model was actually deployed for.
-- Predictions belonging to non-deployed events are treated as backtest data
-- and excluded from live performance metrics (grading, model leaderboard).
ALTER TABLE events ADD COLUMN deployed_at TIMESTAMPTZ;
