# Updating the Site

How to refresh data on https://patrickmcalinden.github.io/ufc-prediction/.

Architecture and rationale: [REWRITE_PLAN.md](REWRITE_PLAN.md).

## TL;DR

**Nothing — it's automated.** Two Windows scheduled tasks run the whole cycle:

| Task | When | What |
|---|---|---|
| `\UFC Predictor\Lock picks` | **Friday 21:00** | scrape next card → train → lock picks → export → PR → merge → Pages deploy |
| `\UFC Predictor\Grade results` | **Sunday 21:00** | reconcile completed events → stats → Elo rebuild → backfill → grade → export → PR → merge |

Friday night (not earlier) is deliberate: weigh-ins are Friday morning, so by
21:00 any fight that fell off the card is already gone from ESPN and we don't
lock picks for fights that never happen.

Install / reinstall / inspect:

```
powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-tasks.ps1
powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-tasks.ps1 -Remove
Get-ScheduledTask -TaskPath '\UFC Predictor\' | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskPath '\UFC Predictor\' -TaskName 'Lock picks'
```

See [Automation](#automation) below for what to check when a run fails.
The manual commands still work and are documented below.

---

## Manual runs

Two loops you can still drive by hand.

**Before an event — lock in predictions:**

```
# Postgres up (however you run it locally)
python -m pipeline.run --pre-event
git add site/public/data/
git commit -m "Lock picks: UFC <event>"
git push
```

**After an event — grade results + update Elo:**

```
python -m pipeline.run --post-event
git add site/public/data/
git commit -m "Grade UFC <event>: results"
git push
```

Each push triggers `.github/workflows/pages.yml` and the site redeploys in ~2 min.
Watch: https://github.com/patrickmcalinden/ufc-prediction/actions

---

## How the site is wired

```
Local Postgres ──► pipeline/export.py ──► site/public/data/*.json
                                                 │
                                                 ▼
                                       git push (committed JSON)
                                                 │
                                                 ▼
                                  .github/workflows/pages.yml
                                    • npm ci  +  npm run build
                                    • output: 'export' → site/out/
                                    • upload site/out/  →  GitHub Pages
                                                 │
                                                 ▼
                           https://patrickmcalinden.github.io/ufc-prediction/
```

The deployed site reads only static JSON. No API, no secrets, no runtime
DB connection. Everything happens at build time on your machine.

---

## The pipeline

One CLI, two modes, plus utility flags. All from `pipeline/run.py`.

| Mode | What it does |
|---|---|
| `python -m pipeline.run --pre-event` | scrape upcoming card → train every registered model → predict next event → export JSON |
| `python -m pipeline.run --post-event` | scrape results → scrape upcoming events (next card metadata) → scrape per-fight stats → **update Elo** + refresh `fighters.current_elo_*` → **backfill** locked picks for any late-add fight on a deployed event → grade picks (incl. voiding NC/Draw) → export JSON |
| `python -m pipeline.run --export-only` | rebuild site JSON without touching the DB |
| `python -m pipeline.run --elo-rebuild` | full Elo rebuild from scratch (rare; used after bulk data fixes) |

Useful flags:

- `--event-id N` — (pre-event) explicit event_id; default is the next upcoming event
- `--model NAME` — (pre-event) limit to one model; repeatable. Default = every registered model
- `--skip-train` — (pre-event) re-predict with the existing artifact, no retrain
- `--skip-stats` — (post-event) skip the slow per-fighter stats scrape
- `--force` — (pre-event) replace existing locked snapshots for this event + model

---

## Automation

The scheduled tasks call [`scripts/weekly.ps1`](scripts/weekly.ps1), which calls
[`pipeline/weekly.py`](pipeline/weekly.py). One entrypoint, three modes:

```
python -m pipeline.weekly              # both halves
python -m pipeline.weekly --no-lock    # grade only   (scripts\weekly.ps1 -Mode grade)
python -m pipeline.weekly --no-grade   # lock only    (scripts\weekly.ps1 -Mode lock)
```

Extra flags: `--lookback-days N` (how far back to reconcile, default 8),
`--no-git` (leave changes in the worktree), `--no-merge` (open the PR but don't
merge), `--allow-dirty` (skip the preflight), `--log-dir PATH`.

**Why `weekly.py` and not `run.py --post-event`.** `weekly.py` exists to work
around three narrow assumptions in the per-event path that only bite when a run
covers more than one event:

- `ingest.ingest_events(mode="reconcile")` takes only the *single* most recent
  past event, so an older unreconciled event in the same window is skipped.
  `weekly.py` loops over every event in the lookback window itself.
- `elo_update._incremental` uses a `fight_id` watermark, which skips events whose
  fights all got freshly-assigned low `fight_id`s. `weekly.py` always does a full
  rebuild.
- Commit / PR / merge was a manual step. Now it isn't.

**Preflight.** Before doing anything the run checks: Postgres answers (retrying
for ~60s, since it's a Docker container that may still be starting), the current
branch is `main`, the working tree is clean, and `gh` is authenticated. Any
failure exits **2** without touching the DB. A failure later in the cycle exits
**1** with a traceback. Success exits **0** — that's what Task Scheduler's "Last
Run Result" column shows.

**Logs.** Every run writes `logs/weekly-<date>_<time>.log` (gitignored). UTF-8,
because fighter names like "Procházka" crash the default Windows console
encoding mid-scrape.

**Missed runs.** Both tasks use `StartWhenAvailable` + `WakeToRun`, so a sleeping
machine gets woken and a machine that was off runs the task on next login. If you
miss a *whole* week, bump the lookback rather than running twice:

```
powershell -ExecutionPolicy Bypass -File scripts\weekly.ps1 -Mode grade -LookbackDays 30
```

**Events the pipeline missed entirely** get their results ingested (so Elo stays
correct) but never get retroactive picks — `events.deployed_at IS NULL` gates
every export, grade, and backfill query. That's intentional: the model artifact
retrained today has those fights in its training set, so a retro-prediction would
be leaky and would flatter the dashboard. A gap in the record is the honest
outcome.

**Known constraint.** The pipeline reads a *local* Docker Postgres, so this can't
move to GitHub Actions without first moving the DB to a hosted instance. The
machine has to be on (or wakeable) at the trigger time. See BACKLOG.md.

---

## Models

Defined in [`pipeline/models.py`](pipeline/models.py). Add a new entry to `MODELS` and the pipeline trains + predicts it automatically; the dashboard adds a tab for it.

Current registry:

| Name | Features | Notes |
|---|---|---|
| `elo_only`  | 6 Elo features + title flag (7 total) | Baseline |
| `elo_stats` | + historical striking, takedown accuracy, grappling aggression (22 total) | Production |

Each trained model writes:

```
model/artifacts/xgb_<name>.json        # the model
model/artifacts/xgb_<name>.meta.json   # model_version, CV metrics, features
```

`model_version` stored on each prediction equals the model name. Snapshots are immutable — the unique index `ux_predictions_locked (fight_id, model_version) WHERE is_locked` enforces this.

---

## Database

Local Postgres. Connection in `.env` (gitignored):

```
DATABASE_URL=postgresql://...@localhost:5432/ufc_predictor
```

Schema lives in [`sql/migrations/`](sql/migrations/). Apply new ones in order:

```
psql $DATABASE_URL -f sql/migrations/NNN_*.sql
```

Key invariants:

- **`events.deployed_at`** is set automatically the first time `--pre-event` writes a locked snapshot for that event. It's the gate that controls whether picks count toward the public dashboard.
- **`fighters.current_elo_*`** is denormalized for fast joins from `predict.py`. Refreshed by every `--post-event` after Elo is recomputed.
- **Post-event step order**: Ingest → Stats → Elo → Backfill → Grade. Elo runs before Backfill so the backfill can read `elo_ratings.elo_*_pre` for the just-completed fights. Grade runs last so any prediction the Backfill just inserted gets graded in the same run. `pipeline/run.py` enforces this order.

---

## Blog

Drop a markdown file under [`blog/`](blog/) with YAML frontmatter:

```
---
slug: my-post
title: Some title
date: 2026-05-30
summary: One-liner shown on the index.
---

# Post body in markdown.
```

The site picks it up at `/blog/<slug>/` on the next build. Nothing to run.

---

## What's NOT here

This project intentionally drops the bet tracker, fighter profile pages, and the FastAPI backend that the previous version had. The bets table still exists in Postgres but nothing reads or writes it. If you want any of those back, see the explicit non-goals in [REWRITE_PLAN.md](REWRITE_PLAN.md) §9.

---

## After the deploy: verifying

```
curl -sI https://patrickmcalinden.github.io/ufc-prediction/data/upcoming.json
```

`Last-Modified` should be within the last few minutes. If the page looks stale in your browser, hard-refresh (`Ctrl+Shift+R`).

Static export means all routes are pre-rendered (`.html` files under `site/out/`), so the hard-refresh 404 problem from the old SPA setup is gone.
