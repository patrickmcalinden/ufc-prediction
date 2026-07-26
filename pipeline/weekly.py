"""One-shot weekly UFC pipeline workflow - safe to run unattended.

    .venv\\Scripts\\python.exe -m pipeline.weekly            # grade + lock
    .venv\\Scripts\\python.exe -m pipeline.weekly --no-lock  # Sunday: grade only
    .venv\\Scripts\\python.exe -m pipeline.weekly --no-grade # Friday: lock only

Does the whole cycle end-to-end so a scheduler only has to fire a single
command:

  1. Reconcile every UFC event in [today-N, today] (N = --lookback-days).
     Works around the single-event filter in ingest.ingest_events(mode=
     "reconcile") which silently skips older events when a newer one is in
     the window.
  2. Scrape per-fight stats scoped to the reconciled events' fighters.
  3. Full Elo rebuild. Works around the fight_id watermark in
     elo_update._incremental which skips events whose fights all got
     freshly-assigned small fight_ids.
  4. Backfill late-add predictions, grade everything ungraded.
  5. Pick the next undeployed upcoming event and lock predictions for it.
  6. Export site JSON.
  7. Create a branch, commit, push, open a PR, merge it.

Events that were never locked stay untouched by 4 and 5: `deployed_at IS
NULL` gates every export/grade/backfill query, so a card the pipeline
missed gets its results ingested (Elo stays correct) but never gets
retroactive picks.

Flags:
  --lookback-days N  how far back to reconcile completed events (default 8)
  --no-git           skip the commit/PR/merge step (leave changes in the worktree)
  --no-grade         skip the grading half
  --no-lock          skip the lock half
  --no-merge         create the PR but don't auto-merge it
  --allow-dirty      skip the clean-worktree/on-main preflight check
  --log-dir PATH     also write a timestamped log file here (default logs/)
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from pipeline import elo_update, export, grade, ingest, predict, train
from pipeline.db import connect
from pipeline.models import all_names
from pipeline.scrape import ESPNScraper

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent


class PreflightError(RuntimeError):
    """Raised when the environment isn't safe to run an unattended cycle in."""


def _setup_logging(log_dir: Path | None) -> Path | None:
    """Configure root logging for an unattended run.

    Two things this has to survive that the interactive path didn't:

    - `pipeline.scrape` calls `logging.basicConfig` at import time, so the
      root logger already has a handler by the time we get here. Without
      force=True our format is silently ignored.
    - Fighter names contain non-cp1252 characters ("Procházka"). On Windows
      the default console/file encoding raises UnicodeEncodeError mid-run,
      which would kill a scheduled job. UTF-8 for the file, replace-on-error
      for the console.
    """
    handlers: list[logging.Handler] = []

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # pragma: no cover - non-standard stream
        pass
    handlers.append(logging.StreamHandler(sys.stdout))

    log_path: Path | None = None
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"weekly-{datetime.now():%Y-%m-%d_%H%M%S}.log"
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
        force=True,
    )
    return log_path


def _heading(label: str) -> None:
    log.info("-" * 60)
    log.info(label)
    log.info("-" * 60)


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess, logging its output. Unlike a bare subprocess.run this
    surfaces stderr — a silent `gh pr merge` failure is exactly the kind of
    thing that makes an unattended run look successful when it wasn't."""
    log.info("$ %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=REPO_ROOT, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    for stream, level in ((proc.stdout, logging.DEBUG), (proc.stderr, logging.INFO)):
        for line in (stream or "").splitlines():
            if line.strip():
                log.log(level, "  | %s", line)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, cmd, proc.stdout, proc.stderr)
    return proc


def wait_for_db(attempts: int = 10, delay: float = 6.0) -> None:
    """Block until Postgres answers. The DB is a Docker container, so a run
    triggered shortly after boot can beat Docker Desktop to the punch."""
    for attempt in range(1, attempts + 1):
        try:
            with connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT 1")
            log.info("Database is up.")
            return
        except Exception as e:
            if attempt == attempts:
                raise PreflightError(f"Database unreachable after {attempts} attempts: {e}") from e
            log.warning("DB not ready (attempt %d/%d): %s — retrying in %.0fs", attempt, attempts, e, delay)
            time.sleep(delay)


