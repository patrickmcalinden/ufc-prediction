from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from api.db.connection import get_db
from api.db.models import Bet, Fight, Event
from api.schemas.core import BetResponse, BetCreate, BetSettle, BetUpdate
from typing import List
from api.auth import verify_api_key

router = APIRouter()

@router.get("/", response_model=List[BetResponse])
def list_bets(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    bets = (
        db.query(Bet)
        .options(
            joinedload(Bet.fighter_backed),
            joinedload(Bet.fight).joinedload(Fight.event),
        )
        .order_by(desc(Bet.bet_id))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [BetResponse.from_orm_bet(b) for b in bets]

@router.post("/", response_model=BetResponse, dependencies=[Depends(verify_api_key)])
def create_bet(bet_in: BetCreate, db: Session = Depends(get_db)):
    db_bet = Bet(**bet_in.model_dump())
    db.add(db_bet)
    db.commit()
    db.refresh(db_bet)
    return db_bet

@router.put("/{bet_id}", response_model=BetResponse, dependencies=[Depends(verify_api_key)])
def update_bet(bet_id: int, update_in: BetUpdate, db: Session = Depends(get_db)):
    bet = db.query(Bet).filter(Bet.bet_id == bet_id).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    for field, value in update_in.model_dump(exclude_unset=True).items():
        setattr(bet, field, value)
    db.commit()
    db.refresh(bet)
    return BetResponse.from_orm_bet(bet)

@router.delete("/bulk", status_code=204, dependencies=[Depends(verify_api_key)])
def delete_bets_bulk(bet_ids: List[int], db: Session = Depends(get_db)):
    deleted = db.query(Bet).filter(Bet.bet_id.in_(bet_ids)).delete(synchronize_session=False)
    db.commit()
    if deleted == 0:
        raise HTTPException(status_code=404, detail="No matching bets found")

@router.delete("/{bet_id}", status_code=204, dependencies=[Depends(verify_api_key)])
def delete_bet(bet_id: int, db: Session = Depends(get_db)):
    bet = db.query(Bet).filter(Bet.bet_id == bet_id).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    db.delete(bet)
    db.commit()

@router.patch("/{bet_id}/settle", response_model=BetResponse, dependencies=[Depends(verify_api_key)])
def settle_bet(bet_id: int, settle_in: BetSettle, db: Session = Depends(get_db)):
    bet = db.query(Bet).filter(Bet.bet_id == bet_id).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")

    bet.result = settle_in.result
    bet.payout_usd = settle_in.payout_usd
    bet.profit_usd = settle_in.payout_usd - float(bet.stake_usd) if settle_in.result == "WIN" else -float(bet.stake_usd)

    db.commit()
    db.refresh(bet)
    return bet
