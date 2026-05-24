"""
Post-Event Pipeline — Single CLI entry point for all post-fight reconciliation.

Usage:
    python -m data.post_event_pipeline                # full pipeline
    python -m data.post_event_pipeline --dry-run       # preview without writing
    python -m data.post_event_pipeline --skip-stats    # skip the slow stats scrape
    python -m data.post_event_pipeline --year 2024     # process a specific year
    python -m data.post_event_pipeline --active-stats  # only scrape stats for active fighters

Steps executed in order:
    1. Ingest — scrape ESPN schedule + fights + fighter profiles for the year
    2. Stats  — scrape per-fight stats for fighters in newly-completed fights
    3. Grade  — grade all ungraded predictions
    4. ELO    — incrementally update ELO ratings for new fights
"""

import argparse
import logging
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.ingest import run_ingestion
from data.grade_predictions import grade_predictions
from data.scrapers.espn_scraper import ESPNScraper
from data.loaders.postgres_loader import PostgresLoader
from model.features.elo_pipeline import run_elo_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def run_stats_scrape(active_only=True, dry_run=False):
    """
    Scrape per-fight stats for fighters and upsert into fighter_stats.
    If active_only=True, only scrapes fighters with is_active=True (~700).
    """
    loader = PostgresLoader()
    scraper = ESPNScraper()

    with loader.get_connection() as conn:
        with conn.cursor() as cur:
            if active_only:
                cur.execute("SELECT espn_id, name FROM fighters WHERE is_active = TRUE ORDER BY fighter_id")
            else:
                cur.execute("SELECT espn_id, name FROM fighters ORDER BY fighter_id")
            fighters = cur.fetchall()

    total = len(fighters)
    logging.info(f"[STATS] Will scrape stats for {total} fighters (active_only={active_only})")

    scraped = 0
    errors = 0
    for i, f in enumerate(fighters, 1):
        espn_id = f['espn_id']
        name = f['name']
        try:
            logging.info(f"[STATS] ({i}/{total}) Scraping stats for {name} ({espn_id})")
            stats_rows = scraper.scrape_fighter_stats(espn_id)
            if stats_rows:
                inserted = loader.upsert_fighter_stats(stats_rows, dry_run=dry_run)
                scraped += 1
                if not dry_run:
                    logging.info(f"  → Upserted {inserted} stat rows for {name}")
            else:
                logging.info(f"  → No stats found for {name}")
        except Exception as e:
            errors += 1
            logging.error(f"  → Error scraping stats for {name}: {e}")

    logging.info(f"[STATS] Complete — {scraped} fighters scraped, {errors} errors")
    return {"scraped": scraped, "errors": errors}


def run_pipeline(year=None, dry_run=False, skip_stats=False, active_stats=True):
    """
    Execute the full post-event reconciliation pipeline.
    """
    if not year:
        year = datetime.now().year

    logging.info("=" * 70)
    logging.info("  UFC POST-EVENT PIPELINE")
    logging.info(f"  Year: {year}  |  Dry Run: {dry_run}  |  Skip Stats: {skip_stats}")
    logging.info("=" * 70)

    # ── Step 1: Ingest ─────────────────────────────────────────────
    logging.info("\n" + "─" * 50)
    logging.info("STEP 1/4: INGEST — Scraping events, fights, fighter profiles")
    logging.info("─" * 50)
    try:
        run_ingestion(year_to_scrape=year, upcoming_only=True, dry_run=dry_run)
        logging.info("[INGEST] ✓ Complete")
    except Exception as e:
        logging.error(f"[INGEST] ✗ Failed: {e}")
        return

    # ── Step 2: Stats ──────────────────────────────────────────────
    if not skip_stats:
        logging.info("\n" + "─" * 50)
        logging.info("STEP 2/4: STATS — Scraping per-fight stats from ESPN")
        logging.info("─" * 50)
        try:
            stats_summary = run_stats_scrape(active_only=active_stats, dry_run=dry_run)
            logging.info(f"[STATS] ✓ Complete — {stats_summary}")
        except Exception as e:
            logging.error(f"[STATS] ✗ Failed: {e}")
    else:
        logging.info("\n[STATS] Skipped (--skip-stats flag)")

    # ── Step 3: Grade ──────────────────────────────────────────────
    logging.info("\n" + "─" * 50)
    logging.info("STEP 3/4: GRADE — Grading ungraded predictions")
    logging.info("─" * 50)
    try:
        grade_summary = grade_predictions(dry_run=dry_run)
        logging.info(f"[GRADE] ✓ Complete — {grade_summary}")
    except Exception as e:
        logging.error(f"[GRADE] ✗ Failed: {e}")

    # ── Step 4: ELO ────────────────────────────────────────────────
    logging.info("\n" + "─" * 50)
    logging.info("STEP 4/4: ELO — Incrementally updating ELO ratings")
    logging.info("─" * 50)
    try:
        if not dry_run:
            run_elo_pipeline(incremental=True)
            logging.info("[ELO] ✓ Complete")
        else:
            logging.info("[ELO] Skipped in dry-run mode")
    except Exception as e:
        logging.error(f"[ELO] ✗ Failed: {e}")

    logging.info("\n" + "=" * 70)
    logging.info("  PIPELINE COMPLETE")
    logging.info("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UFC Post-Event Reconciliation Pipeline")
    parser.add_argument("--year", type=int, help="Year to process (default: current year)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    parser.add_argument("--skip-stats", action="store_true", help="Skip the stats scraping step (saves time)")
    parser.add_argument("--all-fighters", action="store_true", help="Scrape stats for ALL fighters, not just active")
    args = parser.parse_args()

    run_pipeline(
        year=args.year,
        dry_run=args.dry_run,
        skip_stats=args.skip_stats,
        active_stats=not args.all_fighters,
    )
