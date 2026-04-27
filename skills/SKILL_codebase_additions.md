# SKILL: Adding Things to the Codebase (Static-Site Edition)

## Purpose
The deployed site (GitHub Pages) is **fully static** — it reads from JSON
files committed under `frontend/public/data/`. There is **no live API**,
**no database connection**, and **no secrets** in the repo. This skill is
the canonical checklist for adding anything new (a page, a route, a data
field, a model output, a blog post, a fighter detail, …) without
breaking that contract.

Reuse this skill **every time** you touch the codebase.

## The Hard Rules

1. **No secrets in git.** `.env`, `.env.local`, `*.env` are gitignored.
   Only `.env.example` (placeholder values) is committed.
2. **No live network calls in PROD.** All read endpoints in
   `frontend/src/lib/api.js` short-circuit on `IS_STATIC` and read from
   `/data/*.json`. Write operations (`createBet`, `settleBet`) throw in
   static mode — they only work locally against a dev backend.
3. **The deployed site only depends on `frontend/public/data/`.**
   If a new feature needs data, the data must be exported as JSON into
   that directory, then committed.

## When You Add Something — the 5-step checklist

### 1. Decide where the data comes from
- **From the database** → add a new exporter function in
  `data/loaders/export_static_api.py`. Mirror the FastAPI route shape so
  the JSON file is a drop-in for the live response.
- **From a flat file** (markdown blog posts, model artifacts) → write
  directly into `frontend/public/data/` from a small script.
- **From a third-party API** → fetch at export-time on your local
  machine. Never call the third party from the browser at runtime.

### 2. Add the static read path in `frontend/src/lib/api.js`
Every method must have an `if (IS_STATIC) return staticJson(...)` branch
**before** any `fetch(BASE_URL + ...)` call. Pattern:

```js
getThing: (id) => {
  if (IS_STATIC) return staticJson(`things/${id}.json`);
  return get(`/things/${id}`);
},
```

If you forget this, the production build will silently try to hit
`localhost:8000` and fail.

**Filters that the live API applies must be re-applied client-side in
the static branch.** The static export ships *all* rows for an
endpoint; if the live route accepts e.g. `?model_version=v2`, the
static branch must filter the loaded array itself:

```js
getResults: (modelVersion = null) => {
  if (IS_STATIC) {
    return staticJson("results.json").then((rows) =>
      modelVersion ? rows.filter((r) => r.model_version === modelVersion) : rows
    );
  }
  const params = modelVersion ? `?model_version=${modelVersion}` : '';
  return get(`/predictions/results${params}`);
},
```

If you forget this, toggles and selectors silently do nothing in
production and you get duplicate rows when the data has multiple
variants per logical record.

### 3. Re-export and verify locally
```
bash scripts/update_data.sh        # macOS / Linux / Git Bash
scripts\update_data.bat            # Windows cmd
```
Then:
```
cd frontend
npm run build
npm run preview
```
Open the preview URL and click the new feature. If it works in
`preview` (which serves the built bundle), it will work on Pages.

### 4. Audit before committing
Run this from the repo root and check the output is clean:
```
git status --short
git diff --stat --cached
git ls-files --others --ignored --exclude-standard | grep -E '\.env'   # should be empty
git grep -nE 'BET_API_KEY|DATABASE_URL=|password\s*=\s*['\''\"]' -- ':!*.example' ':!skills/*' ':!docs/*'
```
- No `.env*` file in `git status`.
- No real credential strings — only env-var *names* are allowed in code.

### 5. Commit and push
```
git add frontend/public/data frontend/src <new files>
git commit -m "<scope>: <one-line summary>"
git push
```
GitHub Pages rebuilds from the pushed `frontend/public/data/` JSON.

## Files You Care About

```
data/loaders/export_static_api.py    # source of every JSON file under /data
frontend/public/data/                # what the deployed site actually reads
frontend/src/lib/api.js              # the dual-mode (dev API / static) shim
scripts/update_data.{sh,bat}         # one-shot refresh + git add helper
.gitignore                           # the secrets fence — do not weaken
.env.example                         # the only env file allowed in git
```

## Anti-patterns (do not do these)

- ❌ Hard-coding the API URL anywhere in `frontend/src/`.
- ❌ Adding a new method to `api.js` without an `IS_STATIC` branch.
- ❌ Committing `frontend/.env` or any other `.env*` (except `.env.example`).
- ❌ Importing `psycopg2`, `requests`, or any network client into
  `frontend/` source.
- ❌ Bypassing `export_static_api.py` and writing JSON by hand — the
  next refresh will overwrite your edit.
- ❌ Pushing without running `update_data.sh` if the change touches data.

## When to Update This Skill
Any change to the deploy model — new hosting target, a new env file
location, a new directory under `frontend/public/`, a new exporter — needs a
matching edit here in the same commit. Stale skills mislead future runs.
