"""Ingest events, fights, fighter profiles, and per-fight stats into Postgres.

Combines what used to live across data/ingest.py + data/loaders/postgres_loader.py
into one module. Same SQL, cleaner shape.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from pipeline.db import connect
from pipeline.scrape import ESPNScraper

log = logging.getLogger(__name__)


# ───────────────────────────────────────────────────────── upserts


def upsert_fighter(cur, data: dict) -> int | None:
    cur.execute(
        """
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
        RETURNING fighter_id
        """,
        data,
    )
    row = cur.fetchone()
    return row["fighter_id"] if row else None


def upsert_event(cur, data: dict) -> int | None:
    cur.execute(
        """
        INSERT INTO events (
            espn_event_id, name, location, event_date, scraped_at
        ) VALUES (
            %(espn_event_id)s, %(name)s, %(location)s, %(event_date)s, NOW()
        ) ON CONFLICT (espn_event_id) DO UPDATE SET
            name = EXCLUDED.name,
            location = EXCLUDED.location,
            event_date = EXCLUDED.event_date,
            scraped_at = NOW()
        RETURNING event_id
        """,
        data,
    )
    row = cur.fetchone()
    return row["event_id"] if row else None


def upsert_fight(cur, data: dict) -> int | None:
    """Resolve FKs by espn_id, then upsert. Re-scrapes of upcoming events
    must not wipe a previously-recorded winner — see COALESCE below."""
    cur.execute(
        "SELECT event_id, event_date FROM events WHERE espn_event_id = %s",
        (data["espn_event_id"],),
    )
    ev = cur.fetchone()
    if not ev:
        log.warning("Skipping fight %s: event %s not found", data.get("espn_fight_id"), data.get("espn_event_id"))
        return None

    cur.execute("SELECT fighter_id FROM fighters WHERE espn_id = %s", (data["fighter_a_espn_id"],))
    fa = cur.fetchone()
    cur.execute("SELECT fighter_id FROM fighters WHERE espn_id = %s", (data["fighter_b_espn_id"],))
    fb = cur.fetchone()

    if not fa or not fb:
        log.warning("Skipping fight %s: fighter FK unresolved", data.get("espn_fight_id"))
        return None

    win_id = None
    if data.get("winner_espn_id"):
        cur.execute("SELECT fighter_id FROM fighters WHERE espn_id = %s", (data["winner_espn_id"],))
        w = cur.fetchone()
        win_id = w["fighter_id"] if w else None

    payload = {
        **data,
        "event_id": ev["event_id"],
        "fighter_a_id": fa["fighter_id"],
        "fighter_b_id": fb["fighter_id"],
        "winner_id": win_id,
        "fight_date": ev["event_date"],
        "card_order": data.get("card_order"),
        "is_cancelled": data.get("is_cancelled", False),
    }

    cur.execute(
        """
        INSERT INTO fights (
            espn_fight_id, event_id, fighter_a_id, fighter_b_id, winner_id,
            method, round, time, weight_class, is_title_fight, fight_date,
            card_order, is_cancelled, scraped_at
        ) VALUES (
            %(espn_fight_id)s, %(event_id)s, %(fighter_a_id)s, %(fighter_b_id)s, %(winner_id)s,
            %(method)s, %(round)s, %(time)s, %(weight_class)s, %(is_title_fight)s, %(fight_date)s,
            %(card_order)s, %(is_cancelled)s, NOW()
        ) ON CONFLICT (espn_fight_id) DO UPDATE SET
            -- COALESCE protects existing winner/method when re-scraping an upcoming event
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
        RETURNING fight_id
        """,
        payload,
    )
    row = cur.fetchone()
    return row["fight_id"] if row else None


def mark_missing_fights_cancelled(cur, espn_event_id: str, active_espn_fight_ids: list[str]) -> int:
    cur.execute(
        """
        UPDATE fights
           SET is_cancelled = TRUE, scraped_at = NOW()
         WHERE event_id = (SELECT event_id FROM events WHERE espn_event_id = %s)
           AND NOT (espn_fight_id = ANY(%s))
           AND is_cancelled = FALSE
        """,
        (espn_event_id, list(active_espn_fight_ids)),
    )
    return cur.rowcount


_STAT_FIELDS = [
    "knockdowns", "sig_strikes_landed", "sig_strikes_attempted",
    "total_strikes_landed", "total_strikes_attempted",
    "sd_head_landed", "sd_head_attempted",
    "sd_body_landed", "sd_body_attempted",
    "sd_leg_landed", "sd_leg_attempted",
    "sc_head_landed", "sc_head_attempted",
    "sc_body_landed", "sc_body_attempted",
    "sc_leg_landed", "sc_leg_attempted",
    "sg_head_landed", "sg_head_attempted",
    "sg_body_landed", "sg_body_attempted",
    "sg_leg_landed", "sg_leg_attempted",
    "pct_head", "pct_body", "pct_leg",
    "takedowns_landed", "takedowns_attempted",
    "takedown_slams", "takedown_accuracy", "slam_rate",
    "submissions", "reversals",
    "advances", "advance_to_half_guard",
    "advance_to_back", "advance_to_mount", "advance_to_side",
]


def upsert_fighter_stats(cur, rows: list[dict]) -> int:
    """Batch upsert fighter_stats. Each row carries espn_event_id and
    espn_fighter_id which are resolved to internal IDs."""
    inserted = 0
    for row in rows:
        espn_event_id = row.get("espn_event_id")
        espn_fighter_id = row.get("espn_fighter_id")
        if not espn_event_id or not espn_fighter_id:
            continue

        cur.execute("SELECT fighter_id FROM fighters WHERE espn_id = %s", (espn_fighter_id,))
        f = cur.fetchone()
        if not f:
            continue
        fighter_id = f["fighter_id"]

        cur.execute(
            """
            SELECT f.fight_id FROM fights f
              JOIN events e ON e.event_id = f.event_id
             WHERE e.espn_event_id = %s
               AND (f.fighter_a_id = %s OR f.fighter_b_id = %s)
             LIMIT 1
            """,
            (espn_event_id, fighter_id, fighter_id),
        )
        fight_row = cur.fetchone()
        if not fight_row:
            continue
        fight_id = fight_row["fight_id"]

        params = {
            "fight_id": fight_id,
            "fighter_id": fighter_id,
            "espn_event_id": espn_event_id,
            **{k: row.get(k, 0) for k in _STAT_FIELDS},
        }
        cur.execute(_FIGHTER_STATS_UPSERT, params)
        inserted += 1
    return inserted


_FIGHTER_STATS_UPSERT = """
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
"""


# ───────────────────────────────────────────────────────── orchestration


def ingest_events(year: int | None = None, mode: str = "recent") -> None:
    """Scrape the ESPN schedule for `year` and upsert events + fights + fighter profiles.

    mode controls which events get touched:
      "all"      — every event for the year
      "recent"   — events in [today-3d, future] (next ~3 events). Default for pre-event runs.
      "reconcile"— the single most-recent past event (last 7d). For post-event runs.
    """
    year = year or datetime.now().year
    scraper = ESPNScraper()
    events = scraper.scrape_schedule(year)

    if mode == "reconcile":
        today = datetime.now().date()
        cutoff = today - timedelta(days=7)
        events = [e for e in events if cutoff <= e["event_date"] <= today]
        events.sort(key=lambda e: e["event_date"], reverse=True)
        events = events[:1]
    elif mode == "recent":
        today = datetime.now().date()
        cutoff = today - timedelta(days=3)
        events = [e for e in events if e["event_date"] >= cutoff]
        events.sort(key=lambda e: e["event_date"])
        events = events[:3]
    elif mode != "all":
        raise ValueError(f"Unknown ingest mode: {mode}")

    log.info("Ingesting %d event(s) in %s mode", len(events), mode)

    with connect() as conn, conn.cursor() as cur:
        for event in events:
            log.info("Event: %s (%s)", event["name"], event["event_date"])
            upsert_event(cur, event)

            fights = scraper.scrape_event_fights(event["url"], event["espn_event_id"])
            log.info("  → %d fights", len(fights))

            for fight in fights:
                for espn_id in (fight.get("fighter_a_espn_id"), fight.get("fighter_b_espn_id")):
                    if espn_id:
                        profile = scraper.scrape_fighter_profile(espn_id=espn_id)
                        if profile:
                            upsert_fighter(cur, profile)
                upsert_fight(cur, fight)

            active_ids = [f["espn_fight_id"] for f in fights if f.get("espn_fight_id")]
            cancelled = mark_missing_fights_cancelled(cur, event["espn_event_id"], active_ids)
            if cancelled:
                log.info("  → %d fight(s) marked cancelled", cancelled)

            conn.commit()


def ingest_stats(active_only: bool = True) -> dict:
    """Scrape per-fight stats for fighters and upsert into fighter_stats."""
    scraper = ESPNScraper()
    with connect() as conn:
        with conn.cursor() as cur:
            if active_only:
                cur.execute("SELECT espn_id, name FROM fighters WHERE is_active = TRUE ORDER BY fighter_id")
            else:
                cur.execute("SELECT espn_id, name FROM fighters ORDER BY fighter_id")
            fighters = cur.fetchall()

    total = len(fighters)
    log.info("Scraping stats for %d fighter(s) (active_only=%s)", total, active_only)

    scraped, errors = 0, 0
    for i, f in enumerate(fighters, 1):
        try:
            log.info("  (%d/%d) %s", i, total, f["name"])
            stats_rows = scraper.scrape_fighter_stats(f["espn_id"])
            if stats_rows:
                with connect() as conn, conn.cursor() as cur:
                    upsert_fighter_stats(cur, stats_rows)
                    conn.commit()
                scraped += 1
        except Exception as e:
            errors += 1
            log.error("    error: %s", e)

    return {"scraped": scraped, "errors": errors}
