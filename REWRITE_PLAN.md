# UFC Predictor — Rewrite Plan

Single source of truth for the rewrite. Read this first before touching code.

---

## 1. Why we are rewriting

The current app implements six tightly-coupled concerns (data, model, FastAPI, React SPA, bet tracker, blog). It works, but it is too complex for a solo-maintained portfolio project: too many moving parts, too much glue, too much to break.

**Goals of the rewrite:**
- Cut moving parts so changes are cheap
- Look and feel like a real ML portfolio piece (public-facing)
- $0/month to run
- < 1 hour/week to maintain
- Keep Postgres (used daily in day job — staying sharp on it is a goal)
- Keep the existing scrapers (they work)

**What the user said, captured:**
| Decision area | Choice |
|---|---|
| Main pain | Too complex / hard to change |
| Audience | Public portfolio / blog |
| Real bets? | Yes, real money — but app is for prediction/analysis (not bet tracking) |
| Stack flexibility | Open to anything that simplifies |
| Refresh cadence | Once per event (weekly-ish), manual trigger |
| Backend? | No live backend — static site, pre-built JSON |
| Hosting | GitHub Pages, $0 |
| Site framework | Next.js (static export) |
| Design bar | Genuinely nice-looking |
| Value-bet UI? | No — model probabilities only |
| Performance tracking | Snapshot picks pre-event, score after |
| Refresh trigger | Manual (user runs pipeline locally) |
| Postgres location | Local only |
| Existing data | Keep current schema, extend it (no migration to new schema) |
| Old model artifacts | Discard |
| Elo updates | Must update fighters' Elo after fights are graded |

---

## 2. New architecture

```
ufc-predictor/
├── pipeline/                  # Python — everything that touches data
│   ├── scrape.py              # ported from existing data/scrapers/
│   ├── ingest.py              # ported from existing data/ingest.py
│   ├── features.py            # Elo + feature engineering (ported)
│   ├── train.py               # XGBoost training (ported)
│   ├── predict.py             # picks for next event → snapshot row in `predictions`
│   ├── grade.py               # score snapshots post-event (ported from grade_predictions)
│   ├── elo_update.py          # incremental Elo update (ported from elo_pipeline)
│   ├── export.py              # query Postgres → write JSON to site/public/data/
│   └── run.py                 # one entrypoint, two modes: --pre-event / --post-event
├── site/                      # Next.js static export
│   ├── src/
│   │   ├── pages/
│   │   │   ├── index.tsx          # Upcoming predictions
│   │   │   ├── performance.tsx    # Dashboard
│   │   │   ├── methodology.tsx    # MDX — how the model works
│   │   │   └── blog/
│   │   │       ├── index.tsx      # post list
│   │   │       └── [slug].tsx     # MDX post page
│   │   ├── components/
│   │   └── lib/
│   └── public/data/           # JSON committed to repo (the deploy artifact)
├── blog/                      # MDX post files
├── sql/                       # migrations (existing + new)
├── .github/workflows/
│   └── deploy.yml             # build site + deploy to Pages on push
├── requirements.txt           # pip-managed Python deps (kept as-is)
├── REWRITE_PLAN.md            # this file
└── README.md
```

