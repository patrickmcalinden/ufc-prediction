---
name: model-lab
description: Run modelling experiments on the UFC predictor — trying new features, data sources, Elo tweaks or hyperparameters, comparing against the current model, or promoting a new model version (v4, v5...). Use whenever the user wants to improve accuracy, test an idea ("does reach matter?", "add betting odds", "try LightGBM"), analyse model performance, or asks why a model is under/over-performing.
---

# Model lab

The goal is the most accurate model that is *honestly* accurate. This
project already shipped one model (v2) whose 60.9% cross-validation was
fake: its stats only existed for fighters still active today, so "has
stats" meant "kept winning". It ran 57.6% live. Every rule below exists
to stop that happening again.

## The loop

1. **Hypothesis first.** One sentence: what signal, and why it should
   predict fights. Check `model/EXPERIMENTS.md` — it may have been tried.
2. **Coverage check before modelling.** For any new column, answer: is it
   populated for *every* fight, or only for some fighters? If only some,
   *who decides which*? Scraping triggered by appearing on a recent card,
   profile pages, or anything else tied to a career lasting is
   survivorship. Quick test: among fights where only one fighter has the
   value, how often does that fighter win? Far from 50% = biased coverage.
3. **Write an experiment file** in `experiments/NNN_name.py` (numbered,
   never reuse). Template and API: `experiments/README.md`. Build A/B
   stats with `history.add_pair()` — it blanks both sides when either is
   missing. Only pass `symmetric=False` in a deliberate "raw" candidate
   to show the leak.
4. **Run it:** `python -m pipeline.experiment experiments/NNN_name.py`
   (from the repo root, with the venv; PYTHONPATH=. if needed). Takes
   ~1 min per candidate. Nothing touches the DB or model/artifacts.
5. **Read the verdict honestly** (see *Judging results*), then log it:
   re-run with `--log`, and add a line under **Notes** in
   `model/EXPERIMENTS.md` saying what was learned — including dead ends.
   A dropped idea is a result.
6. **Promote only through the registry** (see *Promoting a model*).

## Judging results

- **Log loss is the primary metric**, not accuracy. Accuracy moves in
  coarse steps and ignores confidence; a model can gain 0.5% accuracy by
  luck. Brier is the tie-breaker.
- The harness verdict is **better** only when the paired 95% CI on
  Δlogloss is entirely below 0 *and* the candidate wins at least 2/3 of
  test years. "Inconclusive" means *no evidence*, not "slightly better".
- **LEAK** is a hard stop. Fix the coverage (mask, backfill, or drop) —
  never tune around it.
- A gain that only shows up in one year, or only in 2025–26, is suspect.
  Recent years have fuller histories (DB starts in 2005), so everything
  looks better there.
- Suspiciously good (> ~66% accuracy, or a jump of > 2 points from one
  feature) almost always means leakage. Look for it before celebrating.
  Betting markets only get ~65–68%.
- The **live record outranks any backtest.** After promotion, wait 3–4
  cards before retiring the old model.

## Hard rules

- **Pre-fight only.** Every feature for fight F uses data strictly before
  F's date. The v3 frame is built in one chronological pass; keep new
  features the same way (cumulative sums shifted by one, etc.).
- **Never back-predict history.** A model must not lock picks for fights
  it was trained on. `predict_missing` already restricts backfill to
  events the model locked at the time — don't loosen that.
- **Never edit or delete locked predictions** to improve a record.
- **Same code for training and prediction.** New features go through
  `build_v3_frame` (or a function it calls), not a separate prediction path.
- **Don't touch v1/v2's feature code** — their live records must stay
  attributable to the code that produced them.
- Models are trained by the weekly job, not by hand, once registered.

## Data: what's trustworthy

| Source | Coverage | Safe? |
|---|---|---|
| `fights` (dates, winner, method, round, title flag) | Every UFC + DWCS bout from ESPN's schedule, 2005→ | Yes |
| `fighters.date_of_birth` | ~96% | Yes, masked |
| `fighters.reach_cm`, `height_cm` | ~51–57%, biased to active fighters | Leaks raw; no gain masked (001) |
| `fighters.stance` | ~97% | Untested |
| `fighter_stats` (strikes, takedowns, control...) | Only fighters on recent cards (~91% of 2026-active, ~0–5% of pre-2021-retired) | **Leaks** — unusable until backfilled for all fighters |
| `elo_ratings` | Derived from `fights` | Yes (legacy K=32 Elo; v3 recomputes its own) |
| `fights.weight_class` | Mostly populated | Untested |

## Code map

- `pipeline/history.py` — v3 feature frame (`build_v3_frame`), tuned Elo
  (`ELO3_CONFIG`), `add_pair`, `mirror`.
- `pipeline/evaluate.py` — `walk_forward`, `leak_check`.
- `pipeline/experiment.py` — the harness.
- `pipeline/models.py` — registry (`feature_set`, `retired`, `known_leak`).
- `pipeline/train.py` — per-model leak check + backtest + final fit;
  results land in `model/artifacts/xgb_<name>.meta.json`.
- `pipeline/predict.py` — locking + backfill.

## Promoting a model

1. The experiment must be **better** (not inconclusive) against the
   current best registered model.
2. Move its features into `pipeline/history.py` (so training and
   prediction share them) and add a registry entry `vN` with
   `feature_set="v3"` and the tuned params. Never reuse a model name.
3. Train it once by hand —
   `python -c "from pipeline.train import train_one; train_one('vN')"` —
   and confirm the leak check passes and the backtest matches the
   experiment.
4. Dry-run picks for the next card without writing to the DB (build the
   frame, `load("vN")`, `predict_proba`) and sanity-check them.
5. Update `site/src/app/methodology/page.mdx` and `UPDATING.md`.
6. Branch + PR + merge (the repo's standard flow). Work in a git worktree
   if a scheduled run (Fri/Sun 21:00) might fire — the weekly job needs
   the main checkout clean and on `main`.
7. Run side by side for 3–4 cards, then set `retired=True` on the model
   it replaces. The retired model's record stays on the dashboard.

## Ideas backlog

Roughly by expected value. Move items to `model/EXPERIMENTS.md` when tried.

- **Backfill `fighter_stats` for every fighter** (~2,900 profiles, ~85 min
  scrape). Removes the survivorship bias; then re-test striking /
  grappling features properly — per minute, not per fight.
- **Betting odds** as a feature or benchmark. Biggest known signal, but
  needs a new data source; decide with the user first.
- **Corner / billing order.** Fighter A wins 57%. Only usable if ESPN's
  A/B order is the same before and after the fight — verify first.
- **Opponent-adjusted history** — win rate weighted by opponent Elo;
  strength of schedule.
- **Method-specific form** — KO/TKO power vs chin (finishes for / against
  by type), submission threat vs grappling defence.
- **Weight-class context** — moving up/down, first fight in a division,
  division-specific Elo.
- **Elo refinements** — margin (round of finish), decision type
  (split vs unanimous), Glicko-style uncertainty for low-experience
  fighters.
- **Stance matchup** (orthodox vs southpaw) — stance is ~97% populated.
- **Calibration** — v3 under-rates fighter A by ~4pts in every bin;
  isotonic or Platt scaling on the walk-forward predictions.
- **Model family** — LightGBM / logistic regression / small ensemble
  once features stop improving.
