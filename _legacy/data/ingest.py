import logging
from datetime import datetime, timedelta
import sys
import os

# Add parent directory of data/ to path for absolute imports inside data folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.scrapers.espn_scraper import ESPNScraper
from data.loaders.postgres_loader import PostgresLoader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_ingestion(year_to_scrape=None, upcoming_only=False, reconcile=False, dry_run=False):
    scraper = ESPNScraper()
    loader = PostgresLoader()
    
    if not year_to_scrape:
        year_to_scrape = datetime.now().year
        
    logging.info(f"Starting ingestion process for year: {year_to_scrape}. Dry run: {dry_run}")
    
    events = scraper.scrape_schedule(year_to_scrape)

    if reconcile:
        # --reconcile: target the most recent past event (last 7 days) to capture results
        # This is the key mode for post-fight result ingestion
        today = datetime.now().date()
        lookback = today - timedelta(days=7)
        recent_events = [e for e in events if lookback <= e['event_date'] <= today]
        recent_events.sort(key=lambda x: x['event_date'], reverse=True)
        events = recent_events[:1]
        if events:
            logging.info(f"Reconcile mode: targeting most recent event '{events[0]['name']}' ({events[0]['event_date']})")
        else:
            logging.info("Reconcile mode: no events found in the last 7 days.")
            return
    elif upcoming_only:
        # --upcoming: include events from the last 3 days (may still need results)
        # PLUS the next future event. This prevents the midnight cutoff bug where
        # an event at 11 PM is considered "yesterday" by 12:01 AM.
        today = datetime.now().date()
        lookback = today - timedelta(days=3)
        relevant_events = [e for e in events if e['event_date'] >= lookback]
        relevant_events.sort(key=lambda x: x['event_date'])
        # Take: any events in the lookback window + the next future event
        events = relevant_events[:3]  # At most 3 events (handles rare double-header weeks)
        logging.info(f"Filtered to recent + upcoming events for {year_to_scrape} ({len(events)} event(s))")
    else:
        logging.info(f"Found {len(events)} events for {year_to_scrape}")
    
    # We will process in chronological order
    for event in events:
        logging.info(f"--- Processing event: {event['name']} ---")
        loader.upsert_event(event, dry_run=dry_run)
        
        fights = scraper.scrape_event_fights(event['url'], event['espn_event_id'])
        logging.info(f"Extracted {len(fights)} fights from event")
        
        for fight in fights:
            # First, process both fighters to ensure foreign key integrity
            for f_espn_id in [fight.get('fighter_a_espn_id'), fight.get('fighter_b_espn_id')]:
                if f_espn_id:
                     fighter_data = scraper.scrape_fighter_profile(espn_id=f_espn_id)
                     if fighter_data:
                         loader.upsert_fighter(fighter_data, dry_run=dry_run)
                         
            # Then process the fight itself
            loader.upsert_fight(fight, dry_run=dry_run)
            
        # Reconcile cancelled fights
        active_espn_fight_ids = [f['espn_fight_id'] for f in fights if f.get('espn_fight_id')]
        loader.mark_missing_fights_as_cancelled(event['espn_event_id'], active_espn_fight_ids, dry_run=dry_run)
            
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="UFC Data Ingestion Pipeline")
    parser.add_argument("--all", action="store_true", help="Scrape all historical years back to 2005")
    parser.add_argument("--year", type=int, help="Scrape a specific year")
    parser.add_argument("--upcoming", action="store_true", help="Scrape recent (last 3 days) + next upcoming events")
    parser.add_argument("--reconcile", action="store_true", help="Re-scrape the most recent event to capture fight results")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to DB")
    args = parser.parse_args()
    
    if args.all:
        current_year = datetime.now().year
        # 2005 is generally a safe cutoff for when ESPN UFC data becomes highly reliable
        for y in range(2005, current_year + 1):
             run_ingestion(year_to_scrape=y, upcoming_only=args.upcoming, reconcile=args.reconcile, dry_run=args.dry_run)
    elif args.year:
        run_ingestion(year_to_scrape=args.year, upcoming_only=args.upcoming, reconcile=args.reconcile, dry_run=args.dry_run)
    else:
        # Default to current year
        run_ingestion(upcoming_only=args.upcoming, reconcile=args.reconcile, dry_run=args.dry_run)
