# Backlog

Follow-ups from the rewrite. Each item is self-contained — pick one up
without needing the rest of the project context. Items are roughly
ordered by leverage / effort, not strict priority. Anything explicitly
out of scope for this rewrite is in §"Deferred" at the bottom.

For the bigger picture see [REWRITE_PLAN.md](REWRITE_PLAN.md) (the
architecture and decisions doc) and [UPDATING.md](UPDATING.md) (the
operating guide).

---

## 1. Verify Phase 1 done-criteria against a graded event

**Why:** the rewrite was verified against the historical v1/v2 picks
already in the DB, but the *new* v1/v2 picks for event 5 (May 30
card) haven't been graded yet. The first `--post-event` run after that
card is the real end-to-end check that grading, Elo update,
denormalized `fighters.current_elo_*` refresh, and the dashboard
aggregation all behave correctly when the new model versions get their
first graded picks.

**What to do:**
1. After the May 30 card finishes, run:
   ```
   python -m pipeline.run --post-event
   ```
2. Confirm the log shows `[grade]` graded ≥1 of the 13 locked picks
   per model, `[elo]` processed the new fights, and
   `fighters_refreshed` is > 0.
3. Spot-check the dashboard at https://patrickmcalinden.github.io/ufc-prediction/performance/
   — v1 and v2 tabs should both show graded counts jumping by ~13.
4. Re-run `--post-event` once and verify nothing changes (idempotency).

**Where:** `pipeline/run.py`, `pipeline/grade.py`, `pipeline/elo_update.py`.

---

## 2. Bump GitHub Actions runners to Node 24

**Why:** the `pages.yml` workflow uses several actions pinned to
Node 20, which GitHub will force off the runner on Sep 16, 2026.
Default flip to Node 24 happens Jun 2, 2026. The deploy will start
emitting warnings before then.

**What to do:**

Option A (one-line opt-in, immediate): add to `.github/workflows/pages.yml`
under the `env:` block (top level or per-job):

```yaml
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
```

Option B (proper fix): upgrade each pinned action to its Node-24-capable
release once those tags are out. Affected pins:
- `actions/checkout@v4`
- `actions/setup-node@v4`
- `actions/configure-pages@v5`
- `actions/upload-pages-artifact@v3`
- `actions/deploy-pages@v4`

**Where:** [.github/workflows/pages.yml](.github/workflows/pages.yml)

---

## 3. Drop the `_legacy/` archive

**Why:** ~5000 archived files (old FastAPI app, Vite frontend, bet
tracker data, old planning docs) sit in `_legacy/` for safekeeping
while we trust the rewrite. They're useful as a reference for "how did
the old system work" — but once that's not interesting, they're dead
weight in `git grep`, IDE indexing, and the repo size.

**What to do:**
1. Confirm nothing in `pipeline/` or `site/` imports from `_legacy/`:
   ```
   grep -rn "_legacy" pipeline/ site/src/
   ```
   (Should return nothing.)
2. Delete it:
   ```
   git rm -r _legacy/
   git commit -m "Drop _legacy/ archive"
   ```
3. The git history still contains everything if anyone needs to recover.

**Where:** `_legacy/`

**Don't do this** until you're sure you don't need any reference
material from the old `data/`, `model/`, `api/`, or `frontend/` code.

---

## 4. Add a `model_runs` table for per-retrain provenance

**Why:** right now each prediction row records the `model_version`
string (e.g. "v1") and `model_artifact` filename, but there's no
durable record of *which exact train run* produced the current
artifact. The sidecar `xgb_<name>.meta.json` has `trained_at` +
CV metrics but it gets overwritten on every retrain. After a retrain
you can't reconstruct which past predictions came from which model
fit.

**What to do:**

Add a migration `sql/migrations/011_model_runs.sql`:

