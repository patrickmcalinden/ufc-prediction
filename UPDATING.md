# Updating the Site

How to refresh data on https://patrickmcalinden.github.io/ufc-prediction/.

## TL;DR (the loop you'll run after every event)

```
docker compose up -d                                # local Postgres
python -m data.post_event_pipeline                  # ingest results + grade
.\scripts\update_data.bat                           # export JSON + git add
git commit -m "UFC <event>: results + grades"
git push
```

GitHub Actions rebuilds and deploys in ~2 min. Watch:
https://github.com/patrickmcalinden/ufc-prediction/actions

---

## How the site is wired

```
Local Postgres  ──►  data/loaders/export_static_api.py  ──►  frontend/public/data/*.json
                                                                       │
                                                                       ▼
                                                       git push (committed JSON)
                                                                       │
                                                                       ▼
                                                .github/workflows/pages.yml
                                                  • npm ci  +  npm run build
                                                  • cp dist/index.html dist/404.html
                                                  • upload dist/  →  GitHub Pages
                                                                       │
                                                                       ▼
                                          https://patrickmcalinden.github.io/ufc-prediction/
```

**The deployed site has no API access and no secrets.** It only reads the
JSON files inside `frontend/public/data/`. To change what you see online,
you change those files (and only those) — the export script is the
canonical way to write them.

---

## Step-by-step

### 1. Start your local stack

```
docker compose up -d                                # Postgres on :5432
uvicorn api.main:app --reload                       # only if you'll touch /bets
```

Your `.env` (gitignored, never pushed) holds `DATABASE_URL` and
`BET_API_KEY`. The deployed site never sees either.

### 2. Update the source data

| What changed | Run this |
|---|---|
| New upcoming card to predict | `python -m model.predict_upcoming` |
| Event just finished | `python -m data.post_event_pipeline` |
| Already ingested, just need grading | `python -m data.grade_predictions` |
| Added/settled a bet | hit your **local** API (`POST http://localhost:8000/bets` or `PATCH /bets/{id}/settle`) — uses `BET_API_KEY` |
| Wrote a blog post | drop a `.md` file under `blog/` with frontmatter (`title`, `date`, `slug`, `summary`) |

### 3. Export to static JSON

```
.\scripts\update_data.bat        # PowerShell / cmd
bash scripts/update_data.sh      # if you ever use Git Bash
```

Both run `python -m data.loaders.export_static_api` and `git add` the
results. Output (under `frontend/public/data/`):

| File | Source endpoint | Drives |
|---|---|---|
| `predictions.json` | `GET /predictions` | Predictions page |
| `results.json` | `GET /predictions/results` | Results page |
| `models.json` | `GET /predictions/models` | Models leaderboard + selector |
| `bets.json` | `GET /bets` | Bet Tracker page |
| `fighters.json` + `fighters/<id>.json` + `fighters/<id>_fights.json` | `GET /fighters[/...]` | Fighters list + profiles |
| `blog.json` + `blog/<slug>.json` | `GET /blog[/...]` | Blog index + posts |

### 4. Review

```
git diff --stat --cached
```

Eyeball the line count. A typical post-event refresh touches
`predictions.json`, `results.json`, `models.json`, plus a handful of
`fighters/*_fights.json`. If you see thousands of files churning, you
probably got date stringification differences — usually fine, but
worth a glance.

### 5. Commit + push

```
git commit -m "UFC 312: results + grades"
git push
```

Pushing to `main` triggers `.github/workflows/pages.yml`. Watch the run
at https://github.com/patrickmcalinden/ufc-prediction/actions.
On success, https://patrickmcalinden.github.io/ufc-prediction/ updates
within seconds of the workflow turning green.

---

## After the deploy: verifying

If you want to confirm a specific file went live:

```
curl -sI https://patrickmcalinden.github.io/ufc-prediction/data/results.json
```

Look at `Last-Modified` — should be within the last few minutes.

If the page looks stale in your browser: **hard-refresh** (`Ctrl+Shift+R`).
The CDN serves fresh content, but your browser may hold an older copy.

---

## Routes 404 on hard-refresh — expected

`/ufc-prediction/results`, `/ufc-prediction/fighters/123`, etc. return
HTTP **404 Not Found** on a hard refresh. This is normal: GitHub Pages
has no `results.html` to serve. Our workflow copies `index.html` to
`404.html`, so the SPA shell still loads with status 404, and React
Router picks up the path client-side. The user sees the right page;
only DevTools shows the 404.

If a route ever loads as a blank GitHub-branded 404 page instead of
your app, the fallback step in the workflow didn't run — check the
"Build" job logs for the `cp dist/index.html dist/404.html` step.

---

## What never gets updated by this loop

- The deployed site is **read-only**: `createBet` and `settleBet` in
  [frontend/src/lib/api.js](frontend/src/lib/api.js) throw on the
  static build. You add/settle bets locally, then re-export.
- Live odds, live event data: there is none. Everything on the page
  is a snapshot from your last `update_data` run.

---

## When you add a *new* feature (not just data)

Follow [skills/SKILL_codebase_additions.md](skills/SKILL_codebase_additions.md).
The short version:

1. Add an exporter in `data/loaders/export_static_api.py` that mirrors
   the API response shape into a new JSON file.
2. Add a method in [frontend/src/lib/api.js](frontend/src/lib/api.js)
   with an `if (IS_STATIC) return staticJson(...)` branch first.
3. `npm run build && npm run preview` from `frontend/` to test the
   prod path before pushing.
4. Then run the standard update loop above.
