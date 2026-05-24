import psycopg
import os
import logging
from psycopg.rows import dict_row

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PostgresLoader:
    def __init__(self, db_url=None):
        self.db_url = db_url or os.environ.get('DATABASE_URL', 'postgresql://ufc_user:ufc_password@localhost:5432/ufc_predictor')

    def get_connection(self):
        return psycopg.connect(self.db_url, row_factory=dict_row)

    def upsert_fighter(self, fighter_data, dry_run=False):
        """
        Idempotent insertion/update of fighter.
        Uses ON CONFLICT (espn_id) DO UPDATE.
        """
        if dry_run:
            logging.info(f"DRY RUN: Would upsert fighter {fighter_data.get('name')} ({fighter_data.get('espn_id')})")
            return None
            
        query = """
        INSERT INTO fighters (
            espn_id, name, nickname, weight_class, nationality, 
            date_of_birth, height_cm, reach_cm, stance, 
            record_wins, record_losses, record_draws, last_scraped_at
        ) VALUES (
            %(espn_id)s, %(name)s, %(nickname)s, %(weight_class)s, %(nationality)s,
            %(dob)s, %(height_cm)s, %(reach_cm)s, %(stance)s,
            %(wins)s, %(losses)s, %(draws)s, NOW()
        ) ON CONFLICT (espn_id) DO UPDATE SET
            name = EXCLUDED.name,
            nickname = EXCLUDED.nickname,
            weight_class = EXCLUDED.weight_class,
            nationality = EXCLUDED.nationality,
            date_of_birth = EXCLUDED.date_of_birth,
            height_cm = EXCLUDED.height_cm,
            reach_cm = EXCLUDED.reach_cm,
            stance = EXCLUDED.stance,
            record_wins = EXCLUDED.record_wins,
            record_losses = EXCLUDED.record_losses,
            record_draws = EXCLUDED.record_draws,
            last_scraped_at = NOW()
        RETURNING fighter_id;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, fighter_data)
                fighter_id = cur.fetchone()['fighter_id']
                conn.commit()
                return fighter_id

    def upsert_event(self, event_data, dry_run=False):
        if dry_run:
            logging.info(f"DRY RUN: Would upsert event {event_data.get('name')} ({event_data.get('espn_event_id')})")
            return None
            
        query = """
        INSERT INTO events (
            espn_event_id, name, location, event_date, scraped_at
        ) VALUES (
            %(espn_event_id)s, %(name)s, %(location)s, %(event_date)s, NOW()
        ) ON CONFLICT (espn_event_id) DO UPDATE SET
            name = EXCLUDED.name,
            location = EXCLUDED.location,
            event_date = EXCLUDED.event_date,
            scraped_at = NOW()
        RETURNING event_id;
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, event_data)
                event_id = cur.fetchone()['event_id']
                conn.commit()
                return event_id

    def upsert_fight(self, fight_data, dry_run=False):
        """
        Given espn identifiers, resolves internal integer IDs using subqueries or fetching, 
        and upserts the fight.
        """
        if dry_run:
            logging.info(f"DRY RUN: Would upsert fight {fight_data.get('espn_fight_id')} between {fight_data.get('fighter_a_espn_id')} and {fight_data.get('fighter_b_espn_id')}")
            return None
            
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Resolve foreign keys
                cur.execute("SELECT event_id FROM events WHERE espn_event_id = %s", (fight_data['espn_event_id'],))
                res = cur.fetchone()
                event_id = res['event_id'] if res else None
                
                cur.execute("SELECT fighter_id FROM fighters WHERE espn_id = %s", (fight_data['fighter_a_espn_id'],))
                res = cur.fetchone()
                fa_id = res['fighter_id'] if res else None

                cur.execute("SELECT fighter_id FROM fighters WHERE espn_id = %s", (fight_data['fighter_b_espn_id'],))
                res = res = cur.fetchone()
                fb_id = res['fighter_id'] if res else None
                
                win_id = None
                if fight_data.get('winner_espn_id'):
                    cur.execute("SELECT fighter_id FROM fighters WHERE espn_id = %s", (fight_data['winner_espn_id'],))
                    res = cur.fetchone()
                    win_id = res['fighter_id'] if res else None

                if not event_id or not fa_id or not fb_id:
                     logging.warning(f"Could not resolve foreign keys for fight {fight_data['espn_fight_id']}. Skipping.")
                     return None
                
                fight_data['event_id'] = event_id
                fight_data['fighter_a_id'] = fa_id
                fight_data['fighter_b_id'] = fb_id
                fight_data['winner_id'] = win_id
                
                # Default card_order if the scraper didn't supply one, so old
                # call sites keep working after the schema migration.
                fight_data.setdefault('card_order', None)
                fight_data.setdefault('is_cancelled', False)

                query = """
                INSERT INTO fights (
                    espn_fight_id, event_id, fighter_a_id, fighter_b_id, winner_id,
                    method, round, time, weight_class, is_title_fight, fight_date,
                    card_order, is_cancelled, scraped_at
                ) VALUES (
                    %(espn_fight_id)s, %(event_id)s, %(fighter_a_id)s, %(fighter_b_id)s, %(winner_id)s,
                    %(method)s, %(round)s, %(time)s, %(weight_class)s, %(is_title_fight)s, %(fight_date)s,
                    %(card_order)s, %(is_cancelled)s, NOW()
                ) ON CONFLICT (espn_fight_id) DO UPDATE SET
                    -- Result fields fall back to existing value when the scrape returns NULL
                    -- (e.g. re-scraping an upcoming event must not wipe a previously-recorded winner).
                    winner_id = COALESCE(EXCLUDED.winner_id, fights.winner_id),
                    method = COALESCE(EXCLUDED.method, fights.method),
                    round = COALESCE(EXCLUDED.round, fights.round),
                    time = COALESCE(EXCLUDED.time, fights.time),
                    weight_class = EXCLUDED.weight_class,
                    is_title_fight = EXCLUDED.is_title_fight,
                    fight_date = EXCLUDED.fight_date,
                    card_order = EXCLUDED.card_order,
                    is_cancelled = EXCLUDED.is_cancelled,
                    scraped_at = NOW()
                RETURNING fight_id;
                """
                
                # Fetch fight_date from event to attach directly into fights
                cur.execute("SELECT event_date FROM events WHERE event_id = %s", (event_id,))
                fight_data['fight_date'] = cur.fetchone()['event_date']
                
                cur.execute(query, fight_data)
                fight_id = cur.fetchone()['fight_id']
                conn.commit()
                return fight_id

    def mark_missing_fights_as_cancelled(self, espn_event_id, active_espn_fight_ids, dry_run=False):
        """
        Flags any fights in the database for the given event that are not
        in the provided list of active_espn_fight_ids as cancelled.
        """
        if dry_run:
            logging.info(f"DRY RUN: Would flag missing fights for event {espn_event_id} as cancelled.")
            return

        query = """
        UPDATE fights
        SET is_cancelled = TRUE, scraped_at = NOW()
        WHERE event_id = (SELECT event_id FROM events WHERE espn_event_id = %s)
          AND NOT (espn_fight_id = ANY(%s))
          AND is_cancelled = FALSE;
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (espn_event_id, list(active_espn_fight_ids)))
                updated_count = cur.rowcount
                conn.commit()
                if updated_count > 0:
                    logging.info(f"Flagged {updated_count} missing fights as cancelled for event {espn_event_id}.")

    def upsert_fighter_stats(self, stats_rows, dry_run=False):
        """
        Batch upsert per-fight stats for a single fighter.
        stats_rows is a list of dicts from ESPNScraper.scrape_fighter_stats().
        Each row is matched to fight_id via (espn_event_id + fighter espn_id).
        """
        if dry_run:
            logging.info(f"DRY RUN: Would upsert {len(stats_rows)} stat rows")
            return 0

        inserted = 0
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                for row in stats_rows:
                    espn_event_id = row.get('espn_event_id')
                    espn_fighter_id = row.get('espn_fighter_id')
                    if not espn_event_id or not espn_fighter_id:
                        continue

                    # Resolve fighter_id
                    cur.execute("SELECT fighter_id FROM fighters WHERE espn_id = %s", (espn_fighter_id,))
                    f_res = cur.fetchone()
                    if not f_res:
                        continue
                    fighter_id = f_res['fighter_id']

                    # Resolve fight_id: find the fight in this event involving this fighter
                    cur.execute("""
                        SELECT f.fight_id FROM fights f
                        JOIN events e ON e.event_id = f.event_id
                        WHERE e.espn_event_id = %s
                          AND (f.fighter_a_id = %s OR f.fighter_b_id = %s)
                        LIMIT 1
                    """, (espn_event_id, fighter_id, fighter_id))
                    fight_res = cur.fetchone()
                    if not fight_res:
                        continue
                    fight_id = fight_res['fight_id']

                    cur.execute("""
                        INSERT INTO fighter_stats (
                            fight_id, fighter_id, espn_event_id,
                            knockdowns, sig_strikes_landed, sig_strikes_attempted,
                            total_strikes_landed, total_strikes_attempted,
                            sd_head_landed, sd_head_attempted,
                            sd_body_landed, sd_body_attempted,
                            sd_leg_landed, sd_leg_attempted,
                            sc_head_landed, sc_head_attempted,
                            sc_body_landed, sc_body_attempted,
                            sc_leg_landed, sc_leg_attempted,
                            sg_head_landed, sg_head_attempted,
                            sg_body_landed, sg_body_attempted,
                            sg_leg_landed, sg_leg_attempted,
                            pct_head, pct_body, pct_leg,
                            takedowns_landed, takedowns_attempted,
                            takedown_slams, takedown_accuracy, slam_rate,
                            submissions, reversals,
                            advances, advance_to_half_guard,
                            advance_to_back, advance_to_mount, advance_to_side
                        ) VALUES (
                            %(fight_id)s, %(fighter_id)s, %(espn_event_id)s,
                            %(knockdowns)s, %(sig_strikes_landed)s, %(sig_strikes_attempted)s,
                            %(total_strikes_landed)s, %(total_strikes_attempted)s,
                            %(sd_head_landed)s, %(sd_head_attempted)s,
                            %(sd_body_landed)s, %(sd_body_attempted)s,
                            %(sd_leg_landed)s, %(sd_leg_attempted)s,
                            %(sc_head_landed)s, %(sc_head_attempted)s,
                            %(sc_body_landed)s, %(sc_body_attempted)s,
                            %(sc_leg_landed)s, %(sc_leg_attempted)s,
                            %(sg_head_landed)s, %(sg_head_attempted)s,
                            %(sg_body_landed)s, %(sg_body_attempted)s,
                            %(sg_leg_landed)s, %(sg_leg_attempted)s,
                            %(pct_head)s, %(pct_body)s, %(pct_leg)s,
                            %(takedowns_landed)s, %(takedowns_attempted)s,
                            %(takedown_slams)s, %(takedown_accuracy)s, %(slam_rate)s,
                            %(submissions)s, %(reversals)s,
                            %(advances)s, %(advance_to_half_guard)s,
                            %(advance_to_back)s, %(advance_to_mount)s, %(advance_to_side)s
                        ) ON CONFLICT (fight_id, fighter_id) DO UPDATE SET
                            knockdowns = EXCLUDED.knockdowns,
                            sig_strikes_landed = EXCLUDED.sig_strikes_landed,
                            sig_strikes_attempted = EXCLUDED.sig_strikes_attempted,
                            total_strikes_landed = EXCLUDED.total_strikes_landed,
                            total_strikes_attempted = EXCLUDED.total_strikes_attempted,
                            sd_head_landed = EXCLUDED.sd_head_landed,
                            sd_head_attempted = EXCLUDED.sd_head_attempted,
                            sd_body_landed = EXCLUDED.sd_body_landed,
                            sd_body_attempted = EXCLUDED.sd_body_attempted,
                            sd_leg_landed = EXCLUDED.sd_leg_landed,
                            sd_leg_attempted = EXCLUDED.sd_leg_attempted,
                            sc_head_landed = EXCLUDED.sc_head_landed,
                            sc_head_attempted = EXCLUDED.sc_head_attempted,
                            sc_body_landed = EXCLUDED.sc_body_landed,
                            sc_body_attempted = EXCLUDED.sc_body_attempted,
                            sc_leg_landed = EXCLUDED.sc_leg_landed,
                            sc_leg_attempted = EXCLUDED.sc_leg_attempted,
                            sg_head_landed = EXCLUDED.sg_head_landed,
                            sg_head_attempted = EXCLUDED.sg_head_attempted,
                            sg_body_landed = EXCLUDED.sg_body_landed,
                            sg_body_attempted = EXCLUDED.sg_body_attempted,
                            sg_leg_landed = EXCLUDED.sg_leg_landed,
                            sg_leg_attempted = EXCLUDED.sg_leg_attempted,
                            pct_head = EXCLUDED.pct_head,
                            pct_body = EXCLUDED.pct_body,
                            pct_leg = EXCLUDED.pct_leg,
                            takedowns_landed = EXCLUDED.takedowns_landed,
                            takedowns_attempted = EXCLUDED.takedowns_attempted,
                            takedown_slams = EXCLUDED.takedown_slams,
                            takedown_accuracy = EXCLUDED.takedown_accuracy,
                            slam_rate = EXCLUDED.slam_rate,
                            submissions = EXCLUDED.submissions,
                            reversals = EXCLUDED.reversals,
                            advances = EXCLUDED.advances,
                            advance_to_half_guard = EXCLUDED.advance_to_half_guard,
                            advance_to_back = EXCLUDED.advance_to_back,
                            advance_to_mount = EXCLUDED.advance_to_mount,
                            advance_to_side = EXCLUDED.advance_to_side
                    """, {
                        'fight_id': fight_id,
                        'fighter_id': fighter_id,
                        'espn_event_id': espn_event_id,
                        **{k: row.get(k, 0) for k in [
                            'knockdowns', 'sig_strikes_landed', 'sig_strikes_attempted',
                            'total_strikes_landed', 'total_strikes_attempted',
                            'sd_head_landed', 'sd_head_attempted',
                            'sd_body_landed', 'sd_body_attempted',
                            'sd_leg_landed', 'sd_leg_attempted',
                            'sc_head_landed', 'sc_head_attempted',
                            'sc_body_landed', 'sc_body_attempted',
                            'sc_leg_landed', 'sc_leg_attempted',
                            'sg_head_landed', 'sg_head_attempted',
                            'sg_body_landed', 'sg_body_attempted',
                            'sg_leg_landed', 'sg_leg_attempted',
                            'pct_head', 'pct_body', 'pct_leg',
                            'takedowns_landed', 'takedowns_attempted',
                            'takedown_slams', 'takedown_accuracy', 'slam_rate',
                            'submissions', 'reversals',
                            'advances', 'advance_to_half_guard',
                            'advance_to_back', 'advance_to_mount', 'advance_to_side',
                        ]}
                    })
                    inserted += 1

                conn.commit()
        logging.info(f"Upserted {inserted} fighter stat rows into database.")
        return inserted

if __name__ == "__main__":
    pass