def preflight(need_git: bool, allow_dirty: bool) -> None:
    """Fail fast and loudly rather than half-finish a cycle."""
    _heading("PREFLIGHT")
    wait_for_db()

    if not need_git:
        return

    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    log.info("On branch: %s", branch)
    if branch != "main" and not allow_dirty:
        raise PreflightError(f"Expected to start from main, found '{branch}'. Use --allow-dirty to override.")

    dirty = _run(["git", "status", "--porcelain", "--untracked-files=no"]).stdout.strip()
    if dirty and not allow_dirty:
        raise PreflightError(f"Working tree has uncommitted changes:\n{dirty}\nUse --allow-dirty to override.")

    if _run(["gh", "auth", "status"], check=False).returncode != 0:
        raise PreflightError("`gh` is not authenticated — the PR/merge step would fail.")


def grade_recent_events(lookback_days: int) -> list[int]:
    """Reconcile every event in the lookback window, scrape stats, rebuild Elo,
    backfill, grade. Returns the list of reconciled event_ids."""
    _heading(f"1/4  RECONCILE events from the last {lookback_days} day(s)")
    scraper = ESPNScraper()
    today = datetime.now().date()
    cutoff = today - timedelta(days=lookback_days)

    # A lookback window can straddle a year boundary, so pull both schedules.
    schedule = scraper.scrape_schedule(today.year)
    if cutoff.year != today.year:
        schedule += scraper.scrape_schedule(cutoff.year)

    past_events = [e for e in schedule if cutoff <= e["event_date"] <= today]
    past_events.sort(key=lambda e: e["event_date"])

    if not past_events:
        log.info("No events in the last %d days.", lookback_days)
        return []

    log.info("Reconciling %d event(s)", len(past_events))
    reconciled_ids: list[int] = []
    with connect() as conn, conn.cursor() as cur:
        for event in past_events:
            log.info("Event: %s (%s)", event["name"], event["event_date"])
            event_id = ingest.upsert_event(cur, event)
            fights = scraper.scrape_event_fights(event["url"], event["espn_event_id"])
            log.info("  -> %d fights", len(fights))
            for f in fights:
                for espn_id in (f.get("fighter_a_espn_id"), f.get("fighter_b_espn_id")):
                    if espn_id:
                        profile = scraper.scrape_fighter_profile(espn_id=espn_id)
                        if profile:
                            ingest.upsert_fighter(cur, profile)
                ingest.upsert_fight(cur, f)
            active = [f["espn_fight_id"] for f in fights if f.get("espn_fight_id")]
            ingest.mark_missing_fights_cancelled(cur, event["espn_event_id"], active)
            conn.commit()
            if event_id:
                reconciled_ids.append(event_id)

    _heading("2/4  STATS scrape (scoped)")
    fighter_ids = ingest.fighter_ids_for_events(reconciled_ids)
    log.info("stats: %s", ingest.ingest_stats(fighter_ids=fighter_ids))

    _heading("3/4  FULL Elo rebuild")
    log.info("elo: %s", elo_update.update_elo(full_rebuild=True))

    _heading("4/4  BACKFILL + GRADE")
    log.info("backfill: %s", predict.predict_missing())
    log.info("grade: %s", grade.grade_predictions())

    return reconciled_ids


