from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from api.db.connection import get_db
from api.db.models import Fighter, Fight, Event
from api.schemas.core import FighterResponse, FighterFightResponse

router = APIRouter()

@router.get("/", response_model=list[FighterResponse])
def list_fighters(skip: int = 0, limit: int = 50, active_only: bool = False, db: Session = Depends(get_db)):
    query = db.query(Fighter)
    if active_only:
        query = query.filter(Fighter.is_active == True)
    # Map by wins as standard if active context missing elo
    return query.order_by(desc(Fighter.record_wins)).offset(skip).limit(limit).all()

@router.get("/{fighter_id}", response_model=FighterResponse)
def get_fighter(fighter_id: int, db: Session = Depends(get_db)):
    fighter = db.query(Fighter).filter(Fighter.fighter_id == fighter_id).first()
    if not fighter:
        raise HTTPException(status_code=404, detail="Fighter not found")
    return fighter

@router.get("/{fighter_id}/fights", response_model=list[FighterFightResponse])
def get_fighter_fights(fighter_id: int, db: Session = Depends(get_db)):
    """Return fight history for a fighter, most recent first."""
    fighter = db.query(Fighter).filter(Fighter.fighter_id == fighter_id).first()
    if not fighter:
        raise HTTPException(status_code=404, detail="Fighter not found")

    fights = (
        db.query(Fight)
        .filter(or_(Fight.fighter_a_id == fighter_id, Fight.fighter_b_id == fighter_id))
        .filter(Fight.fight_date.isnot(None))
        .order_by(desc(Fight.fight_date))
        .all()
    )

    results = []
    for fight in fights:
        opponent_id = fight.fighter_b_id if fight.fighter_a_id == fighter_id else fight.fighter_a_id
        opponent = db.query(Fighter).filter(Fighter.fighter_id == opponent_id).first()
        event = db.query(Event).filter(Event.event_id == fight.event_id).first()

        if fight.winner_id is None:
            result = "NC"
        elif fight.winner_id == fighter_id:
            result = "W"
        elif fight.winner_id == opponent_id:
            result = "L"
        else:
            result = "D"

        results.append(FighterFightResponse(
            fight_id=fight.fight_id,
            fight_date=fight.fight_date,
            event_name=event.name if event else None,
            opponent_name=opponent.name if opponent else "Unknown",
            opponent_id=opponent_id,
            result=result,
            method=fight.method,
            round=fight.round,
            time=fight.time,
            is_title_fight=fight.is_title_fight,
            weight_class=fight.weight_class,
        ))
    return results
