from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, case, cast, Float
from typing import Optional
from api.db.connection import get_db
from api.db.models import Prediction, Fight, Fighter, Event, EloRating
from api.schemas.core import PredictionResponse, ResultResponse, ModelPerformanceResponse
from data.grade_predictions import grade_predictions

router = APIRouter()

@router.get("/", response_model=list[PredictionResponse])
def list_predictions(
    skip: int = 0,
    limit: int = 500,
    model_version: Optional[str] = Query(None, description="Filter by model version (e.g. v1, v2)"),
    db: Session = Depends(get_db)
):
    from datetime import date
    query = (
        db.query(Prediction)
        .join(Fight)
        .join(Event, Event.event_id == Fight.event_id)
        .filter(
            Fight.is_cancelled == False,
            # Deployed past events + all future events; excludes backtest-only events.
            (Event.deployed_at.isnot(None)) | (Event.event_date >= date.today()),
        )
    )
    if model_version:
        query = query.filter(Prediction.model_version == model_version)

    preds = (
        query
        .order_by(desc(Prediction.prediction_id))
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    results = []
    for p in preds:
        fight = db.query(Fight).filter(Fight.fight_id == p.fight_id).first()
        if not fight: continue
        
        fa = db.query(Fighter).filter(Fighter.fighter_id == fight.fighter_a_id).first()
        fb = db.query(Fighter).filter(Fighter.fighter_id == fight.fighter_b_id).first()
        pw = db.query(Fighter).filter(Fighter.fighter_id == p.predicted_winner_id).first()
        event = db.query(Event).filter(Event.event_id == fight.event_id).first()
        
        fa_elo = db.query(EloRating).filter(EloRating.fighter_id == fight.fighter_a_id).order_by(desc(EloRating.rating_id)).first()
        fb_elo = db.query(EloRating).filter(EloRating.fighter_id == fight.fighter_b_id).order_by(desc(EloRating.rating_id)).first()
        
        results.append({
           "prediction_id": p.prediction_id,
           "fight_id": p.fight_id,
           "predicted_winner_id": p.predicted_winner_id,
           "win_probability": p.win_probability,
           "model_version": p.model_version,
           "was_correct": p.was_correct,
           "fighter_a_id": fight.fighter_a_id,
           "fighter_b_id": fight.fighter_b_id,
           "fighter_a_name": fa.name if fa else "Unknown",
           "fighter_b_name": fb.name if fb else "Unknown",
           "predicted_winner_name": pw.name if pw else "Unknown",
           "event_name": event.name if event else "Unknown",
           "fight_date": fight.fight_date,
           "weight_class": fight.weight_class,
           "card_order": fight.card_order,
           "is_title_fight": fight.is_title_fight,
           "fighter_a_espn_id": fa.espn_id if fa else None,
           "fighter_b_espn_id": fb.espn_id if fb else None,
           "fighter_a_record": f"{fa.record_wins}-{fa.record_losses}-{fa.record_draws}" if fa else "0-0-0",
           "fighter_b_record": f"{fb.record_wins}-{fb.record_losses}-{fb.record_draws}" if fb else "0-0-0",
           "fighter_a_elo": float(fa_elo.elo_standard) if fa_elo and fa_elo.elo_standard is not None else None,
           "fighter_b_elo": float(fb_elo.elo_standard) if fb_elo and fb_elo.elo_standard is not None else None,
           "fighter_a_nationality": fa.nationality if fa else None,
           "fighter_b_nationality": fb.nationality if fb else None,
           "fighter_a_height_cm": float(fa.height_cm) if fa and fa.height_cm else None,
           "fighter_b_height_cm": float(fb.height_cm) if fb and fb.height_cm else None,
           "fighter_a_reach_cm": float(fa.reach_cm) if fa and fa.reach_cm else None,
           "fighter_b_reach_cm": float(fb.reach_cm) if fb and fb.reach_cm else None
        })
    return results


@router.get("/results", response_model=list[ResultResponse])
def list_results(
    skip: int = 0,
    limit: int = 500,
    model_version: Optional[str] = Query(None, description="Filter by model version"),
    db: Session = Depends(get_db)
):
    """Return completed predictions with fight outcome details for the Results page."""
    query = (
        db.query(Prediction)
        .join(Fight)
        .filter(Prediction.was_correct.isnot(None), Fight.is_cancelled == False)
    )
    if model_version:
        query = query.filter(Prediction.model_version == model_version)

    preds = (
        query
        .order_by(desc(Prediction.prediction_id))
        .offset(skip)
        .limit(limit)
        .all()
    )

    results = []
    for p in preds:
        fight = db.query(Fight).filter(Fight.fight_id == p.fight_id).first()
        if not fight:
            continue

        fa = db.query(Fighter).filter(Fighter.fighter_id == fight.fighter_a_id).first()
        fb = db.query(Fighter).filter(Fighter.fighter_id == fight.fighter_b_id).first()
        pw = db.query(Fighter).filter(Fighter.fighter_id == p.predicted_winner_id).first()
        aw = db.query(Fighter).filter(Fighter.fighter_id == fight.winner_id).first() if fight.winner_id else None
        event = db.query(Event).filter(Event.event_id == fight.event_id).first()

        results.append({
            "prediction_id": p.prediction_id,
            "fight_id": p.fight_id,
            "predicted_winner_id": p.predicted_winner_id,
            "predicted_winner_name": pw.name if pw else "Unknown",
            "actual_winner_id": fight.winner_id,
            "actual_winner_name": aw.name if aw else "Unknown",
            "win_probability": p.win_probability,
            "was_correct": p.was_correct,
            "model_version": p.model_version,
            "fighter_a_id": fight.fighter_a_id,
            "fighter_b_id": fight.fighter_b_id,
            "fighter_a_name": fa.name if fa else "Unknown",
            "fighter_b_name": fb.name if fb else "Unknown",
            "fighter_a_espn_id": fa.espn_id if fa else None,
            "fighter_b_espn_id": fb.espn_id if fb else None,
            "event_name": event.name if event else "Unknown",
            "fight_date": fight.fight_date,
            "weight_class": fight.weight_class,
            "is_title_fight": fight.is_title_fight,
            "card_order": fight.card_order,
            "method": fight.method,
            "round": fight.round,
            "time": fight.time,
        })
    return results


@router.get("/models", response_model=list[ModelPerformanceResponse])
def list_models(db: Session = Depends(get_db)):
    """Return performance stats for each model version.

    Scoped to predictions for deployed events only — backtest predictions
    are excluded so the leaderboard reflects live model performance.
    """
    rows = (
        db.query(
            Prediction.model_version,
            func.count(Prediction.prediction_id).label("total_predictions"),
            func.count(Prediction.was_correct).label("graded"),
            func.sum(case((Prediction.was_correct == True, 1), else_=0)).label("correct"),
            func.avg(Prediction.win_probability).label("avg_confidence"),
        )
        .join(Fight, Fight.fight_id == Prediction.fight_id)
        .join(Event, Event.event_id == Fight.event_id)
        .filter(Event.deployed_at.isnot(None))
        .group_by(Prediction.model_version)
        .order_by(Prediction.model_version)
        .all()
    )

    results = []
    for r in rows:
        total = r.total_predictions
        graded = r.graded
        correct = int(r.correct or 0)
        accuracy = round((correct / graded * 100), 1) if graded > 0 else 0.0
        avg_conf = round(float(r.avg_confidence or 0) * 100, 1)

        # High confidence accuracy (>70%) — also scoped to deployed events
        high_conf_q = (
            db.query(Prediction)
            .join(Fight, Fight.fight_id == Prediction.fight_id)
            .join(Event, Event.event_id == Fight.event_id)
            .filter(
                Prediction.model_version == r.model_version,
                Prediction.was_correct.isnot(None),
                Prediction.win_probability > 0.70,
                Event.deployed_at.isnot(None),
            )
        )
        high_conf_total = high_conf_q.count()
        high_conf_correct = high_conf_q.filter(Prediction.was_correct == True).count()
        high_conf_acc = round((high_conf_correct / high_conf_total * 100), 1) if high_conf_total > 0 else None

        results.append({
            "model_version": r.model_version,
            "total_predictions": total,
            "graded": graded,
            "correct": correct,
            "accuracy": accuracy,
            "avg_confidence": avg_conf,
            "high_conf_accuracy": high_conf_acc,
        })

    return results


@router.post("/grade")
def grade(dry_run: bool = False):
    """Grade all ungraded predictions against actual fight outcomes.

    Compares each prediction's predicted_winner_id to the fight's winner_id
    and sets was_correct + actual_winner_id. Fights that haven't happened
    yet (no winner_id) are skipped.

    Pass ?dry_run=true to preview without writing to the database.
    """
    summary = grade_predictions(dry_run=dry_run)
    return summary
