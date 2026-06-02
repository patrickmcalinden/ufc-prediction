# Updating the Site

How to refresh data on https://patrickmcalinden.github.io/ufc-prediction/.

Architecture and rationale: [REWRITE_PLAN.md](REWRITE_PLAN.md).

## TL;DR

Two loops you actually run.

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
| `python -m pipeline.run --post-event` | scrape results → scrape upcoming events (next card metadata) → scrape per-fight stats → grade picks (incl. voiding NC/Draw) → **update Elo** → refresh `fighters.current_elo_*` → export JSON |
| `python -m pipeline.run --export-only` | rebuild site JSON without touching the DB |
| `python -m pipeline.run --elo-rebuild` | full Elo rebuild from scratch (rare; used after bulk data fixes) |

Useful flags:

- `--event-id N` — (pre-event) explicit event_id; default is the next upcoming event
- `--model NAME` — (pre-event) limit to one model; repeatable. Default = every registered model
- `--skip-train` — (pre-event) re-predict with the existing artifact, no retrain
- `--skip-stats` — (post-event) skip the slow per-fighter stats scrape
- `--force` — (pre-event) replace existing locked snapshots for this event + model

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
- **Grade order is fixed**: Ingest → Stats → Grade → Elo. Elo must run after Grade because it reads `fights.winner_id` which Grade reconciles. `pipeline/run.py` enforces this order.

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
