# Rebuild Spec

A self-contained specification for re-implementing this UFC prediction
project from scratch, incorporating lessons from the current
implementation. Companion to [LESSONS.md](LESSONS.md) — read both.

If you (or an LLM) are tasked with rewriting this system, the goal
is **one-shot correctness**: implementing every contract here on the
first pass should produce a working, deployable system that does
not repeat the mistakes documented in LESSONS.md.

---

## 0. Project shape

A static-site UFC fight predictor:

```
ESPN.com  ──scrape──►  Postgres  ──model──►  predictions
                          │
                          └──export──►  static JSON  ──►  GitHub Pages (React)
```

Three runtime contexts:

| Context | Has DB? | Has API? | Has predictions/grading? |
|---|---|---|---|
| Local dev | yes (Docker Postgres) | yes (FastAPI, optional) | yes |
| GitHub Pages (production) | **no** | **no** | reads committed JSON only |
| Tests / CI | depends | mocks | n/a |

**The deployed site is read-only.** All writes happen locally; the
operator re-exports JSON and pushes. There is no production database
and no secrets in the deployed bundle.

---

## 1. Data model

PostgreSQL. All `*_id` are `SERIAL PRIMARY KEY` unless stated. All
timestamps are `TIMESTAMPTZ`. All `*_at` columns default `NOW()`.

### 1.1 `fighters`
- `fighter_id`, `espn_id VARCHAR(64) UNIQUE NOT NULL`, `name NOT NULL`
- `nickname, weight_class, nationality, date_of_birth, stance`
- `height_cm NUMERIC, reach_cm NUMERIC`
- `record_wins INT DEFAULT 0, record_losses INT DEFAULT 0, record_draws INT DEFAULT 0`
- `is_active BOOLEAN DEFAULT FALSE` — filter for stats-scrape default
- `last_scraped_at TIMESTAMPTZ DEFAULT NOW()`

### 1.2 `events`
- `event_id`, `espn_event_id VARCHAR(64) UNIQUE`, `name, location`
- `event_date DATE`
- `scraped_at TIMESTAMPTZ DEFAULT NOW()`
- **`deployed_at TIMESTAMPTZ NULL`** — set by `predict_upcoming` (§5)
  for events whose date is today-or-future when predictions are
  generated. The single gate that splits "live deployed" from
  "backtest" predictions for the leaderboard. **Critical: nothing
  else writes this column.** Don't ever conflate "scraped" with
  "deployed."

### 1.3 `fights`
- `fight_id`, `espn_fight_id VARCHAR(64) UNIQUE`
- `event_id FK, fighter_a_id FK, fighter_b_id FK, winner_id FK NULL`
- `method VARCHAR(64), round INT, time VARCHAR(8), weight_class`
- `is_title_fight BOOLEAN DEFAULT FALSE`
- `fight_date DATE` (denormalized for query speed)
- `card_order INT NULL` — preserved from ESPN segment ordering
- **`is_cancelled BOOLEAN DEFAULT FALSE`** — the auto-cancel signal.
  Set by `mark_missing_fights_as_cancelled` and via manual fix for
  matchups outside the scrape window. **Never delete a fight row** —
  predictions, ELO, bets, fighter_stats all FK to it.
- `scraped_at TIMESTAMPTZ DEFAULT NOW()`

### 1.4 `predictions`
- `prediction_id, fight_id FK`
- `predicted_winner_id FK, win_probability NUMERIC(5,4)`
- `model_version VARCHAR(32)` — e.g. `'v1'`, `'v2'`
- `features_snapshot JSONB NULL` — optional reproducibility breadcrumb
- `actual_winner_id FK NULL, was_correct BOOLEAN NULL`
- `created_at TIMESTAMPTZ DEFAULT NOW()`

### 1.5 `elo_ratings`
**Load-bearing for honest backfills.** See LESSONS §B3.

- `rating_id, fighter_id FK, fight_id FK`
- `elo_standard NUMERIC(8,2), elo_modified NUMERIC(8,2)` — post-fight state
- `elo_standard_pre NUMERIC(8,2), elo_modified_pre NUMERIC(8,2)` — **pre-fight state**
- `rating_date DATE` — same as the fight's date
- `created_at TIMESTAMPTZ DEFAULT NOW()`

