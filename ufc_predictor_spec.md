# UFC Fight Predictor
## Project Architecture & LLM Guidance Document
*v1.0 | Full-Stack ML Project*

---

## 1. Purpose of This Document

This document serves as the single source of truth for the UFC Fight Predictor project. It is written to guide LLMs (and human developers) who are implementing specific pieces of this system. Each section explains what a component does, how it fits into the broader architecture, what technology to use, and what constraints to respect.

If you are an LLM working on a task in this project: read this document in full before writing any code. Do not invent architecture decisions that contradict what is written here.

---

## 2. Project Overview

This project has six distinct concerns that must be implemented and maintained together:

- Data pipeline: scrape UFC fighter and fight data from ESPN, store in PostgreSQL
- ML model: XGBoost classifier using Elo ratings (standard and modified) as features
- Public React website: fighter profiles, fight predictions, model performance dashboard
- Bet tracker: public log of fight bets, outcomes, ROI over time
- Blog: markdown-file-based posts about learnings and model updates
- API: FastAPI backend that connects the database, model, and frontend

---

## 3. Repository Structure

### Recommendation: Monorepo with Clear Subdirectory Separation

Because this is a solo project and all six pieces are tightly coupled (the frontend depends on the API, the API depends on the model, the model depends on the data pipeline), use a single GitHub repository organized into top-level subdirectories. This is the right call here; a multi-repo setup adds complexity with no payoff at this scale.

```
ufc-predictor/
├── data/                    # Data pipeline (scraping + ingestion)
│   ├── scrapers/            # ESPN scraper scripts
│   ├── loaders/             # PostgreSQL ingestion logic
│   └── sql/                 # Table DDL, migration scripts
├── model/                   # ML model code
│   ├── features/            # Feature engineering (Elo, stats)
│   ├── training/            # XGBoost training scripts
│   ├── evaluation/          # Accuracy, calibration, log-loss
│   └── artifacts/           # Saved model files (.json or .pkl)
├── api/                     # FastAPI backend
│   ├── routers/             # Route files (fighters, fights, bets, blog)
│   ├── schemas/             # Pydantic models
│   ├── db/                  # SQLAlchemy models + connection
│   └── main.py
├── frontend/                # React application (Vite)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/           # Home, Fighter, Predictions, Bets, Blog
│   │   └── lib/             # API client, helpers
│   └── public/
├── blog/                    # Markdown post files
│   └── YYYY-MM-DD-slug.md
├── skills/                  # LLM skill files (one per component)
├── .env.example             # Environment variable template
├── docker-compose.yml       # Local dev: PostgreSQL + API
└── README.md
```

> **LLM instruction:** When writing code for this project, always place new files inside the correct subdirectory as shown above. Never create files in the repo root unless they are config files like `.env.example` or `docker-compose.yml`.

---

## 4. Technology Stack

| Layer | Technology + Rationale |
|---|---|
| Database | PostgreSQL — relational, handles time-series fight data well, strong JSON support for flexible fields |
| Data pipeline | Python — requests + BeautifulSoup for scraping, psycopg2 or SQLAlchemy for DB writes |
| ML model | Python — XGBoost, pandas, scikit-learn for preprocessing, joblib for model serialization |
| API | FastAPI — Python-native so it shares code with the model layer, async support, auto-generates OpenAPI docs |
| ORM | SQLAlchemy (used inside FastAPI) — maps PostgreSQL tables to Python objects cleanly |
| Frontend | React (Vite) — component-based, large ecosystem, easy deployment |
| Blog | Markdown files in /blog — parsed at build time or via API, no CMS needed |
| Hosting (recommendation) | Render.com — free tier for FastAPI web service + PostgreSQL, pairs naturally with Vercel for the React frontend |
| Version control | GitHub — single monorepo, branch-per-feature workflow |
| Local dev | Docker Compose — spins up PostgreSQL locally so dev matches prod |

---

## 5. Database Schema

### 5.1 Core Tables

All tables live in PostgreSQL. Use snake_case for all table and column names. Primary keys are serial integers as indicated.

