# Rebuild Reference

Concrete snippets and parameter values needed to actually re-implement
this system. Companion to [REBUILD_SPEC.md](REBUILD_SPEC.md) (which
covers the architecture, contracts, and invariants) and
[LESSONS.md](LESSONS.md) (operational pain points).

> Every code block below is paraphrased from the actual implementation
> — exact enough to reproduce behavior, not a verbatim copy. Read the
> referenced files for the literal source.

---

## 1. ELO math

`model/features/elo_config.py`:

```python
ELO_CONFIG = {
    "starting_rating":  1500.0,
    "base_k":           32.0,
    "elite_threshold":  1600.0,
    "elite_multiplier": 1.5,
    "weak_threshold":   1400.0,
    "weak_multiplier":  0.75,
}
```

### 1.1 Standard ELO

`model/features/elo.py`:

```python
def expected_score(rating_a, rating_b):
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400.0))

def update_standard_elo(winner_rating, loser_rating, k=32.0):
    exp = expected_score(winner_rating, loser_rating)
    return (winner_rating + k * (1.0 - exp),
            loser_rating  + k * (0.0 - (1.0 - exp)))
```

### 1.2 Modified ELO

The "modified" variant uses an **opponent-aware K**: each fighter's K
is computed from the *other's* rating, interpolated linearly between
the weak (1400) and elite (1600) thresholds. Beating an elite opponent
swings your rating more; the elite opponent loses less from being upset.

```python
def modified_k(opponent_rating, cfg=ELO_CONFIG):
    if opponent_rating >= cfg["elite_threshold"]:
        return cfg["base_k"] * cfg["elite_multiplier"]
    if opponent_rating <= cfg["weak_threshold"]:
        return cfg["base_k"] * cfg["weak_multiplier"]
    t = (opponent_rating - cfg["weak_threshold"]) / (
        cfg["elite_threshold"] - cfg["weak_threshold"])
    return cfg["base_k"] * (
        cfg["weak_multiplier"] + t * (cfg["elite_multiplier"] - cfg["weak_multiplier"]))

def update_modified_elo(winner, loser, cfg=ELO_CONFIG):
    k_w = modified_k(loser, cfg)    # winner's K depends on loser's rating
    k_l = modified_k(winner, cfg)   # loser's K depends on winner's rating
    exp = expected_score(winner, loser)
    return winner + k_w * (1.0 - exp), loser + k_l * (0.0 - (1.0 - exp))
```

### 1.3 What does NOT affect the update

- Draws — filtered out (`WHERE winner_id IS NOT NULL`)
- Title fights — flag ignored
- Method (KO/Sub/Dec) — ignored
- Round / time — ignored

Only the winner identity matters. If you want method/round factors,
that's net-new modeling work.

### 1.4 Pipeline write contract

Two rows per fight (one per fighter):

```sql
INSERT INTO elo_ratings
    (fighter_id, fight_id,
     elo_standard_pre, elo_standard,
     elo_modified_pre, elo_modified,
     rating_date)
```

The "pre" columns are taken from the in-memory state **before** the
update; the post columns are the result of the update. Don't omit
"pre" — it's load-bearing for backfills.

---

## 2. XGBoost training (`model/training/train.py`)

```python
# v1: max_depth=4, learning_rate=0.05
# v2: max_depth=6, learning_rate=0.02
model = xgb.XGBClassifier(
    n_estimators=300,
    max_depth=max_depth,
    learning_rate=learning_rate,
    subsample=0.8,
    colsample_bytree=0.8,
    eval_metric="logloss",
    random_state=42,
)
```

### 2.1 CV + final fit

`TimeSeriesSplit(n_splits=5)` for cross-validation diagnostics
(log-loss, accuracy per fold), then **final model trained on the
full dataset**:

```python
tscv = TimeSeriesSplit(n_splits=5)
for fold, (tr_idx, te_idx) in enumerate(tscv.split(X)):
    fold_model = clone_with_same_params(...)
    fold_model.fit(X.iloc[tr_idx], y.iloc[tr_idx])
    # log fold metrics

# Final
final_model = xgb.XGBClassifier(... same params ...)
final_model.fit(X, y)
final_model.save_model(f"model/artifacts/xgb_{version}.json")
```