**What goes away:**
- `api/` (FastAPI) — gone, no backend
- `frontend/` (Vite + React SPA) — replaced by `site/`
- `docker-compose.yml` — not needed (Postgres runs natively on user's machine)
- `data/loaders/export_static_api.py` — replaced by `pipeline/export.py`
- `bets` table usage on the site (table itself stays in case it's useful in psql)
- `blog_posts` table — blog is MDX files in repo
- Fighter profile pages
- Bet tracker / ROI page
- All `_v1` / `_v2` parallel files (we pick one and move on)

---

## 3. The two-loop workflow

### Pre-event (user, when fight card is locked)
```
python -m pipeline.run --pre-event [--event-id N]
```
1. Scrape any newly-announced upcoming event
2. Retrain model on all completed fights
3. Generate predictions for the upcoming event
4. Insert snapshot rows into `predictions` with `snapshot_at = NOW()`, `is_locked = TRUE`
5. Export JSON to `site/public/data/`
6. User commits + pushes → Pages redeploys

### Post-event (user, after the card finishes)
```
python -m pipeline.run --post-event
```
1. Scrape results for the completed event
2. Scrape per-fight stats for fighters in completed fights
3. **Grade** all ungraded locked predictions (fill `actual_winner_id`, `was_correct`, `graded_at`)
4. **Elo update** (incremental) for the newly-completed fights — this is the user's explicit requirement
5. Refresh `fighters.current_elo_standard` / `current_elo_modified` (denormalized fast-read columns — see schema changes)
6. Export updated JSON (performance dashboard now reflects the new results)
7. User commits + pushes → Pages redeploys

**Critical ordering** (preserved from existing `data/post_event_pipeline.py`):
> Ingest → Stats → Grade → Elo update

Elo MUST run after Grade, because Elo derives from `winner_id` and `winner_id` is what Grade reconciles. The current code does this correctly; the rewrite preserves it.

---

## 4. Schema — what stays, what changes

### Stays as-is (good schemas)
- `fighters` (with `is_active` flag)
- `events` (with `deployed_at` for filtering live vs. backtest)
- `fights` (with `card_order`, `is_cancelled`)
- `fighter_stats` (full 37-column ESPN stats with unique constraint)
- `elo_ratings` (one row per fighter-fight, with pre/post for both standard and modified)

### Extend `predictions` (additive, no breakage)

The existing `predictions` table already has `actual_winner_id` and `was_correct` for grading. Extend it to support the pre-event snapshot pattern:

```sql
-- 007_extend_predictions_for_snapshots.sql
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS event_id INT REFERENCES events(event_id);
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS snapshot_at TIMESTAMPTZ;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS is_locked BOOLEAN DEFAULT FALSE;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS graded_at TIMESTAMPTZ;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS model_artifact VARCHAR(128);

-- One locked prediction per fight per model version
CREATE UNIQUE INDEX IF NOT EXISTS ux_predictions_locked
  ON predictions (fight_id, model_version)
  WHERE is_locked = TRUE;

CREATE INDEX IF NOT EXISTS idx_predictions_event ON predictions(event_id);
```

**Why each:**
- `event_id` — denormalized, lets the dashboard query "all picks for event X" without joining through `fights`
- `snapshot_at` — when picks were locked. Distinguishes "this is what the model said *at the time*" from "this is what the current model would say now"
- `is_locked` — separates the immutable pre-event snapshot from any exploratory predictions
- `graded_at` — companion to `actual_winner_id`/`was_correct`; useful for "show me picks graded in last 7 days"
- `model_artifact` — filename of the model file used (e.g. `xgb_2026_05_20.json`) for full reproducibility

### Extend `fighters` (denormalized current Elo for fast reads)

```sql
-- 008_add_current_elo_to_fighters.sql
ALTER TABLE fighters ADD COLUMN IF NOT EXISTS current_elo_standard NUMERIC(8,2);
ALTER TABLE fighters ADD COLUMN IF NOT EXISTS current_elo_modified NUMERIC(8,2);
ALTER TABLE fighters ADD COLUMN IF NOT EXISTS current_elo_updated_at TIMESTAMPTZ;
```

**Why:** the predictions page needs "what's this fighter's Elo *right now*" for every upcoming fight. Without denormalization, that's a `DISTINCT ON (fighter_id) ... ORDER BY rating_id DESC` per fighter every page build. With it, it's a trivial join. The post-event pipeline updates these columns after the Elo step.

### Indexes worth adding

```sql
-- 009_add_useful_indexes.sql
CREATE INDEX IF NOT EXISTS idx_fights_fight_date ON fights(fight_date);
CREATE INDEX IF NOT EXISTS idx_fights_event ON fights(event_id);
CREATE INDEX IF NOT EXISTS idx_elo_ratings_fighter_recent
  ON elo_ratings(fighter_id, rating_id DESC);
```

### Tables we stop using (but don't drop)

- `bets` — keep the table so historical data isn't lost, but no code reads or writes it
- `blog_posts` — same; blog is now MDX files. Could drop in a follow-up migration if desired.

### Recommendations the user can ignore

These are nice-to-haves I noticed but are not required for the rewrite:
1. **`model_runs` table** — track each training run (date, training set size, holdout metrics, artifact filename). Useful for the performance page but the same info can be backed out from `predictions.model_version`.
2. **`events.status` enum** — `upcoming | live | completed | cancelled`. Currently derived from dates + winner presence; works fine as-is.
3. **Materialized view for the performance dashboard** — premature; recompute at export time.

---

## 5. Site structure

Three pages plus blog. No login, no API.

### `/` — Upcoming predictions
- Hero: next event name + date + location
- Fight cards in `card_order` (main event first)
- Per fight: both fighters (name, record, current Elo), model probability for each, confidence bar
- Subtle "How does this work?" link to `/methodology`

### `/performance` — Dashboard
- Headline numbers: overall accuracy on locked picks, log loss, count of graded picks
- Cumulative accuracy chart over time
- Calibration plot (predicted prob vs. actual win rate, bucketed)
- Per-event drilldown table (event, n picks, n correct, log loss)
- Filter: deployed events only (uses `events.deployed_at`)

### `/methodology` — How the model works
- MDX page
- Sections: Data sources → Feature engineering (Elo standard + modified) → Model (XGBoost) → Training cadence → Known limits / what the model can't see (e.g., camp changes, injuries)

### `/blog`
- Index page lists MDX posts (date, title, summary)
- `/blog/[slug]` renders MDX with prose styling

---

## 6. Tech choices, locked in

| Layer | Choice | Why |
|---|---|---|
| Database | PostgreSQL (local) | User works with it daily, existing data, no migration |
| Python deps | `pip` + `requirements.txt` + venv | Already in use; no new tooling to install |
| Python DB client | `psycopg` (v3, already in use) | Already used |
| Model | XGBoost (existing approach) | User picked "keep XGBoost + Elo, just clean up the code" |
| Frontend | Next.js 14+ (App Router) with `output: 'export'` | User picked it |
| Styling | Tailwind CSS | Standard for Next.js, fast to iterate |
| Charts | Recharts | React-native, good defaults, easy to style |
| MDX | `next-mdx-remote` or built-in `@next/mdx` | For blog + methodology |
| Package manager | npm | Already installed; no new tool needed |
| Hosting | GitHub Pages | $0, native to GitHub Actions |
| CI | GitHub Actions | One workflow: build + deploy on push |

---

## 7. JSON contract between pipeline and site

All files written by `pipeline/export.py` into `site/public/data/`:

```
site/public/data/
├── upcoming.json          # next event + locked predictions for it
├── performance.json       # aggregates for dashboard (cumulative accuracy, calibration, etc.)
├── events.json            # all events with summary (for filters)
└── snapshots/
    └── <event_id>.json    # per-event detail (each event's picks + results)
```

Schemas are documented inline in `pipeline/export.py` and TypeScript types live in `site/src/lib/types.ts`. JSON files are the API contract — both sides import the same type.

---

## 8. Phased build

| Phase | Goal | Outcome |
|---|---|---|
| **0. Scaffold** | New directory layout; archive `api/` and `frontend/` to `_legacy/`; `npx create-next-app site` | Empty but valid repo structure on the new branch |
| **1. Pipeline** | Port scrape/ingest/features/train; add predict/grade/elo_update/export; run.py with `--pre-event` / `--post-event`; run schema migrations 007–009 | Single command produces JSON locally; Elo updates correctly after grading (verified on real data) |
| **2. Site shell** | Next.js + Tailwind + MDX scaffold; layout, nav, typography; routes wired to JSON | Site loads with real JSON, no styling polish yet |
| **3. Pages** | Build all three pages + blog renderer | Functional site reading real JSON |
| **4. Deploy** | GitHub Actions workflow for Pages | Live at `username.github.io/<repo>/` |
| **5. Polish** | Design pass — chart styling, dark mode, typography, color palette | "Genuinely nice-looking" hit |

### Done-criteria for Phase 1 (the most important one)
- [ ] `python -m pipeline.run --pre-event --event-id N` produces locked predictions for event N
- [ ] `python -m pipeline.run --post-event` grades them, updates Elo, and `fighters.current_elo_*` reflect new values
- [ ] Re-running `--post-event` is idempotent (no duplicate Elo rows, no duplicate gradings)
- [ ] `site/public/data/upcoming.json` and `performance.json` are written

---

## 9. Things explicitly NOT in scope

To prevent scope creep, this rewrite will not deliver:
- Fighter profile pages
- Bet tracker UI / ROI dashboard
- Value-bet UI (odds-implied probability, edge %, Kelly)
- Hosted Postgres / cloud DB
- Auth / user accounts
- Hosted backend API
- Docker
- Live in-event updates
- Custom domain

Some of these may make sense later; none are part of this rewrite.

---

## 10. Open questions / things to confirm during execution

1. The existing scraper's `scrape_schedule(year)` returns upcoming events — confirmed by reading `data/scrapers/espn_scraper.py:201`. Good.
2. The existing post-event pipeline already does Ingest → Stats → Grade → Elo in that order — confirmed at `data/post_event_pipeline.py:149`. The rewrite preserves this.
3. Calibration plot bucketing approach (e.g., 10 equal-width bins of predicted probability) — can be decided in Phase 3.
4. Whether `model_version` should be auto-generated (e.g., date-based) or human-chosen — recommend auto, format `xgb_YYYYMMDD_HHMM`.
