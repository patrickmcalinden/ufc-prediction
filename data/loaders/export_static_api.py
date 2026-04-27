"""
Static API Exporter
===================
Connects to the live PostgreSQL database and exports every API endpoint's
response as static JSON files into frontend/public/data/.

This is designed to run on your always-on server BEFORE building the
frontend for GitHub Pages deployment. The React app will read these
JSON files instead of hitting a live API.

Usage:
    python -m data.loaders.export_static_api           # full export
    python -m data.loaders.export_static_api --dry-run  # preview only
"""

import json
import os
import sys
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Resolve paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

OUTPUT_DIR = PROJECT_ROOT / "frontend" / "public" / "data"

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://ufc_user:ufc_password@localhost:5432/ufc_predictor",
)


class JSONEncoder(json.JSONEncoder):
    """Handle date, Decimal, and other non-serializable types."""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def get_conn():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)


def write_json(filename: str, data, dry_run: bool = False):
    path = OUTPUT_DIR / filename
    if dry_run:
        print(f"  [DRY RUN] Would write {path}  ({len(data) if isinstance(data, list) else 'obj'} items)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, cls=JSONEncoder, ensure_ascii=False)
    size_kb = path.stat().st_size / 1024
    count = len(data) if isinstance(data, list) else "obj"
    print(f"  [OK] {path.name}  ({count} items, {size_kb:.1f} KB)")


# ─── Exporters ──────────────────────────────────────────────────────────

def export_fighters(cur, dry_run: bool):
    """Export the full fighters list (mirrors GET /fighters?limit=9999)."""
    cur.execute("""
        SELECT fighter_id, espn_id, name, nickname, weight_class,
               nationality, date_of_birth, height_cm, reach_cm, stance,
               record_wins, record_losses, record_draws, is_active
        FROM fighters
        ORDER BY record_wins DESC
    """)
    fighters = cur.fetchall()

    # Attach elo_ratings array to each fighter (mirrors the FighterResponse schema)
    for f in fighters:
        cur.execute("""
            SELECT elo_standard, elo_modified, rating_date
            FROM elo_ratings
            WHERE fighter_id = %s
            ORDER BY rating_id ASC
        """, (f["fighter_id"],))
        f["elo_ratings"] = cur.fetchall()

    write_json("fighters.json", fighters, dry_run)
    return fighters


def export_fighter_details(cur, fighters, dry_run: bool):
    """Export per-fighter detail & fight history (mirrors GET /fighters/:id and /fighters/:id/fights)."""
    fighters_dir = OUTPUT_DIR / "fighters"
    if not dry_run:
        fighters_dir.mkdir(parents=True, exist_ok=True)

    for f in fighters:
        fid = f["fighter_id"]

        # Fighter detail — same data as list entry, already has elo_ratings
        write_json(f"fighters/{fid}.json", f, dry_run)

        # Fight history (mirrors GET /fighters/:id/fights)
        cur.execute("""
            SELECT fight_id, fight_date, event_id, fighter_a_id, fighter_b_id,
                   winner_id, method, round, time, is_title_fight, weight_class
            FROM fights
            WHERE (fighter_a_id = %s OR fighter_b_id = %s)
              AND fight_date IS NOT NULL
            ORDER BY fight_date DESC
        """, (fid, fid))
        fights = cur.fetchall()

        fight_history = []
        for fight in fights:
            opponent_id = fight["fighter_b_id"] if fight["fighter_a_id"] == fid else fight["fighter_a_id"]

            cur.execute("SELECT name FROM fighters WHERE fighter_id = %s", (opponent_id,))
            opp = cur.fetchone()

            cur.execute("SELECT name FROM events WHERE event_id = %s", (fight["event_id"],))
            ev = cur.fetchone()

            if fight["winner_id"] is None:
                result = "NC"
            elif fight["winner_id"] == fid:
                result = "W"
            elif fight["winner_id"] == opponent_id:
                result = "L"
            else:
                result = "D"

            fight_history.append({
                "fight_id": fight["fight_id"],
                "fight_date": fight["fight_date"],
                "event_name": ev["name"] if ev else None,
                "opponent_name": opp["name"] if opp else "Unknown",
                "opponent_id": opponent_id,
                "result": result,
                "method": fight["method"],
                "round": fight["round"],
                "time": fight["time"],
                "is_title_fight": fight["is_title_fight"],
                "weight_class": fight["weight_class"],
            })

        write_json(f"fighters/{fid}_fights.json", fight_history, dry_run)


def export_predictions(cur, dry_run: bool):
    """Export predictions (mirrors GET /predictions)."""
    cur.execute("""
        SELECT p.prediction_id, p.fight_id, p.predicted_winner_id,
               p.win_probability, p.model_version, p.was_correct,
               f.fighter_a_id, f.fighter_b_id, f.fight_date,
               f.weight_class, f.card_order, f.is_title_fight,
               fa.name AS fighter_a_name, fa.espn_id AS fighter_a_espn_id,
               fa.record_wins AS fa_wins, fa.record_losses AS fa_losses, fa.record_draws AS fa_draws,
               fa.nationality AS fighter_a_nationality,
               fa.height_cm AS fighter_a_height_cm, fa.reach_cm AS fighter_a_reach_cm,
               fb.name AS fighter_b_name, fb.espn_id AS fighter_b_espn_id,
               fb.record_wins AS fb_wins, fb.record_losses AS fb_losses, fb.record_draws AS fb_draws,
               fb.nationality AS fighter_b_nationality,
               fb.height_cm AS fighter_b_height_cm, fb.reach_cm AS fighter_b_reach_cm,
               pw.name AS predicted_winner_name,
               e.name AS event_name
        FROM predictions p
        JOIN fights f ON p.fight_id = f.fight_id
        JOIN fighters fa ON f.fighter_a_id = fa.fighter_id
        JOIN fighters fb ON f.fighter_b_id = fb.fighter_id
        LEFT JOIN fighters pw ON p.predicted_winner_id = pw.fighter_id
        LEFT JOIN events e ON f.event_id = e.event_id
        ORDER BY p.prediction_id DESC
        LIMIT 150
    """)
    rows = cur.fetchall()

    predictions = []
    for r in rows:
        # Fetch latest Elo for each fighter
        cur.execute("""
            SELECT elo_standard FROM elo_ratings
            WHERE fighter_id = %s ORDER BY rating_id DESC LIMIT 1
        """, (r["fighter_a_id"],))
        fa_elo = cur.fetchone()

        cur.execute("""
            SELECT elo_standard FROM elo_ratings
            WHERE fighter_id = %s ORDER BY rating_id DESC LIMIT 1
        """, (r["fighter_b_id"],))
        fb_elo = cur.fetchone()

        predictions.append({
            "prediction_id": r["prediction_id"],
            "fight_id": r["fight_id"],
            "predicted_winner_id": r["predicted_winner_id"],
            "win_probability": r["win_probability"],
            "model_version": r["model_version"],
            "was_correct": r["was_correct"],
            "fighter_a_id": r["fighter_a_id"],
            "fighter_b_id": r["fighter_b_id"],
            "fighter_a_name": r["fighter_a_name"],
            "fighter_b_name": r["fighter_b_name"],
            "predicted_winner_name": r["predicted_winner_name"],
            "event_name": r["event_name"],
            "fight_date": r["fight_date"],
            "weight_class": r["weight_class"],
            "card_order": r["card_order"],
            "is_title_fight": r["is_title_fight"],
            "fighter_a_espn_id": r["fighter_a_espn_id"],
            "fighter_b_espn_id": r["fighter_b_espn_id"],
            "fighter_a_record": f"{r['fa_wins']}-{r['fa_losses']}-{r['fa_draws']}",
            "fighter_b_record": f"{r['fb_wins']}-{r['fb_losses']}-{r['fb_draws']}",
            "fighter_a_elo": float(fa_elo["elo_standard"]) if fa_elo and fa_elo["elo_standard"] else None,
            "fighter_b_elo": float(fb_elo["elo_standard"]) if fb_elo and fb_elo["elo_standard"] else None,
            "fighter_a_nationality": r["fighter_a_nationality"],
            "fighter_b_nationality": r["fighter_b_nationality"],
            "fighter_a_height_cm": float(r["fighter_a_height_cm"]) if r["fighter_a_height_cm"] else None,
            "fighter_b_height_cm": float(r["fighter_b_height_cm"]) if r["fighter_b_height_cm"] else None,
            "fighter_a_reach_cm": float(r["fighter_a_reach_cm"]) if r["fighter_a_reach_cm"] else None,
            "fighter_b_reach_cm": float(r["fighter_b_reach_cm"]) if r["fighter_b_reach_cm"] else None,
        })

    write_json("predictions.json", predictions, dry_run)


def export_results(cur, dry_run: bool):
    """Export completed prediction results (mirrors GET /predictions/results)."""
    cur.execute("""
        SELECT p.prediction_id, p.fight_id, p.predicted_winner_id,
               p.win_probability, p.was_correct, p.model_version,
               f.fighter_a_id, f.fighter_b_id, f.winner_id,
               f.fight_date, f.weight_class, f.is_title_fight,
               f.card_order, f.method, f.round, f.time,
               fa.name AS fighter_a_name, fa.espn_id AS fighter_a_espn_id,
               fb.name AS fighter_b_name, fb.espn_id AS fighter_b_espn_id,
               pw.name AS predicted_winner_name,
               aw.name AS actual_winner_name,
               e.name AS event_name
        FROM predictions p
        JOIN fights f ON p.fight_id = f.fight_id
        JOIN fighters fa ON f.fighter_a_id = fa.fighter_id
        JOIN fighters fb ON f.fighter_b_id = fb.fighter_id
        LEFT JOIN fighters pw ON p.predicted_winner_id = pw.fighter_id
        LEFT JOIN fighters aw ON f.winner_id = aw.fighter_id
        LEFT JOIN events e ON f.event_id = e.event_id
        WHERE p.was_correct IS NOT NULL
        ORDER BY p.prediction_id DESC
        LIMIT 500
    """)
    rows = cur.fetchall()

    results = []
    for r in rows:
        results.append({
            "prediction_id": r["prediction_id"],
            "fight_id": r["fight_id"],
            "predicted_winner_id": r["predicted_winner_id"],
            "predicted_winner_name": r["predicted_winner_name"],
            "actual_winner_id": r["winner_id"],
            "actual_winner_name": r["actual_winner_name"],
            "win_probability": r["win_probability"],
            "was_correct": r["was_correct"],
            "model_version": r["model_version"],
            "fighter_a_id": r["fighter_a_id"],
            "fighter_b_id": r["fighter_b_id"],
            "fighter_a_name": r["fighter_a_name"],
            "fighter_b_name": r["fighter_b_name"],
            "fighter_a_espn_id": r["fighter_a_espn_id"],
            "fighter_b_espn_id": r["fighter_b_espn_id"],
            "event_name": r["event_name"],
            "fight_date": r["fight_date"],
            "weight_class": r["weight_class"],
            "is_title_fight": r["is_title_fight"],
            "card_order": r["card_order"],
            "method": r["method"],
            "round": r["round"],
            "time": r["time"],
        })

    write_json("results.json", results, dry_run)


def export_bets(cur, dry_run: bool):
    """Export bets (mirrors GET /bets)."""
    cur.execute("""
        SELECT b.bet_id, b.fight_id, b.fighter_backed_id, b.odds,
               b.stake_usd, b.payout_usd, b.result, b.profit_usd, b.notes,
               fb.name AS fighter_backed_name,
               e.name AS event_name
        FROM bets b
        LEFT JOIN fighters fb ON b.fighter_backed_id = fb.fighter_id
        LEFT JOIN fights f ON b.fight_id = f.fight_id
        LEFT JOIN events e ON f.event_id = e.event_id
        ORDER BY b.bet_id DESC
        LIMIT 50
    """)
    rows = cur.fetchall()

    bets = []
    for r in rows:
        bets.append({
            "bet_id": r["bet_id"],
            "fight_id": r["fight_id"],
            "fighter_backed_id": r["fighter_backed_id"],
            "fighter_backed_name": r["fighter_backed_name"],
            "event_name": r["event_name"],
            "odds": r["odds"],
            "stake_usd": r["stake_usd"],
            "payout_usd": r["payout_usd"],
            "result": r["result"],
            "profit_usd": r["profit_usd"],
            "notes": r["notes"],
        })

    write_json("bets.json", bets, dry_run)


def export_models(cur, dry_run: bool):
    """Export per-model performance stats (mirrors GET /predictions/models)."""
    cur.execute("""
        SELECT model_version,
               COUNT(prediction_id) AS total_predictions,
               COUNT(was_correct)   AS graded,
               COALESCE(SUM(CASE WHEN was_correct = TRUE THEN 1 ELSE 0 END), 0) AS correct,
               AVG(win_probability) AS avg_confidence
        FROM predictions
        GROUP BY model_version
        ORDER BY model_version
    """)
    rows = cur.fetchall()

    models = []
    for r in rows:
        graded = r["graded"] or 0
        correct = int(r["correct"] or 0)
        accuracy = round((correct / graded * 100), 1) if graded > 0 else 0.0
        avg_conf = round(float(r["avg_confidence"] or 0) * 100, 1)

        cur.execute("""
            SELECT
              COUNT(*) FILTER (WHERE was_correct IS NOT NULL)               AS hc_total,
              COUNT(*) FILTER (WHERE was_correct IS NOT NULL AND was_correct = TRUE) AS hc_correct
            FROM predictions
            WHERE model_version = %s
              AND win_probability > 0.70
        """, (r["model_version"],))
        hc = cur.fetchone()
        hc_total = hc["hc_total"] or 0
        hc_correct = hc["hc_correct"] or 0
        high_conf_acc = round((hc_correct / hc_total * 100), 1) if hc_total > 0 else None

        models.append({
            "model_version": r["model_version"],
            "total_predictions": r["total_predictions"],
            "graded": graded,
            "correct": correct,
            "accuracy": accuracy,
            "avg_confidence": avg_conf,
            "high_conf_accuracy": high_conf_acc,
        })

    write_json("models.json", models, dry_run)


def export_blog(dry_run: bool):
    """Export blog posts (mirrors GET /blog and GET /blog/:slug)."""
    import frontmatter

    blog_dir = PROJECT_ROOT / "blog"
    if not blog_dir.exists():
        print("  ⚠ No blog/ directory found, skipping blog export")
        return

    posts_index = []
    for md_file in sorted(blog_dir.glob("*.md")):
        post = frontmatter.load(str(md_file))
        slug = post.metadata.get("slug", md_file.stem.split("-")[-1])

        posts_index.append({
            "slug": slug,
            "title": post.metadata.get("title", md_file.stem),
            "published_at": post.metadata.get("date", None),
            "summary": post.metadata.get("summary", ""),
        })

        # Individual post file
        post_data = {
            "slug": slug,
            "metadata": dict(post.metadata),
            "content": post.content,
        }
        write_json(f"blog/{slug}.json", post_data, dry_run)

    # Sort newest first
    posts_index.sort(key=lambda x: str(x.get("published_at", "")), reverse=True)
    write_json("blog.json", posts_index, dry_run)


# ─── Main ────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Export live API data to static JSON")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()

    dry_run = args.dry_run

    print("=" * 60)
    print("  STATIC API EXPORTER")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Mode:   {'DRY RUN' if dry_run else 'LIVE WRITE'}")
    print("=" * 60)

    conn = get_conn()
    cur = conn.cursor()

    try:
        print("\n[1/7] Exporting fighters list...")
        fighters = export_fighters(cur, dry_run)

        print(f"\n[2/7] Exporting per-fighter details ({len(fighters)} fighters)...")
        export_fighter_details(cur, fighters, dry_run)

        print("\n[3/7] Exporting predictions...")
        export_predictions(cur, dry_run)

        print("\n[4/7] Exporting results...")
        export_results(cur, dry_run)

        print("\n[5/7] Exporting bets...")
        export_bets(cur, dry_run)

        print("\n[6/7] Exporting model leaderboard...")
        export_models(cur, dry_run)

        print("\n[7/7] Exporting blog posts...")
        export_blog(dry_run)

        print("\n" + "=" * 60)
        print("  EXPORT COMPLETE ✓")
        print("=" * 60)

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