### 2.2 Label and dataset mirroring

```python
df["label"] = (df["winner_id"] == df["fighter_a_id"]).astype(int)
```

Then mirror to balance bias: swap fighter A/B, flip sign of all
`diff_*` features and ELO pre values, re-label, concatenate. This
ensures the model can't cheat by always predicting fighter A.

### 2.3 v1 vs v2 features

```python
FEATURES_V1 = [
    "elo_std_pre_a", "elo_mod_pre_a", "elo_std_pre_b", "elo_mod_pre_b",
    "elo_diff_std", "elo_diff_mod",
    "is_title_fight",
]

FEATURES_V2 = FEATURES_V1 + [
    "a_str_acc", "a_str_vol", "a_td_acc", "a_grap_agg", "a_str_def",
    "b_str_acc", "b_str_vol", "b_td_acc", "b_grap_agg", "b_str_def",
    "diff_str_acc", "diff_str_vol", "diff_td_acc", "diff_grap_agg", "diff_str_def",
]
```

---

## 3. ESPN integration

### 3.1 URL templates

```python
SCHEDULE_URL        = "https://www.espn.com/mma/schedule/_/year/{year}/league/ufc"
FIGHTER_PROFILE_URL = "https://www.espn.com/mma/fighter/_/id/{espn_id}"
FIGHTER_STATS_URL   = "https://www.espn.com/mma/fighter/stats/_/id/{espn_id}"
# Event URL: grab the absolute href from the schedule's <a> link, e.g.
# https://www.espn.com/mma/fightcenter/_/id/{event_id}/league/ufc
```

### 3.2 Extracting the gamepackage JSON

ESPN's MMA pages embed a `__espnfitt__` JSON blob inside a `<script>`:

```python
import re, json
m = re.search(r"window\['__espnfitt__'\]\s*=\s*(\{.*?\});", html, re.DOTALL)
data = json.loads(m.group(1))
```

### 3.3 JSON path to the fight list

```
data
└── page
    └── content
        └── gamepackage
            └── cardSegs[*]            # Main Card, Prelims, Early Prelims
                └── mtchs[*]           # individual fights, in card order
```

### 3.4 Per-match keys we care about

```python
m["id"]                          # espn_fight_id (string)
m["nte"]                         # note, contains "Title Fight" or weight class
m["status"]["state"]             # "post" once the fight has concluded
m["status"]["dspClk"]            # "5:00" — display clock at end
m["status"]["rd"]                # "R3" — round
m["dec"]["shrtDspNm"]            # "U Dec", "KO/TKO", "Sub"

# Per-corner (awy = away, hme = home):
corner = m["awy"]                # or m["hme"]
ath    = corner.get("ath", {})
espn_id = (
    extract_id(ath.get("lnk"))    # primary: link contains /id/<N>
    or extract_id(corner.get("lnk"))
    or str(ath.get("id"))         # fallback: raw numeric id
)
won = corner.get("isWin") or ath.get("isWin")   # authoritative (LESSONS §F1)
```

### 3.5 Card order

```python
card_order = seg_index * 100 + match_index
```

Preserves "Main Card → Prelims → Early Prelims" segment ordering plus
the within-segment display order (main event first).

---

## 4. v2 feature formulas

Per fighter, computed from `fighter_stats` history:

```python
str_acc  = sig_strikes_landed     / sig_strikes_attempted   # 0.0 if denom is 0
str_vol  = sig_strikes_landed     / hist_fights
td_acc   = takedowns_landed       / takedowns_attempted     # 0.0 if denom is 0
grap_agg = (advances + submissions) / hist_fights
str_def  = opp_sig_strikes_landed / hist_fights   # higher means worse defense
```

### 4.1 `str_def` (opponent strikes landed on me)

```sql
SELECT SUM(opp_fs.sig_strikes_landed)
FROM fighter_stats opp_fs
JOIN fights past_f ON opp_fs.fight_id = past_f.fight_id
WHERE opp_fs.fighter_id != :me
  AND (past_f.fighter_a_id = :me OR past_f.fighter_b_id = :me)
  AND past_f.fight_date < :this_fight_date     -- TRAINING ONLY
```