Two rows per fight (one per fighter). The "pre" columns let
`backfill_predictions` retrieve historical ELO without re-running
the entire pipeline.

### 1.6 `fighter_stats`
- `(fight_id, fighter_id) UNIQUE`
- Per-fight, per-fighter stats: `kd, sig_strikes_landed/attempted,
  total_strikes_landed/attempted, sd/sc/sg head/body/leg landed+attempted,
  takedowns_landed/attempted/slams/accuracy/slam_rate, submissions,
  reversals, advances, advance_to_{half_guard,back,mount,side}`
- `created_at TIMESTAMPTZ DEFAULT NOW()`
- `espn_event_id VARCHAR(64)` mirror for direct event-scoped queries

### 1.7 `bets`
- `bet_id, fight_id FK, fighter_backed_id FK`
- `odds, stake_usd, payout_usd, profit_usd`
- `result VARCHAR(16)` — `'win'|'loss'|'push'|'pending'`
- `notes TEXT, placed_at TIMESTAMPTZ DEFAULT NOW()`

### 1.8 NOT in the data model

- **No `blog_posts` table.** Blog reads markdown files directly from
  `/blog/*.md` with frontmatter. A table existed historically but is
  unused — drop it in the rewrite.
- **No "model artifacts" metadata table.** The two XGBoost JSON files
  on disk (`model/artifacts/xgb_v*.json`) are the artifact store.

---

## 2. Invariants

These hold across every code path. Violating one means the live site
is wrong even though every individual script reports success.

1. **Filter coherence.** The static exporter and the live FastAPI
   endpoint that share a name must apply identical filter clauses.
   Specifically, for any `(predictions.json, GET /predictions)`,
   `(results.json, GET /predictions/results)`, `(models.json, GET
   /predictions/models)` pair: the WHERE clauses must match line-for-line
   semantically. **Test fixture:** export both, diff the IDs.

2. **Idempotent upserts with COALESCE for "fills-once" columns.**
   `winner_id`, `method`, `round`, `time` on `fights` use
   `COALESCE(EXCLUDED.x, fights.x)`. Other columns overwrite
   unconditionally. Never NULL-out a result field on re-scrape.

3. **`is_cancelled` is the only cancellation signal.** Never delete
   fight rows. Never overload `winner_id IS NULL` to mean cancelled —
   that's the "not yet decided" state.

4. **`deployed_at` is the only live-vs-backtest signal.** Never
   special-case "the last N events" or "events deployed_at IS NOT
   NULL OR fight_id > N" — those drift. The gate is a single boolean
   on a single column.

5. **Pre-event ELO is preserved per fight.** `elo_standard_pre` /
   `elo_modified_pre` are written at the same time as the post-fight
   values. Backfills depend on them.

6. **Static export is the only path to the deployed site.** Frontend
   code MUST NOT call `/api/*` at runtime; everything reads
   `frontend/public/data/*.json`. Detect static mode with an env
   flag (e.g. `IS_STATIC`) at build time.

---

## 3. Pipeline contracts

### 3.1 Scraper (`data/scrapers/espn_scraper.py`)

ESPN's MMA gamepackage exposes a JSON blob inside the HTML; parse
that, don't scrape the DOM. Key methods:

| Method | Input | Output (dict keys) |
|---|---|---|
| `scrape_schedule(year)` | int | `[{espn_event_id, name, location, event_date, url}]` |
| `scrape_event_fights(url, espn_event_id)` | strings | `[{espn_fight_id, espn_event_id, fighter_a_espn_id, fighter_b_espn_id, winner_espn_id, method, round, time, is_title_fight, card_order}]` |
| `scrape_fighter_profile(espn_id)` | str | `{espn_id, name, nickname, weight_class, nationality, dob, height_cm, reach_cm, stance, wins, losses, draws}` |
| `scrape_fighter_stats(espn_id)` | str | `[{...37 stat fields per fight...}]` |

Winner extraction: ESPN's `awy` (away) and `hme` (home) corners each
carry an `isWin` flag. Check both `corner.get('isWin')` and
`corner.get('ath', {}).get('isWin')` — older payloads put it on the
inner athlete node. This flag is **authoritative**; ignore listicle
summaries (see LESSONS §F1).