def lock_next_event() -> dict | None:
    """Lock predictions for the next undeployed upcoming event. Returns the
    event row, or None if there's nothing to lock."""
    _heading("1/3  INGEST upcoming events")
    ingest.ingest_events(mode="recent")

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT event_id, name, event_date
              FROM events
             WHERE event_date >= CURRENT_DATE
               AND deployed_at IS NULL
             ORDER BY event_date
             LIMIT 1
            """
        )
        row = cur.fetchone()

    if not row:
        log.info("No undeployed upcoming event to lock.")
        return None

    log.info("Next event: %s (%s)", row["name"], row["event_date"])
    _heading("2/3  TRAIN models")
    train.train_all(only=all_names())

    _heading("3/3  PREDICT")
    log.info("predict: %s", predict.predict_event(event_id=row["event_id"], models=all_names()))
    return row


def _unique_branch(base: str) -> str:
    """`weekly/2026-08-01`, or `weekly/2026-08-01-2` if that already exists.
    Never reuse a branch name — `checkout -B` would silently discard whatever
    a previous partial run left there."""
    existing = _run(["git", "branch", "--list", f"{base}*"]).stdout
    if base not in existing:
        return base
    for n in range(2, 100):
        candidate = f"{base}-{n}"
        if candidate not in existing:
            return candidate
    raise PreflightError(f"Too many existing branches named {base}*")


def git_commit_and_pr(title: str, body: str, merge: bool = True) -> None:
    diff = _run(["git", "status", "--porcelain", "site/public/data/"]).stdout.strip()
    if not diff:
        log.info("No site/public/data changes — nothing to commit.")
        return

    branch = _unique_branch(f"weekly/{datetime.now():%Y-%m-%d}")

    _heading(f"GIT: branch {branch} + commit + PR (merge={merge})")
    _run(["git", "checkout", "-b", branch])
    _run(["git", "add", "site/public/data/"])
    _run(["git", "commit", "-m", title])
    _run(["git", "push", "-u", "origin", branch])
    _run(["gh", "pr", "create", "--title", title, "--body", body])
    if merge:
        _run(["gh", "pr", "merge", "--merge", "--delete-branch"])
        _run(["git", "checkout", "main"])
        _run(["git", "pull"])
    else:
        log.info("PR left open (--no-merge). Still on branch %s.", branch)


def _describe(graded_ids: list[int] | None, locked: dict | None) -> tuple[str, str]:
    """Commit title + PR body reflecting what the run actually did."""
    datestamp = f"{datetime.now():%Y-%m-%d}"
    parts = []
    if graded_ids is not None:
        parts.append(f"graded {len(graded_ids)} event(s)")
    if locked is not None:
        parts.append(f"locked {locked['name']}")
    suffix = f" - {'; '.join(parts)}" if parts else ""

    title = f"Weekly update {datestamp}{suffix}"
    lines = ["Automated run via `python -m pipeline.weekly`.", ""]
    if graded_ids is not None:
        lines.append(
            f"- Reconciled {len(graded_ids)} completed event(s), scraped stats, "
            "full Elo rebuild, backfill + grade."
        )
    if locked is not None:
        lines.append(f"- Locked predictions for {locked['name']} ({locked['event_date']}).")
    elif graded_ids is not None:
        lines.append("- No undeployed upcoming event to lock.")
    return title, "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lookback-days", type=int, default=8, help="how far back to reconcile completed events (default 8)")
    parser.add_argument("--no-git", action="store_true", help="skip commit/PR/merge")
    parser.add_argument("--no-grade", action="store_true", help="skip the grading half")
    parser.add_argument("--no-lock", action="store_true", help="skip the lock half")
    parser.add_argument("--no-merge", action="store_true", help="create the PR but don't auto-merge")
    parser.add_argument("--allow-dirty", action="store_true", help="skip the clean-worktree/on-main preflight check")
    parser.add_argument("--log-dir", default="logs", help="directory for the run log, or '' to disable (default logs/)")
    args = parser.parse_args()

    log_dir = (REPO_ROOT / args.log_dir) if args.log_dir else None
    log_path = _setup_logging(log_dir)
    started = time.monotonic()
    if log_path:
        log.info("Logging to %s", log_path)

    try:
        preflight(need_git=not args.no_git, allow_dirty=args.allow_dirty)

        graded_ids = None if args.no_grade else grade_recent_events(args.lookback_days)
        locked = None if args.no_lock else lock_next_event()

        _heading("EXPORT site JSON")
        export.export_all()

        if not args.no_git:
            title, body = _describe(graded_ids, locked)
            git_commit_and_pr(title, body, merge=not args.no_merge)
    except PreflightError as e:
        log.error("PREFLIGHT FAILED: %s", e)
        return 2
    except Exception:
        log.exception("WEEKLY RUN FAILED after %.1f min", (time.monotonic() - started) / 60)
        return 1

    log.info("Done in %.1f min.", (time.monotonic() - started) / 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
