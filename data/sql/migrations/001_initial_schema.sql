-- 001_initial_schema.sql

CREATE TABLE fighters (
  fighter_id      SERIAL PRIMARY KEY,
  espn_id         VARCHAR(64) UNIQUE NOT NULL,
  name            VARCHAR(255) NOT NULL,
  nickname        VARCHAR(255),
  weight_class    VARCHAR(64),
  nationality     VARCHAR(128),
  date_of_birth   DATE,
  height_cm       NUMERIC(5,1),
  reach_cm        NUMERIC(5,1),
  stance          VARCHAR(32),
  record_wins     INT DEFAULT 0,
  record_losses   INT DEFAULT 0,
  record_draws    INT DEFAULT 0,
  last_scraped_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE events (
  event_id        SERIAL PRIMARY KEY,
  espn_event_id   VARCHAR(64) UNIQUE,
  name            VARCHAR(255),
  location        VARCHAR(255),
  event_date      DATE,
  scraped_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE fights (
  fight_id        SERIAL PRIMARY KEY,
  espn_fight_id   VARCHAR(64) UNIQUE,
  event_id        INT REFERENCES events(event_id),
  fighter_a_id    INT REFERENCES fighters(fighter_id),
  fighter_b_id    INT REFERENCES fighters(fighter_id),
  winner_id       INT REFERENCES fighters(fighter_id),
  method          VARCHAR(64),
  round           INT,
  time            VARCHAR(8),
  weight_class    VARCHAR(64),
  is_title_fight  BOOLEAN DEFAULT FALSE,
  fight_date      DATE,
  scraped_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE fighter_stats (
  stat_id                  SERIAL PRIMARY KEY,
  fight_id                 INT REFERENCES fights(fight_id),
  fighter_id               INT REFERENCES fighters(fighter_id),
  sig_strikes_landed       INT,
  sig_strikes_attempted    INT,
  total_strikes_landed     INT,
  total_strikes_attempted  INT,
  takedowns_landed         INT,
  takedowns_attempted      INT,
  submission_attempts      INT,
  reversals                INT,
  control_time_sec         INT,
  knockdowns               INT
);

CREATE TABLE elo_ratings (
  rating_id        SERIAL PRIMARY KEY,
  fighter_id       INT REFERENCES fighters(fighter_id),
  fight_id         INT REFERENCES fights(fight_id),
  elo_standard     NUMERIC(8,2),
  elo_modified     NUMERIC(8,2),
  elo_standard_pre NUMERIC(8,2),
  elo_modified_pre NUMERIC(8,2),
  rating_date      DATE,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE predictions (
  prediction_id       SERIAL PRIMARY KEY,
  fight_id            INT REFERENCES fights(fight_id),
  predicted_winner_id INT REFERENCES fighters(fighter_id),
  win_probability     NUMERIC(5,4),
  model_version       VARCHAR(32),
  features_snapshot   JSONB,
  actual_winner_id    INT REFERENCES fighters(fighter_id),
  was_correct         BOOLEAN,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE bets (
  bet_id             SERIAL PRIMARY KEY,
  fight_id           INT REFERENCES fights(fight_id),
  fighter_backed_id  INT REFERENCES fighters(fighter_id),
  odds               VARCHAR(16),
  stake_usd          NUMERIC(8,2),
  payout_usd         NUMERIC(8,2),
  result             VARCHAR(8),
  profit_usd         NUMERIC(8,2),
  notes              TEXT,
  placed_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE blog_posts (
  post_id      SERIAL PRIMARY KEY,
  slug         VARCHAR(255) UNIQUE NOT NULL,
  title        VARCHAR(255) NOT NULL,
  summary      TEXT,
  tags         TEXT[],
  published_at DATE,
  is_published BOOLEAN DEFAULT FALSE
);
