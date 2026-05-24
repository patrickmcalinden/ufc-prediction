from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import date

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class EloRatingBase(BaseSchema):
    elo_standard: Optional[float]
    elo_modified: Optional[float]
    rating_date: Optional[date]

class FighterResponse(BaseSchema):
    fighter_id: int
    espn_id: Optional[str]
    name: str
    nickname: Optional[str]
    weight_class: Optional[str]
    nationality: Optional[str]
    date_of_birth: Optional[date]
    height_cm: Optional[float]
    reach_cm: Optional[float]
    stance: Optional[str]
    record_wins: Optional[int]
    record_losses: Optional[int]
    record_draws: Optional[int]
    is_active: Optional[bool]
    elo_ratings: List[EloRatingBase] = []


class ModelPerformanceResponse(BaseSchema):
    model_version: str
    total_predictions: int
    graded: int
    correct: int
    accuracy: float
    avg_confidence: float
    high_conf_accuracy: Optional[float] = None


class FighterFightResponse(BaseSchema):
    fight_id: int
    fight_date: Optional[date]
    event_name: Optional[str]
    opponent_name: Optional[str]
    opponent_id: Optional[int]
    result: Optional[str]  # 'W', 'L', 'D', 'NC'
    method: Optional[str]
    round: Optional[int]
    time: Optional[str]
    is_title_fight: Optional[bool]
    weight_class: Optional[str]

class EventResponse(BaseSchema):
    event_id: int
    name: Optional[str]
    location: Optional[str]
    event_date: Optional[date]

class FightResponse(BaseSchema):
    fight_id: int
    event_id: Optional[int]
    fighter_a_id: Optional[int]
    fighter_b_id: Optional[int]
    winner_id: Optional[int]
    method: Optional[str]
    round: Optional[int]
    time: Optional[str]
    is_title_fight: Optional[bool]
    fight_date: Optional[date]

class PredictionResponse(BaseSchema):
    prediction_id: int
    fight_id: int
    predicted_winner_id: int
    win_probability: float
    model_version: str
    was_correct: Optional[bool]

    # Attached API Join Context:
    fighter_a_id: Optional[int] = None
    fighter_b_id: Optional[int] = None
    fighter_a_name: Optional[str] = "Unknown"
    fighter_b_name: Optional[str] = "Unknown"
    predicted_winner_name: Optional[str] = "Unknown"
    event_name: Optional[str] = "Unknown"
    fight_date: Optional[date] = None
    weight_class: Optional[str] = "Unknown"
    card_order: Optional[int] = None
    is_title_fight: Optional[bool] = False

    # Fighter UI additions
    fighter_a_espn_id: Optional[str] = None
    fighter_b_espn_id: Optional[str] = None
    fighter_a_record: Optional[str] = "0-0-0"
    fighter_b_record: Optional[str] = "0-0-0"
    fighter_a_elo: Optional[float] = None
    fighter_b_elo: Optional[float] = None
    fighter_a_nationality: Optional[str] = None
    fighter_b_nationality: Optional[str] = None
    fighter_a_height_cm: Optional[float] = None
    fighter_b_height_cm: Optional[float] = None
    fighter_a_reach_cm: Optional[float] = None
    fighter_b_reach_cm: Optional[float] = None

class ResultResponse(BaseSchema):
    prediction_id: int
    fight_id: int
    predicted_winner_id: int
    predicted_winner_name: Optional[str] = "Unknown"
    actual_winner_id: Optional[int] = None
    actual_winner_name: Optional[str] = "Unknown"
    win_probability: float
    was_correct: Optional[bool] = None
    model_version: Optional[str] = None

    fighter_a_id: Optional[int] = None
    fighter_b_id: Optional[int] = None
    fighter_a_name: Optional[str] = "Unknown"
    fighter_b_name: Optional[str] = "Unknown"
    fighter_a_espn_id: Optional[str] = None
    fighter_b_espn_id: Optional[str] = None

    event_name: Optional[str] = "Unknown"
    fight_date: Optional[date] = None
    weight_class: Optional[str] = "Unknown"
    is_title_fight: Optional[bool] = False
    card_order: Optional[int] = None

    method: Optional[str] = None
    round: Optional[int] = None
    time: Optional[str] = None

class BetCreate(BaseModel):
    fight_id: int
    fighter_backed_id: int
    odds: str
    stake_usd: float
    notes: Optional[str] = None

class BetSettle(BaseModel):
    result: str
    payout_usd: float

class BetUpdate(BaseModel):
    fight_id: Optional[int] = None
    fighter_backed_id: Optional[int] = None
    odds: Optional[str] = None
    stake_usd: Optional[float] = None
    notes: Optional[str] = None
    result: Optional[str] = None
    payout_usd: Optional[float] = None

class BetResponse(BaseSchema):
    bet_id: int
    fight_id: int
    fighter_backed_id: int
    fighter_backed_name: Optional[str] = None
    event_name: Optional[str] = None
    odds: str
    stake_usd: float
    payout_usd: Optional[float]
    result: Optional[str]
    profit_usd: Optional[float]
    notes: Optional[str]

    @classmethod
    def from_orm_bet(cls, bet):
        return cls(
            bet_id=bet.bet_id,
            fight_id=bet.fight_id,
            fighter_backed_id=bet.fighter_backed_id,
            fighter_backed_name=bet.fighter_backed.name if bet.fighter_backed else None,
            event_name=bet.fight.event.name if bet.fight and bet.fight.event else None,
            odds=bet.odds,
            stake_usd=float(bet.stake_usd),
            payout_usd=float(bet.payout_usd) if bet.payout_usd is not None else None,
            result=bet.result,
            profit_usd=float(bet.profit_usd) if bet.profit_usd is not None else None,
            notes=bet.notes,
        )