#### fighters

```sql
CREATE TABLE fighters (
  fighter_id      SERIAL PRIMARY KEY,
  espn_id         VARCHAR(64) UNIQUE NOT NULL,  -- ESPN's internal ID
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
```

#### fights

```sql
CREATE TABLE fights (
  fight_id        SERIAL PRIMARY KEY,
  espn_fight_id   VARCHAR(64) UNIQUE,
  event_id        INT REFERENCES events(event_id),
  fighter_a_id    INT REFERENCES fighters(fighter_id),
  fighter_b_id    INT REFERENCES fighters(fighter_id),
  winner_id       INT REFERENCES fighters(fighter_id),   -- NULL if future/draw
  method          VARCHAR(64),   -- KO, TKO, SUB, DEC, etc.
  round           INT,
  time            VARCHAR(8),    -- e.g. '3:47'
  weight_class    VARCHAR(64),
  is_title_fight  BOOLEAN DEFAULT FALSE,
  fight_date      DATE,
  scraped_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### events

```sql
CREATE TABLE events (
  event_id        SERIAL PRIMARY KEY,
  espn_event_id   VARCHAR(64) UNIQUE,
  name            VARCHAR(255),
  location        VARCHAR(255),
  event_date      DATE,
  scraped_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### fighter_stats (per-fight stats)

```sql
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
```

#### elo_ratings

```sql
CREATE TABLE elo_ratings (
  rating_id        SERIAL PRIMARY KEY,
  fighter_id       INT REFERENCES fighters(fighter_id),
  fight_id         INT REFERENCES fights(fight_id),
  elo_standard     NUMERIC(8,2),   -- classic Elo after this fight
  elo_modified     NUMERIC(8,2),   -- opponent-quality-weighted Elo after this fight
  elo_standard_pre NUMERIC(8,2),   -- Elo before this fight (for feature use)
  elo_modified_pre NUMERIC(8,2),
  rating_date      DATE,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);
```

#### predictions

```sql
CREATE TABLE predictions (
  prediction_id       SERIAL PRIMARY KEY,
  fight_id            INT REFERENCES fights(fight_id),
  predicted_winner_id INT REFERENCES fighters(fighter_id),
  win_probability     NUMERIC(5,4),   -- e.g. 0.6734
  model_version       VARCHAR(32),
  features_snapshot   JSONB,          -- store the feature vector used
  actual_winner_id    INT REFERENCES fighters(fighter_id),  -- NULL until result
  was_correct         BOOLEAN,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

#### bets

```sql
CREATE TABLE bets (
  bet_id             SERIAL PRIMARY KEY,
  fight_id           INT REFERENCES fights(fight_id),
  fighter_backed_id  INT REFERENCES fighters(fighter_id),
  odds               VARCHAR(16),    -- e.g. '-150', '+220'
  stake_usd          NUMERIC(8,2),
  payout_usd         NUMERIC(8,2),   -- NULL until settled
  result             VARCHAR(8),     -- WIN, LOSS, PUSH, NULL
  profit_usd         NUMERIC(8,2),   -- negative for losses
  notes              TEXT,
  placed_at          TIMESTAMPTZ DEFAULT NOW()
);
```

#### blog_posts (metadata only — body lives in /blog/*.md)

```sql
CREATE TABLE blog_posts (
  post_id      SERIAL PRIMARY KEY,
  slug         VARCHAR(255) UNIQUE NOT NULL,  -- matches filename
  title        VARCHAR(255) NOT NULL,
  summary      TEXT,
  tags         TEXT[],
  published_at DATE,
  is_published BOOLEAN DEFAULT FALSE
);
```

> **LLM instruction:** Never alter the schema above without documenting the migration in `data/sql/migrations/`. New columns must be nullable or have a DEFAULT to avoid breaking existing rows. Always use REFERENCES constraints for foreign keys.

---

## 6. Data Pipeline

### 6.1 Source

All fighter and fight data is scraped from ESPN (espn.com). This is triggered manually. There is no automated scheduler in v1.

### 6.2 Scraper Architecture

The scraper lives in `data/scrapers/`. It must be written in Python using the `requests` library and BeautifulSoup for HTML parsing. Do not use Selenium unless ESPN blocks requests-based scraping (it may for some pages — try requests first).

The scraping flow is:

- Scrape the UFC fighter index page to get a list of active fighters and their ESPN IDs
- For each fighter, scrape their profile page: bio, record, career stats
- Scrape the fights/events list to get historical fight results and per-fight stats
- Write all raw data to staging tables first (prefixed `raw_`), then run a transform step into the clean tables

### 6.3 Idempotency Rule

All scrapers must be idempotent. Running the same scraper twice must not create duplicate rows. Use `INSERT ... ON CONFLICT (espn_id) DO UPDATE` for upserts.

> **LLM instruction:** Every scraper function must accept a `dry_run=True` parameter that prints what would be inserted without touching the database. This makes testing safe.

---

## 7. Elo Rating System

### 7.1 Standard Elo

Standard Elo works the same as chess. Each fighter starts at 1500. After each fight, ratings update based on the outcome and the expected probability of winning derived from the rating difference.

```python
K = 32   # K-factor: controls how fast ratings change

def expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def update_elo(winner_rating, loser_rating, k=K):
    expected_win = expected_score(winner_rating, loser_rating)
    new_winner = winner_rating + k * (1 - expected_win)
    new_loser  = loser_rating  + k * (0 - (1 - expected_win))
    return new_winner, new_loser
```

### 7.2 Modified Elo (Opponent-Quality Weighted)

The modified Elo adjusts the K-factor dynamically based on the quality of the opponent at the time of the fight. The idea: beating an elite opponent should move your rating more than beating a low-ranked opponent, even if standard Elo already partially accounts for this through the expected score formula. The modification adds an explicit multiplier to K.

```python
BASE_K = 32
ELITE_THRESHOLD = 1600    # Rating above which opponent is considered elite
ELITE_MULTIPLIER = 1.5    # Boost K by 50% when opponent is elite
WEAK_THRESHOLD = 1400     # Rating below which opponent is considered weak
WEAK_MULTIPLIER = 0.75    # Reduce K by 25% when opponent is weak

def modified_k(opponent_rating):
    if opponent_rating >= ELITE_THRESHOLD:
        return BASE_K * ELITE_MULTIPLIER
    elif opponent_rating <= WEAK_THRESHOLD:
        return BASE_K * WEAK_MULTIPLIER
    else:
        # Linear interpolation between thresholds
        t = (opponent_rating - WEAK_THRESHOLD) / (ELITE_THRESHOLD - WEAK_THRESHOLD)
        return BASE_K * (WEAK_MULTIPLIER + t * (ELITE_MULTIPLIER - WEAK_MULTIPLIER))

def update_modified_elo(winner_rating, loser_rating):
    k_winner = modified_k(loser_rating)   # Winner's K based on opponent quality
    k_loser  = modified_k(winner_rating)
    expected_win = expected_score(winner_rating, loser_rating)
    new_winner = winner_rating + k_winner * (1 - expected_win)
    new_loser  = loser_rating  + k_loser  * (0 - (1 - expected_win))
    return new_winner, new_loser
```

> **LLM instruction:** The thresholds (1400, 1600) and multipliers (0.75, 1.5) above are starting values and should be treated as hyperparameters. Do not hard-code them as magic numbers — load them from a config dict or constants file so they can be tuned easily.

Both the standard and modified Elo ratings for each fighter are stored in the `elo_ratings` table after every fight is processed. The Elo computation must be run in chronological fight order — always sort by `fight_date ASC` before processing.

---

## 8. Machine Learning Model

### 8.1 Model Choice

XGBoost binary classifier. Predicts: did `fighter_a` win? (1 = yes, 0 = no). The model also outputs a win probability via `predict_proba`, which is stored alongside the binary prediction.

### 8.2 Feature Set

Features are computed per matchup (one row = one fight, from `fighter_a`'s perspective). The model is trained with both fighters appearing as `fighter_a` across different rows to balance perspective.

| Feature | Description | Source |
|---|---|---|
| elo_standard_pre_a | Fighter A standard Elo before this fight | elo_ratings |
| elo_modified_pre_a | Fighter A modified Elo before this fight | elo_ratings |
| elo_standard_pre_b | Fighter B standard Elo before this fight | elo_ratings |
| elo_modified_pre_b | Fighter B modified Elo before this fight | elo_ratings |
| elo_diff_standard | elo_pre_a - elo_pre_b (standard) | derived |
| elo_diff_modified | elo_pre_a - elo_pre_b (modified) | derived |
| wins_a / losses_a | Fighter A career record | fighters |
| wins_b / losses_b | Fighter B career record | fighters |
| sig_strike_acc_a | Career significant strike accuracy | fighter_stats (agg) |
| sig_strike_acc_b | Fighter B equivalent | fighter_stats (agg) |
| td_acc_a / td_acc_b | Takedown accuracy per fighter | fighter_stats (agg) |
| days_since_last_fight_a | Layoff in days for fighter A | fights (derived) |
| days_since_last_fight_b | Fighter B equivalent | fights (derived) |
| is_title_fight | 1 if this is a title bout | fights |
| weight_class_encoded | One-hot or ordinal encoded weight class | fights (encoded) |

### 8.3 Training

```python
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import log_loss, accuracy_score

# IMPORTANT: Use TimeSeriesSplit, not random KFold.
# We must not train on future fights to predict past ones.
tscv = TimeSeriesSplit(n_splits=5)

model = xgb.XGBClassifier(
    n_estimators=300,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    use_label_encoder=False,
    eval_metric='logloss'
)

# After training, serialize the model:
model.save_model('model/artifacts/xgb_vX.json')
```

> **LLM instruction:** Always use `TimeSeriesSplit` for cross-validation. Random splits would leak future fight data into training, making accuracy metrics meaningless. The model artifact filename must include a version number (e.g. `xgb_v1.json`, `xgb_v2.json`). Never overwrite the previous version.

### 8.4 Model Output

For any given upcoming fight, the API loads the latest model artifact and returns both a predicted winner and a win probability for each fighter. These are stored in the `predictions` table. Once the fight result is known, the `was_correct` column is updated by re-running a post-event scoring script.

---

## 9. FastAPI Backend

### 9.1 Structure

The API lives in `api/`. Each concern gets its own router file. All routers are registered in `api/main.py`. The API exposes JSON endpoints consumed by the React frontend.

| Router file | Endpoints |
|---|---|
| routers/fighters.py | GET /fighters, GET /fighters/{id}, GET /fighters/{id}/stats, GET /fighters/{id}/elo |
| routers/fights.py | GET /fights, GET /fights/{id}, GET /fights/upcoming |
| routers/predictions.py | GET /predictions, GET /predictions/{fight_id}, POST /predictions/run |
| routers/bets.py | GET /bets, POST /bets, PATCH /bets/{id}/settle |
| routers/blog.py | GET /blog, GET /blog/{slug} |
| routers/model.py | GET /model/performance — accuracy, log-loss, calibration over time |

### 9.2 Database Connection

```python
# api/db/connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ['DATABASE_URL']  # Never hard-code credentials

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

> **LLM instruction:** All database credentials and secrets go in environment variables loaded via `python-dotenv` locally and set as real env vars in production. Never commit a `.env` file. An `.env.example` file with placeholder values should always be kept up to date.

### 9.3 Blog Endpoint

Blog posts are markdown files in `/blog/`. The API reads the file system to return post content. The `blog_posts` table stores only metadata (title, slug, published_at, tags). The `/blog/{slug}` endpoint reads the corresponding `.md` file and returns its content as a string. The frontend renders it with a markdown parser like `react-markdown`.

---

## 10. React Frontend

### 10.1 Stack

React 18 with Vite for fast local development. Use React Router for client-side routing. Use TanStack Query (React Query) for all API data fetching — it handles caching, loading states, and refetching cleanly. Style with Tailwind CSS.

### 10.2 Pages

| Route | Purpose |
|---|---|
| / | Home — recent fights, latest predictions, blog highlights |
| /fighters | Fighter search and index |
| /fighters/:id | Fighter profile — bio, record, Elo history chart, recent fights |
| /predictions | Upcoming fight predictions — win probabilities, model confidence |
| /model | Model performance dashboard — accuracy over time, calibration, log-loss |
| /bets | Public bet tracker — table of all bets, ROI summary, win rate |
| /blog | Blog post index |
| /blog/:slug | Individual blog post rendered from markdown |

### 10.3 Key Components

- `EloChart` — recharts LineChart showing a fighter's Elo history over fights
- `PredictionCard` — shows fight matchup, predicted winner, probability bar
- `BetTable` — sortable table of all bets with color-coded win/loss rows
- `ModelMetricsPanel` — accuracy, log-loss, and calibration curve
- `MarkdownRenderer` — wraps react-markdown for blog post display

> **LLM instruction:** Do not use create-react-app. Use Vite (`npm create vite@latest`). All API calls go through a single `lib/api.js` client file that sets the base URL from an environment variable (`VITE_API_URL`). Never hard-code the API URL in component files.

---

## 11. Bet Tracker

### 11.1 Behavior

The bet tracker is publicly visible — anyone visiting the site can see the bet history. There is no authentication in v1. New bets are added and settled via direct API calls (`POST /bets` and `PATCH /bets/{id}/settle`). You can call these from a tool like Postman, Insomnia, or a simple admin script.

### 11.2 Metrics Displayed

- Total bets placed
- Win/loss/push breakdown
- Total profit/loss in USD
- ROI percentage: (total profit / total staked) * 100
- Running profit/loss chart over time (recharts AreaChart)
- Bet vs. model prediction alignment: did you bet on who the model picked?

### 11.3 Odds Handling

Store odds in American format as a string (e.g. `'-150'`, `'+220'`). The API converts to decimal odds for ROI calculations. Provide a utility function in the frontend to display odds in either format.

```python
def american_to_decimal(odds_str: str) -> float:
    odds = int(odds_str)
    if odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1
```

---

## 12. Blog

### 12.1 File Convention

Blog post files live in `/blog/` at the repo root. File naming convention: `YYYY-MM-DD-slug.md` where slug is a URL-safe lowercase string with hyphens. Example: `2025-03-15-how-modified-elo-works.md`

### 12.2 Frontmatter

Each markdown file must start with YAML frontmatter that matches the `blog_posts` table schema:

```yaml
---
title: How the Modified Elo System Works
summary: A breakdown of how opponent quality changes Elo K-factor adjustments.
tags: [elo, model, methodology]
published_at: 2025-03-15
is_published: true
---

Post body starts here in standard markdown...
```

A sync script in `data/loaders/sync_blog.py` reads all `.md` files, parses their frontmatter, and upserts the metadata into `blog_posts`. Run this script after writing a new post.

---

## 13. Environment Variables

The `.env.example` file in the repo root must always be kept current. The actual `.env` is gitignored.

```bash
# .env.example

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/ufc_predictor

# API
API_HOST=0.0.0.0
API_PORT=8000

# Frontend (Vite prefix required)
VITE_API_URL=http://localhost:8000

# Model
MODEL_ARTIFACT_PATH=model/artifacts/xgb_v1.json
```

---

## 14. Deployment (Recommended Path)

| Component | Recommended Service |
|---|---|
| PostgreSQL | Render.com managed PostgreSQL (free tier: 1GB, sufficient for v1) |
| FastAPI | Render.com Web Service — connect to GitHub repo, set build command: `pip install -r requirements.txt`, start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT` |
| React frontend | Vercel — connect GitHub repo, set root to `/frontend`, Vercel auto-detects Vite |
| Blog markdown files | Served from the API container filesystem — no separate hosting needed in v1 |

> **LLM instruction:** When writing deployment-related code or configuration, target Render.com for the API/database and Vercel for the frontend. Do not write AWS, Azure, or GCP-specific infrastructure code unless the user explicitly changes this decision.

---

## 15. LLM Working Rules

If you are an LLM implementing any part of this project, follow these rules without exception:

- Read this entire document before writing any code for a new component.
- Do not invent table names, column names, or API routes that are not defined here. If you need something new, note it explicitly and ask the user to confirm before implementing.
- All Python code targets Python 3.11+. Use type hints throughout.
- All SQL is PostgreSQL — do not write SQLite or MySQL syntax.
- Never commit credentials. All secrets use environment variables.
- Model artifacts are versioned. Never overwrite `xgb_v1.json` — create `xgb_v2.json`.
- Elo must be computed in chronological fight order (sort by `fight_date ASC`) and stored in `elo_ratings` after every fight.
- Use `TimeSeriesSplit` for all model cross-validation. No random splits.
- The bet tracker is public and requires no authentication in v1.
- Blog posts are markdown files — do not build a database-backed CMS.
- When in doubt about a design decision not covered here, ask the user before implementing.

---

## 16. Recommended Build Order

Build in this sequence to minimize rework. Each phase produces something independently testable before moving on.

| Phase | Deliverable |
|---|---|
| Phase 1 | PostgreSQL schema — create all tables using the DDL in Section 5. Verify with a local Docker Compose setup. |
| Phase 2 | Data scraper — scrape fighters and fights from ESPN, load into database. Verify row counts and upsert behavior. |
| Phase 3 | Elo computation — process all historical fights in order, populate elo_ratings. Sanity check: top-rated fighters should look reasonable. |
| Phase 4 | Feature engineering + XGBoost training — build the feature matrix, train the model, evaluate with TimeSeriesSplit, save artifact. |
| Phase 5 | FastAPI — build all routers, connect to database and model, test all endpoints with Swagger UI at /docs. |
| Phase 6 | React frontend — build all pages against the live API. Start with fighters and predictions before bets and blog. |
| Phase 7 | Blog — write first post, run sync script, verify it appears via API and frontend. |
| Phase 8 | Deploy — Render.com for API + DB, Vercel for frontend. Smoke test all pages in production. |

---

## 17. Global Best Practices for LLMs

This section defines standards that apply across every component in the project. Any LLM working on any part of this codebase must follow all of these without exception.

### 17.1 Python Code Standards

- Target Python 3.11+. Use type hints on all function signatures.
- Use `pathlib.Path` instead of `os.path` for all file system operations.
- Use `python-dotenv` to load `.env` files locally. Never call `os.environ.get()` with a fallback that contains a real credential.
- All database-touching functions must accept a db session as a parameter — never open a new connection inside a utility function.
- Use f-strings for string formatting. Do not use `%` formatting or `.format()`.
- Wrap all external HTTP calls (ESPN scraper) in try/except with specific exception handling for `requests.HTTPError` and `requests.Timeout`.
- Every script that can be run from the command line must use `if __name__ == '__main__':` guard.

### 17.2 SQL and Database Standards

- All SQL files use uppercase keywords: SELECT, FROM, WHERE, JOIN, etc.
- All table and column names are snake_case, never camelCase.
- Every INSERT that could produce a duplicate must use `ON CONFLICT ... DO UPDATE` or `ON CONFLICT DO NOTHING`. Never assume a row does not exist.
- Never use `SELECT *` in production query code. Always name the columns you need.
- All schema changes (new tables, new columns, dropped columns) go in a numbered migration file in `data/sql/migrations/`. Filename format: `001_create_fighters.sql`, `002_add_elo_table.sql`.
- Foreign key constraints are required on all referencing columns. Do not skip them for convenience.

### 17.3 API Standards

- All API responses are JSON. Use Pydantic response models — never return raw SQLAlchemy objects.
- HTTP status codes must be correct: 200 for success, 201 for creation, 404 for not found, 422 for validation errors (FastAPI handles this automatically).
- All list endpoints must support pagination via `skip` and `limit` query parameters with sensible defaults (`skip=0`, `limit=50`).
- CORS must be configured in `main.py` to allow the frontend origin. In development, allow all origins. In production, restrict to the Vercel deployment URL.
- Never expose internal database IDs as the only identifier in URLs — include a human-readable slug or name where possible.

### 17.4 React / Frontend Standards

- All API calls go through `lib/api.js`. No `fetch()` or `axios` calls directly in component files.
- Use TanStack Query (`useQuery`, `useMutation`) for all server state. Do not use `useState + useEffect` for data fetching.
- Environment variables must use the `VITE_` prefix to be accessible in the browser. Never access `process.env` in Vite — use `import.meta.env`.
- Components go in `src/components/` if reusable, `src/pages/` if they are route-level pages.
- Do not install a UI component library (e.g. MUI, Ant Design). Use Tailwind utility classes directly. If a complex component is needed, build it.
- All charts use recharts. Do not introduce a second charting library.

### 17.5 Git and File Hygiene

- Branch naming: `feature/phase-1-schema`, `fix/elo-sort-order`, `chore/update-deps`.
- `.gitignore` must include: `.env`, `__pycache__`, `*.pyc`, `node_modules`, `model/artifacts/*.json` (model files are large — use Git LFS or store externally), `dist/`.
- Never commit a model artifact without incrementing the version number in the filename.
- The `.env.example` file must be updated any time a new environment variable is added to the codebase.

### 17.6 Error Handling Philosophy

- Fail loudly during development. Do not swallow exceptions with bare `except: pass`.
- In the API, use FastAPI's `HTTPException` for all user-facing errors. Include a meaningful `detail` message.
- In the scraper, log every failed request with the URL and status code. Continue processing remaining fighters — one failure should not abort the whole run.
- In the model training script, assert that the feature matrix has no NaN values before fitting. Raise a descriptive error if it does.

---

## 18. Skill Files

### What Are Skill Files?

Skill files are short, focused markdown documents — one per project component — that live in a `skills/` folder at the repo root. Each skill file contains the exact patterns, library choices, gotchas, and working code snippets for its component. When you start a new task with an LLM, you pass only the relevant skill file as context rather than this entire spec document.

This keeps context windows lean and ensures the LLM gets precise, task-specific guidance rather than wading through sections that are not relevant to the task at hand.

### Skill File Locations

```
ufc-predictor/
└── skills/
    ├── SKILL_scraper.md       # Phase 2: ESPN scraping patterns
    ├── SKILL_elo.md           # Phase 3: Elo computation patterns
    ├── SKILL_model.md         # Phase 4: XGBoost training patterns
    ├── SKILL_api.md           # Phase 5: FastAPI patterns
    ├── SKILL_frontend.md      # Phase 6: React + Vite patterns
    ├── SKILL_blog.md          # Phase 7: Markdown blog patterns
    └── SKILL_deploy.md        # Phase 8: Render + Vercel deployment
```

### Skill File Template

Use this structure for every skill file:

```markdown
# SKILL: [Component Name]

## Purpose
One sentence: what does this component do in the project?

## Files It Owns
List the directories and files this skill covers.

## Key Libraries
List with pinned versions once established.

## Patterns
Working code snippets for the most common operations.
Prefer real code over prose explanations.

## Gotchas
Things that went wrong during implementation and how they were resolved.
This section grows as you build.

## LLM Instructions
Explicit rules for any LLM working on this component.
Reference relevant sections of the main spec doc by number.

## Status
NOT STARTED | IN PROGRESS | COMPLETE
```

### How to Use Skill Files With an LLM

When starting a task, open a new chat and paste:

- The relevant skill file in full
- The relevant sections from this spec document (e.g. Section 5 for database work, Section 7 for Elo work)
- Your specific task description

The LLM does not need the entire spec every time. Skill files are designed to be the fast path — they contain the distilled, working knowledge from the spec plus any lessons learned during implementation.

> **Important:** Skill files are living documents. After finishing each phase, spend 10 minutes updating the relevant skill file with any gotchas, pattern adjustments, or library decisions that came up during implementation. Future LLMs (and future you) will thank you.

---

*End of Document*