```sql
CREATE TABLE model_runs (
  run_id          SERIAL PRIMARY KEY,
  model_version   VARCHAR(64) NOT NULL,       -- e.g. "v1"
  trained_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  artifact_path   VARCHAR(256) NOT NULL,
  cv_accuracy     NUMERIC(6,4),
  cv_logloss      NUMERIC(7,4),
  n_samples       INT,
  features        JSONB,
  notes           TEXT
);

ALTER TABLE predictions
  ADD COLUMN IF NOT EXISTS model_run_id INT REFERENCES model_runs(run_id);

CREATE INDEX IF NOT EXISTS idx_predictions_model_run ON predictions(model_run_id);
```

Then in `pipeline/train.py:train_one()` after saving the artifact,
INSERT a row into `model_runs` and return its `run_id`. In
`pipeline/predict.py:_predict_for_model()` accept that `run_id` and
include it in the INSERT.

The dashboard could then add a chart of "CV accuracy across training
runs" or annotate the cumulative-accuracy line with retrain timestamps.

**Where:** `sql/migrations/`, `pipeline/train.py`, `pipeline/predict.py`,
optional UI work in `site/src/app/performance/`.

**Mentioned in:** [REWRITE_PLAN.md §4 "Recommendations the user can ignore"](REWRITE_PLAN.md#4--schema--what-stays-what-changes).

---

## 5. Drop unused `bets` and `blog_posts` tables

**Why:** the rewrite stopped using both — bets are tracked off-site,
blog posts live as MDX files in `blog/`. The tables still exist (with
historical bet data) but no code reads or writes them. Keeping them
clutters `\d` listings and is slightly misleading for anyone exploring
the schema.

**What to do:**

Decide first whether you care about the historical bet rows:
- **Yes** — `pg_dump --table=bets ufc_predictor > bets_archive.sql`
  somewhere safe, then drop.
- **No** — straight drop.

Add a migration `sql/migrations/012_drop_unused_tables.sql`:

```sql
DROP TABLE IF EXISTS bets;
DROP TABLE IF EXISTS blog_posts;
```

**Where:** `sql/migrations/`

---

## Deferred (explicitly out of scope, may want later)

These were discussed during the rewrite and intentionally dropped.
Listed here so future-you doesn't re-derive the decision from scratch.
See [REWRITE_PLAN.md §9](REWRITE_PLAN.md#9-things-explicitly-not-in-scope)
for the original rationale.

| Feature | Why dropped | Would-be effort if revisited |
|---|---|---|
| **Fighter profile pages** | Out of scope for the portfolio version. Data is in Postgres + scraped JSON. | New `/fighters/[id]/` route, export per-fighter snapshot JSON. Medium. |
| **Bet tracker / ROI UI** | User bets off-site; the app is for prediction/analysis. | Re-introduce `bets` table writes, new `/bets/` route. Medium-large (needs auth or local-only edit flow). |
| **Value-bet UI (odds + Kelly)** | "No — just show model probabilities" — user preference. | Scrape books, compute edge, render side-by-side with `win_probability`. Medium. |
| **Hosted Postgres** | Local-only chosen so user keeps psql/DataGrip in their daily loop. Now also the one thing pinning the weekly automation to this machine — the Task Scheduler jobs in [UPDATING.md](UPDATING.md#automation) need the PC awake Friday/Sunday 21:00. | Swap `DATABASE_URL` to Neon/Supabase; pipeline still runs locally OR in CI. Small DB change, larger workflow change if CI runs the pipeline — CI would also need `model/artifacts/*.json` committed (currently gitignored) or rebuilt each run, plus a `DATABASE_URL` secret. |
| **Live in-event updates** | Static-site model assumes nothing changes between pushes. | Out of architecture; would need a runtime API. Large. |
| **Custom domain** | `username.github.io/ufc-prediction` is fine for now. | Standard Pages custom domain + CNAME. Tiny. |

---

## How to use this file

When you pick up an item:
1. Branch: `git checkout -b <area>/<item-slug>` (e.g. `infra/node-24-bump`)
2. Do the work, push, open a PR against `main`.
3. Update this file in the same PR — remove the item or move it into a "Done" log if you want history.
4. The Pages deploy runs automatically on merge to main.

If you add a new item: keep the per-item shape (Why / What to do / Where).
Self-contained beats brief.
