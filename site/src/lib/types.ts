// Types matching the JSON written by pipeline/export.py.
// Single source of truth for the contract between pipeline and site.

export interface Fighter {
  fighter_id: number;
  name: string;
  nickname: string | null;
  weight_class: string | null;
  record_wins: number;
  record_losses: number;
  record_draws: number;
  current_elo_standard: number | null;
  current_elo_modified: number | null;
}

export interface Prediction {
  prediction_id: number;
  predicted_winner_id: number;
  win_probability: number;
  model_version: string;
  snapshot_at: string;
  was_correct: boolean | null;
  actual_winner_id: number | null;
  graded_at: string | null;
}

export interface Fight {
  fight_id: number;
  card_order: number | null;
  weight_class: string | null;
  is_title_fight: boolean | null;
  winner_id: number | null;
  method: string | null;
  round: number | null;
  fighter_a: Fighter | null;
  fighter_b: Fighter | null;
  predictions: Prediction[];
  prediction: Prediction | null; // back-compat: first locked pick
}

export interface Event {
  event_id: number;
  espn_event_id: string;
  name: string;
  location: string | null;
  event_date: string;
  deployed_at: string | null;
}

export interface UpcomingPayload {
  event: Event | null;
  fights: Fight[];
  models: string[];
  default_model: string | null;
}

export interface EventSnapshot {
  event: Event;
  fights: Fight[];
  models: string[];
  default_model: string | null;
}

export interface PerformanceTotals {
  graded: number;
  correct: number;
  wrong: number;
  accuracy: number | null;
  log_loss: number | null;
}

export interface AccuracyPoint {
  event_id: number;
  event_date: string;
  event_name: string;
  n_correct_so_far: number;
  n_picks_so_far: number;
  accuracy_so_far: number;
}

export interface PerEventStats {
  event_id: number;
  name: string;
  event_date: string;
  n_picks: number;
  n_correct: number;
  n_wrong: number;
  n_pending: number;
}

export interface CalibrationBin {
  bin: number;
  n: number;
  actual_win_rate: number;
  bucket_center: number;
}

export interface ModelMeta {
  model_version: string;
  model_artifact: string;
  description: string;
  trained_at: string;
  evaluation?: ModelEvaluation;
  leak_check?: LeakCheck;
  n_samples: number;
  features: string[];
}

export interface EvalScores {
  accuracy: number;
  logloss: number;
  brier: number;
  n: number;
}

/** Walk-forward backtest: train on all prior years, test on each year. */
export interface ModelEvaluation extends EvalScores {
  method: string;
  test_years: [number, number];
  /** Leak-flagged models only: scores on fights the leak can't help with. */
  clean_subset?: EvalScores;
}

export interface LeakCheck {
  passed: boolean;
  flagged: { feature: string; n: number; present_side_win_rate: number }[];
}

export interface ModelPerformance {
  totals: PerformanceTotals;
  per_event: PerEventStats[];
  calibration: CalibrationBin[];
  timeseries: AccuracyPoint[];
  meta: ModelMeta | null;
  retired: boolean;
}

export interface PerformancePayload {
  models: string[];
  default_model: string | null;
  by_model: Record<string, ModelPerformance>;
}
