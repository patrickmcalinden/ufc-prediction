# Lessons Learned

Operational pain points hit while running and refactoring this project.
Each lesson is short by design — root cause + fix. Cross-reference
[REBUILD_SPEC.md](REBUILD_SPEC.md) for the design invariants these
lessons motivate.

---

## A. The "invisible event" problem

### A1. `events.deployed_at` is a manual gate

**What broke:** Allen vs. Costa (2026-05-16) ran and was scraped/graded
correctly, but never appeared on `/results` or `/models`. Cause:
`events.deployed_at` was `NULL`, and the grader, models leaderboard,
and exporter all filter on `deployed_at IS NOT NULL`.

**Root cause:** Nothing in the codebase set the column. The three
previously-visible events had been backfilled by a one-time `UPDATE`
on 2026-05-10. New events silently fell through.

**Fix (landed, PR #6):** `predict_upcoming.py` now sets
`deployed_at = NOW()` (if NULL) for any event whose date is
today-or-future at predict time. The deploy timestamp is now coupled
to the actual deployment moment.

**Watch for:** if you ever see a finished event missing from the live
surfaces, the first query to run is:

```sql
SELECT event_id, name, deployed_at FROM events ORDER BY event_date DESC LIMIT 5;
```

### A2. "Pipeline complete" does not mean "visible on the site"

`python -m data.post_event_pipeline` ends with `✓ PIPELINE COMPLETE`
even when downstream gates (`deployed_at`, `is_cancelled`) keep the
data hidden. The script reports steps it ran, not whether the data
is reachable from the frontend.

**Mitigation:** the rebuild spec proposes a final reconciliation step
in `post_event_pipeline` that asserts every settled fight on a deployed
event has predictions and a non-NULL `was_correct`. See REBUILD_SPEC §6.

---

## B. Mid-week card changes leave gaps

### B1. Cancelled fights that aren't re-scraped stay "active"

**What broke:** Three matchups in our DB (Filho-Rocha, Tuivasa-Sharaf,
Blachowicz-Guskov) sat ungraded forever because ESPN had replaced or
removed them after we'd scraped the announced card. The auto-cancel
logic (`mark_missing_fights_as_cancelled`) only runs when an event
gets re-scraped, and `--upcoming` only re-scrapes within 3 days.

**Root cause:** `data/ingest.py` filters to `today - 3 days <= event_date
<= today + future`. Older events with changed cards are never revisited.

**Fix applied for these three:** Manual `UPDATE fights SET is_cancelled
= TRUE WHERE fight_id IN (...)`.

**Long-term fix (open):** Widen the reconcile window or run
`mark_missing_fights_as_cancelled` against any event with predictions
whose `was_correct IS NULL`.

### B2. Card swaps create fights with winners but no predictions

**What broke:** Allen vs. Costa had 13 actual fights, but the
results page only showed 10. The other 3 (Bukauskas-Edwards,
Veretennikov-Williams, Gantt-Minev) were late additions after
`predict_upcoming` ran on 2026-05-02 — they had winners scraped
but no model output.

**Root cause:** `predict_upcoming` only runs on operator demand,
before the event. It doesn't know to re-run when the card changes.

**Fix (landed, PR #7):** Added `model/backfill_predictions.py` that
uses **pre-event** ELO from `elo_ratings.elo_standard_pre` to predict
specific late-added fights without leaking post-fight knowledge.

**Long-term fix (open):** `post_event_pipeline` should detect "settled
fight on a deployed event with no prediction" and invoke the backfill
automatically.

### B3. The pre-event ELO column is the load-bearing trick

`elo_ratings.elo_standard_pre` / `elo_modified_pre` store each fighter's
rating **going into** the fight. This makes legitimate backfills
possible — without it, any prediction generated after-the-fact would
use post-fight ELO and effectively cheat. Preserve this column in any
rewrite. See REBUILD_SPEC §4.

---

## C. Filter drift between live API and static export

### C1. The exporter and the API must filter identically

**What broke:** `data/loaders/export_static_api.py` did not filter on
`is_cancelled`, so cancelled-and-orphaned fights leaked into
`predictions.json` and `results.json` even though the live API hid them.
The deployed site showed phantom predictions for fights that never
happened.

**Root cause:** Two filter clauses in two languages (Python/psycopg2
SQL vs SQLAlchemy ORM) maintained separately. Adding a filter to one
without the other introduces drift.

**Fix (landed):** Sync — both now apply `is_cancelled = FALSE` to
predictions and results outputs.

**Repeat offender:** Git log shows multiple historical "Restore X.json"
commits. The exporter has lost data more than once.

**Long-term fix (open):** Either consolidate to a single filter helper,
or add a sanity test that asserts each exporter query returns the same
row IDs as the equivalent API endpoint for a known fixture.

### C2. The models endpoint still doesn't filter cancelled fights

Both `api/routers/predictions.py::list_models` and the corresponding
exporter step count predictions on cancelled fights in `total_predictions`.
This is a pre-existing inconsistency (the leaderboard treats
`was_correct = NULL` rows as "deployed but ungraded" rather than
"never happened"). Out of scope for now; documented for the rewrite.

---

## D. Re-scrape data preservation

### D1. ON CONFLICT must use COALESCE for result fields

**What broke (historical):** Commit `42d16f2` — "Fix upsert_fight:
don't NULL-overwrite winner when re-scraping". Re-running the
pipeline on an upcoming event would NULL out previously-recorded
winners because the live scrape correctly returned NULL for the
incomplete fight.

**Fix (already landed):** `data/loaders/postgres_loader.py::upsert_fight`
uses `winner_id = COALESCE(EXCLUDED.winner_id, fights.winner_id)` for
`winner_id`, `method`, `round`, `time`. Keep this pattern.

**Lesson:** Any column that can transition NULL → value but never
back to NULL must use COALESCE-on-NULL in its upsert. The cancellation
flag is the explicit reverse signal — never overload NULL to mean
"cancelled."

### D2. The auto-cancellation flag is the right way to "remove" a fight

`mark_missing_fights_as_cancelled` flips `is_cancelled = TRUE` for
rows whose `espn_fight_id` is no longer in the active scrape. Never
delete fight rows — predictions, bets, and ELO ratings reference them
and the FK cascade would corrupt downstream data. Cancellation
preserves history while letting filters hide the row.

---

## E. Tooling quirks

### E1. Windows console can't encode `✓`

`data/loaders/export_static_api.py` finishes with `print("  EXPORT
COMPLETE ✓")` which crashes Python on Windows cp1252 consoles. The
JSON files are already written by then — exit is non-zero anyway.

**Workaround:** Ignore the trailing crash. The data is fine.
**Real fix:** Replace `✓` with `OK` or set `PYTHONIOENCODING=utf-8`.

### E2. PowerShell `errorlevel` propagation lies

Running `.\scripts\update_data.bat` through the agent's PowerShell
wrapper sometimes returns exit 1 even when the script succeeded,
because stdout buffer truncation aborts the pipe mid-stream. The
`git add` step in the .bat does *not* run in this case — must be
done manually:

```sh
git add frontend/public/data blog
```

### E3. `tail -200` buffers entirely

Piping a long-running Python script through `tail -200` (Bash on
Windows) returns nothing until the entire pipeline ends — `tail`
doesn't pass through line-buffered, it accumulates. Don't do this
when monitoring. Use `tee` if you need both viewing and logging.

### E4. `gh pr merge` fails from a worktree

If `main` is checked out in the parent repo, `gh pr merge` errors
with "fatal: 'main' is already used by worktree at ...". The
**remote merge still succeeds** — verify with `gh pr view N --json
state`. The error is from `gh` trying to update local main.

### E5. Model artifacts are gitignored

`model/artifacts/xgb_v*.json` are in `.gitignore` (large binaries).
A fresh worktree has no copies. `predict_upcoming` and
`backfill_predictions` fail with `XGBoostError: Opening ... failed`
until you copy them from the parent repo:

```sh
cp ../../../model/artifacts/*.json model/artifacts/
```

---

## F. Verification habits

### F1. ESPN's fightcenter listing page WebFetch hallucinates winners

When auditing fight outcomes, do **not** trust a Claude WebFetch
summary of `espn.com/mma/fightcenter/_/id/.../league/ufc`. It
extracts the first-named fighter as the winner regardless of who
actually won.

**Authoritative sources, in order of trust:**
1. Per-fighter profile page (`espn.com/mma/fighter/_/id/<id>`) —
   states "Loss" or "Win" explicitly next to the most recent fight.
2. ESPN gamepackage JSON `awy.isWin` / `hme.isWin` flags
   (what our scraper actually reads).
3. In-fight stats — for a submission win, the winner has
   `subatt > 0` and the bulk of `ctrl` (control time).

**The cost of skipping verification:** ~20 min spent on a fictional
"systematic scraper bug" alarm in this session.

### F2. ELO sanity check after rebuilds

The top-10 ranked fighters by `elo_modified` should be roughly the
fighters you'd expect (Jones, Makhachev, Khabib, GSP, Volkanovski-tier).
If the top of the leaderboard looks weird after an ELO replay, the
ordering or watermark is off.

---

## G. Workflow

### G1. Default to PR-merge, not direct push

Even when the user says "push to main," the established pattern in
this repo is `branch → PR → squash-merge`. Direct push works but
leaves no review surface and complicates rollback. The agent's memory
captures this preference.

### G2. Hard-refresh after every deploy

The CDN serves fresh content but the browser caches the SPA shell.
After the Pages deploy turns green:

```
Ctrl+Shift+R
```

Otherwise you see stale data and think the deploy is broken.

### G3. `git diff --stat --cached` before commit

A typical post-event refresh touches `predictions.json`,
`results.json`, `models.json`, plus a handful of `fighters/*_fights.json`
(say 50-100 file mods). If you see thousands of files churning, you
probably regenerated against a different DB state — investigate
before committing.