### 3.2 Loader (`data/loaders/postgres_loader.py`)

| Method | Conflict key | Behavior |
|---|---|---|
| `upsert_fighter` | `espn_id` | Overwrite all |
| `upsert_event` | `espn_event_id` | Overwrite all. **Never touches `deployed_at`.** |
| `upsert_fight` | `espn_fight_id` | COALESCE `winner_id, method, round, time`. Overwrite the rest. |
| `mark_missing_fights_as_cancelled(espn_event_id, active_ids)` | n/a | UPDATE: `is_cancelled=TRUE` for fights not in `active_ids`. |
| `upsert_fighter_stats` | `(fight_id, fighter_id)` | Overwrite all stats. |

### 3.3 Ingest (`data/ingest.py`)

Three modes:
- `--all` — every year since 2005. One-time bootstrap.
- `--year YYYY` — backfill a single season.
- `--upcoming` — last 3 days + next future event (default in
  post_event_pipeline).
- `--reconcile` — only the single most recent event in the last
  7 days (used when you want to force-re-pull results without
  the rest).

Per event: scrape profiles → upsert fighters → upsert fights →
`mark_missing_fights_as_cancelled` against the event's active list.

**Open issue (see LESSONS §B1):** `--upcoming`'s 3-day window misses
older events whose cards changed. The rewrite should either widen this
window or run cancellation reconciliation against any event with
ungraded predictions, not just freshly-scraped ones.

### 3.4 ELO pipeline (`model/features/elo_pipeline.py`)

`run_elo_pipeline(incremental: bool = True)`:

- **Full** — `TRUNCATE elo_ratings RESTART IDENTITY`, then replay
  every fight with `winner_id IS NOT NULL` ordered by
  `(fight_date, fight_id)`. Use after bulk reseeds or schema changes.
- **Incremental** — watermark = `MAX(fight_id) FROM elo_ratings`.
  Seed in-memory state from each fighter's latest existing row
  (DISTINCT ON), then process only fights with `fight_id > watermark`.

Both modes write two rows per fight: `(fighter_id, fight_id,
elo_standard_pre, elo_standard, elo_modified_pre, elo_modified,
rating_date)`. The "pre" columns are non-negotiable — they unlock
backfills (§5).

Sanity check: after a full replay, `SELECT name, elo_modified FROM
fighters JOIN ... ORDER BY elo_modified DESC LIMIT 10` should return
Jones, Makhachev, GSP, Khabib, etc. If not, the date ordering or
seeding logic is wrong.

### 3.5 Stats scrape

`run_stats_scrape(active_only=True)` — iterates `fighters WHERE
is_active = TRUE` (~700 in steady state) and pulls per-fight stats.
Takes 20-40 minutes. Default `active_only` to `True`; only flip it
when bootstrapping. Surface it as `--all-fighters` on the CLI for
clarity.

### 3.6 Grading (`data/grade_predictions.py`)

Single SQL filter:

```sql
WHERE p.was_correct IS NULL
  AND e.deployed_at IS NOT NULL
  AND f.is_cancelled = FALSE       -- propose adding this in rewrite
```

(The current implementation lacks `is_cancelled = FALSE`; it works
because the loop skips `winner_id IS NULL` and cancelled fights always
have NULL winner. But the filter is more explicit.)

For each row: compare `predicted_winner_id` to `fights.winner_id`; set
`was_correct` and `actual_winner_id`. Skip rows where `winner_id IS
NULL` (fight not decided).

### 3.7 Post-event pipeline (`data/post_event_pipeline.py`)

Single CLI entry point. Steps in order:

1. **Ingest** — `--upcoming` mode by default.
2. **Stats** — `active_only=True` by default; `--skip-stats` to skip.
3. **Grade** — invoke `grade_predictions`.
4. **ELO** — `run_elo_pipeline(incremental=True)`.

**Proposed rewrite addition: Step 5 — Reconcile.** Detect:
- Settled fights on deployed events with no prediction →
  invoke `backfill_predictions` automatically.
- Events with ungraded predictions whose fights have winners →
  log loudly; usually means `is_cancelled` or `deployed_at` is wrong.

This step closes the "pipeline ✓ but site wrong" gap (LESSONS §A2).

---

## 4. Model

### 4.1 Features