### 4.2 Point-in-time vs lifetime: a real gotcha

- **Training** (`build_features_v2.py`) restricts with `past_f.fight_date <
  f.fight_date` — only history *before* the fight being predicted.
- **Inference** (`load_v2_stats` in `predict_upcoming.py`) sums **all
  history**, no date guard.

This is fine for upcoming fights (there's no future to leak). For
backfilling past fights (`backfill_predictions.py`), the lack of a
date guard is a known potential leak — but in practice it's mitigated
because we run with `--skip-stats` so the May-16 fight stats aren't
in the table at backfill time. **Rewrite recommendation:** add the
date guard in `load_v2_stats` too, taking the predicted fight's
`fight_date` as an argument.

### 4.3 Diff features

For each base feature `x`, the model gets:
```python
diff_x = a_x - b_x
```

Diffs cancel out absolute-level bias and give the tree splitter a
direct "is A or B better at X" signal.

---

## 5. Frontend static-mode pattern

`frontend/src/lib/api.js`:

```javascript
const BASE_URL  = import.meta.env.VITE_API_URL || "http://localhost:8000";
const IS_STATIC = import.meta.env.PROD;   // set by `vite build`

async function staticJson(filename) {
  const res = await fetch(`${import.meta.env.BASE_URL}data/${filename}`);
  if (!res.ok) throw new Error(`Static data not found: ${filename}`);
  return res.json();
}

export const api = {
  getPredictions: (modelVersion = null) => {
    if (IS_STATIC) {
      return staticJson("predictions.json").then((rows) =>
        modelVersion ? rows.filter((r) => r.model_version === modelVersion) : rows);
    }
    return get(`/predictions${modelVersion ? `?model_version=${modelVersion}` : ""}`);
  },

  // Write methods throw on the static build:
  createBet: (payload) => {
    if (IS_STATIC) throw new Error("Bets are read-only on the deployed site.");
    return post("/bets", payload);
  },
};
```

### 5.1 Vite config

```javascript
// frontend/vite.config.js
export default defineConfig({
  plugins: [react()],
  base: "/ufc-prediction/",   // GH Pages subpath
});
```

### 5.2 SPA fallback on GitHub Pages

Pages serves files, not routes. Without this, a hard refresh on
`/ufc-prediction/results` would 404 with the GitHub error page. We
copy `index.html` to `404.html` so any unknown path serves the SPA
shell (HTTP 404 but correct HTML); React Router takes over client-side.

```yaml
# .github/workflows/pages.yml (build job, working-directory: frontend)
- run: npm ci
- run: npm run build
- run: cp dist/index.html dist/404.html
- uses: actions/configure-pages@v5
- uses: actions/upload-pages-artifact@v3
  with: { path: frontend/dist }
```

---

## 6. SQL migrations (`data/sql/migrations/`)

Apply in order:

| File | Adds |
|---|---|
| `001_initial_schema.sql` | base tables: fighters, events, fights, fighter_stats (initial small set), elo_ratings, predictions, bets |
| `002_add_is_active_flag.sql` | `fighters.is_active BOOLEAN DEFAULT FALSE` |
| `003_add_card_order.sql` | `fights.card_order INT` |
| `004_add_is_cancelled.sql` | `fights.is_cancelled BOOLEAN DEFAULT FALSE` |
| `005_expand_fighter_stats.sql` | drops + recreates `fighter_stats` with ~37 ESPN stat columns, `UNIQUE(fight_id, fighter_id)` |
| `006_add_event_deployed_at.sql` | `events.deployed_at TIMESTAMPTZ` (the live-vs-backtest gate) |

In a clean rewrite, consolidate these into `001_initial_schema.sql`.
The migration order only matters if you're upgrading an existing DB.

---

## 7. Dependencies

### 7.1 `requirements.txt`

```
requests
beautifulsoup4
psycopg[binary]              # v3 — but predict_upcoming.py imports psycopg2 (legacy)
sqlalchemy
pandas
xgboost
scikit-learn
fastapi
uvicorn[standard]
python-dotenv
pydantic
python-frontmatter
```

⚠️ **Drift to fix on rewrite:** `predict_upcoming.py` does
`import psycopg2`. Either pin `psycopg2-binary` in requirements or
migrate the import to `psycopg` (v3). Currently works on dev
machines that happen to have both installed.

### 7.2 `frontend/package.json` (key versions)

```json
"react":              "^19.2.4",
"react-dom":          "^19.2.4",
"react-router-dom":   "^7.14.1",
"@tanstack/react-query": "^5.99.2",
"react-markdown":     "^10.1.0",
"recharts":           "^3.8.1",
"vite":               "^8.0.4",
"@vitejs/plugin-react": "^6.0.1",
"tailwindcss":        "^3.4.19"
```

---

## 8. `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:15
    container_name: ufc_postgres
    restart: always
    environment:
      POSTGRES_USER:     ufc_user
      POSTGRES_PASSWORD: ufc_password
      POSTGRES_DB:       ufc_predictor
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

`.env` (gitignored) carries:

```
DATABASE_URL=postgresql://ufc_user:ufc_password@localhost:5432/ufc_predictor
BET_API_KEY=<any-string-for-local-auth>
```

---

## 9. CI workflow (`.github/workflows/pages.yml`)

Job-level defaults run from `frontend/`; Node 20 with
`cache-dependency-path: frontend/package-lock.json`. Build steps:

```yaml
defaults:
  run:
    working-directory: frontend

steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-node@v4
    with:
      node-version: "20"
      cache: "npm"
      cache-dependency-path: frontend/package-lock.json
  - run: npm ci
  - run: npm run build
  - run: cp dist/index.html dist/404.html   # SPA fallback
  - uses: actions/configure-pages@v5
  - uses: actions/upload-pages-artifact@v3
    with:
      path: frontend/dist
  - uses: actions/deploy-pages@v4
```

Triggers on push to `main`.

---

## 10. Bootstrap order (for a true one-shot)

If you're starting from an empty directory and want a working system:

1. **Schema:** apply migrations against a Postgres 15 instance.
2. **Scraper smoke test:** `scrape_schedule(2026)` returns events;
   pick one and `scrape_event_fights` returns a list of `mtchs`.
3. **Bulk ingest:** `python -m data.ingest --all` (or a recent window
   while iterating).
4. **Active fighter flag:** mark fighters with at least one fight in
   the last 2-3 years `is_active = TRUE`.
5. **Stats:** `python -m data.post_event_pipeline --skip-stats=false`
   (or call `run_stats_scrape(active_only=True)` directly). Takes
   20-40 min.
6. **ELO bootstrap:** `python -m model.features.elo_pipeline --full`.
   Sanity check: top-10 by `elo_modified` should be plausible
   (Jones, Makhachev, GSP, etc.).
7. **Train both versions:** `python -m model.training.train v1` then
   `v2`. Saves `xgb_v1.json` / `xgb_v2.json`.
8. **First predict:** `python -m model.predict_upcoming` for v1 and v2.
   Confirms `events.deployed_at` gets set for future events.
9. **Export + commit:** `python -m data.loaders.export_static_api`,
   then commit `frontend/public/data/`.
10. **Deploy:** push `main`, watch the Pages workflow.

---

## 11. Behavioral oddities to preserve (or fix consciously)

- **`v2` inference uses lifetime stats** (no date guard). Fine for
  upcoming fights, leaky for backfills. See §4.2.
- **No method/round in ELO.** A "lucky" KO win moves rating the same
  as a dominant decision. Considered feature, not yet implemented.
- **`predict_upcoming` deletes-then-inserts** rather than upserting.
  Re-running invalidates any external references to the old
  `prediction_id`. Bets reference fight_id, not prediction_id, so
  this is currently safe — preserve that boundary.
- **All predictions are insert-time only.** No `features_snapshot`
  is ever written despite the column existing. If you want
  reproducibility, populate it on insert.
- **The blog table exists but is unused.** Reads come from
  `/blog/*.md` frontmatter. Drop the table in a rewrite.

---

## Cross-references

- Architecture, contracts, invariants → [REBUILD_SPEC.md](REBUILD_SPEC.md)
- Operational pitfalls → [LESSONS.md](LESSONS.md)
- Day-to-day refresh loop → [../UPDATING.md](../UPDATING.md)
- Component skill docs → [../skills/](../skills/)