- **v1 (7 features):** `elo_std_pre_a, elo_mod_pre_a, elo_std_pre_b,
  elo_mod_pre_b, elo_diff_std, elo_diff_mod, is_title_fight`
- **v2 (22 features):** v1 + per-fighter `str_acc, str_vol, td_acc,
  grap_agg, str_def` + 5 diff features.

Stored as `xgb_v1.json` / `xgb_v2.json` (XGBoost native format).
**Gitignored** — version-control elsewhere (artifact store, Git LFS,
or a build step that retrains on demand). A fresh worktree without
these files crashes any prediction script.

### 4.2 Prediction modes

**`predict_upcoming.py` — pre-event:** Scans fights in
`event_date >= today - 60 days`, `is_cancelled = FALSE`. ELO source:
**latest** row per fighter from `elo_ratings`. Inserts predictions
for both v1 and v2 per fight, then `UPDATE events SET deployed_at =
NOW() WHERE event_id = ANY(future_event_ids) AND deployed_at IS NULL`.

**`backfill_predictions.py` — post-event late additions:**
Targeted at specific `--fight-ids`. ELO source: `elo_standard_pre`
on the existing `elo_ratings` row for that fight (or, as fallback,
the most recent rating strictly before that fight's `rating_id`).
Used when a card changed mid-week and `predict_upcoming` missed the
new matchup.

Both share the same XGBoost forward pass; only the ELO source differs.

---

## 5. Static exporter (`data/loaders/export_static_api.py`)

Writes seven JSON outputs to `frontend/public/data/`. **Each output
must mirror its FastAPI counterpart in `api/routers/`.** Treat the
exporter as a SQL view over the live API.

| Output | Mirrors | Filter |
|---|---|---|
| `fighters.json` | `GET /fighters` | none — full list, ordered by `record_wins DESC` |
| `fighters/<id>.json` + `_fights.json` | `GET /fighters/{id}` | per-fighter detail + fights `WHERE fight_date IS NOT NULL` |
| `predictions.json` | `GET /predictions` | `f.is_cancelled = FALSE AND (e.deployed_at IS NOT NULL OR e.event_date >= CURRENT_DATE)` |
| `results.json` | `GET /predictions/results` | `p.was_correct IS NOT NULL AND f.is_cancelled = FALSE` LIMIT 500 |
| `models.json` | `GET /predictions/models` | JOIN events, `e.deployed_at IS NOT NULL`, GROUP BY model_version. High-conf sub-query: `win_probability > 0.70 AND deployed_at IS NOT NULL` |
| `bets.json` | `GET /bets` | LIMIT 50 |
| `blog/*.json` + `blog.json` | `GET /blog`, `GET /blog/{slug}` | Reads markdown from `/blog/*.md` with frontmatter — does **not** touch the DB |

**Rewrite recommendation:** Factor the filter clauses into a single
Python module (e.g. `data/filters.py`) and have both the exporter and
the API import from it. Drift between these has cost time multiple
times (see LESSONS §C1 + git log "Restore X.json" commits).

---

## 6. Frontend

React + Vite. Pages under `frontend/src/pages/*.jsx`:

| Page | Purpose | Data source |
|---|---|---|
| `Home.jsx` | Landing dashboard summary | `predictions.json` + `results.json` |
| `Predictions.jsx` | Upcoming/recent predictions | `predictions.json` |
| `Results.jsx` | Graded past predictions | `results.json` |
| `ModelLeaderboard.jsx` | Per-model accuracy | `models.json` |
| `Fighters.jsx` | Directory list | `fighters.json` |
| `FighterProfile.jsx` | Single fighter detail | `fighters/<id>.json` + `_fights.json` |
| `BetTracker.jsx` | Bets view | `bets.json` |
| `Blog.jsx` / `BlogPost.jsx` | Posts | `blog.json` + `blog/<slug>.json` |

**Critical constraint:** the deployed bundle has **no API access**.
The API client (`frontend/src/lib/api.js`) must short-circuit to
`staticJson()` lookups when `IS_STATIC` (build-time env var) is set.
`createBet`, `settleBet`, `gradePredictions` throw on the static build —
those are local-only ops.

### 6.1 GitHub Pages routing

Pages serves files; it doesn't know about React Router. The build
step (`.github/workflows/pages.yml`) does `cp dist/index.html
dist/404.html` so any unknown path serves the SPA shell (HTTP 404
but correct HTML). Client-side routing picks up from there. DevTools
will show 404 for deep links — that's expected.

---

## 7. Deploy flow

The canonical local loop:

```sh
docker compose up -d                          # local Postgres
python -m data.post_event_pipeline             # ingest + stats + grade + ELO
.\scripts\update_data.bat                       # export + git add
git diff --stat --cached                       # sanity check (~50-100 files)
git commit -m "Refresh static data: <event>"
git push origin HEAD:main                      # or via PR (preferred)
```

GitHub Actions builds & deploys in ~30 seconds. CDN serves fresh
content immediately; browser may cache the SPA shell — hard-refresh
(Ctrl+Shift+R) to force reload.

### 7.1 Required env vars (`.env`, gitignored)

- `DATABASE_URL=postgresql://ufc_user:ufc_password@localhost:5432/ufc_predictor`
- `BET_API_KEY=...` — for the local-only bet endpoints

### 7.2 Required model artifacts

- `model/artifacts/xgb_v1.json`
- `model/artifacts/xgb_v2.json`

Gitignored. Document where they live (separate artifact store or
retraining script) so a fresh clone can produce them.

---

## 8. Operational invariants checklist

Run through this list when something appears wrong on the deployed
site:

- [ ] `SELECT event_id, name, deployed_at FROM events ORDER BY event_date DESC LIMIT 5;` — does the event have a deploy timestamp?
- [ ] `SELECT fight_id, is_cancelled, winner_id FROM fights WHERE event_id = X;` — every settled fight has a winner; cancelled fights have `is_cancelled = TRUE`.
- [ ] `SELECT COUNT(*) FROM predictions p JOIN fights f ON ... WHERE f.event_id = X AND p.was_correct IS NULL;` — should be zero for completed events on deployed gates.
- [ ] `SELECT COUNT(*) FROM fights f LEFT JOIN predictions p ON ... WHERE f.event_id = X AND f.is_cancelled = FALSE AND p.prediction_id IS NULL;` — settled fights with no prediction (the §B2 gap).
- [ ] `git diff --stat --cached` line count is in the expected range.
- [ ] GitHub Actions build succeeded (`gh run list --branch main --limit 1`).
- [ ] Hard-refresh in the browser before declaring stale.

---

## 9. Things to add in the rewrite (open work)

In rough priority:

1. **Centralized filter helpers** — eliminate the
   exporter-vs-API drift problem at the source. (LESSONS §C1)
2. **Auto-backfill in `post_event_pipeline`** — detect settled
   fights with no prediction, run `backfill_predictions` for them.
   (LESSONS §B2)
3. **Wider reconcile window or trigger** — re-run
   `mark_missing_fights_as_cancelled` for any event with ungraded
   predictions, not just events freshly scraped. (LESSONS §B1)
4. **Integration test for the export round-trip** — fixture DB,
   run export, diff against expected JSON. Catches "Restore X.json"
   regressions before they ship.
5. **Cancelled-fight filter in `grade_predictions`** — currently
   implicit (NULL winner); make explicit.
6. **Replace `print("✓")` with `print("OK")`** or set
   `PYTHONIOENCODING=utf-8` to stop the harmless-but-noisy Windows
   crashes. (LESSONS §E1)
7. **Document model-artifact provisioning** — fresh clones currently
   need manual copy. (LESSONS §E5)
8. **Cancellation filter on `/models`** — pre-existing leak from
   the cancelled-fight cleanup. (LESSONS §C2)

---

## 10. Drift between SQL and SQLAlchemy models

The current `api/db/models.py` is missing several columns that exist
in the SQL migrations. Not blocking the static site (the exporter
uses raw SQL) but a foot-gun for anyone writing API code. Fix in
the rewrite:

- `Fighter` is missing `last_scraped_at`
- `Event` is missing `scraped_at`
- `Fight` is missing `scraped_at`
- `EloRating` is missing `created_at`
- `Bet` is missing `placed_at`
- `BlogPost` is missing `tags TEXT[]` (or drop the table entirely
  since blog reads from markdown — see §1.8)
- No SQLAlchemy model exists for `fighter_stats` at all
