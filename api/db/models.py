from sqlalchemy import Column, Integer, String, Boolean, Date, Numeric, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from api.db.connection import Base

class Fighter(Base):
    __tablename__ = "fighters"
    fighter_id = Column(Integer, primary_key=True, index=True)
    espn_id = Column(String(64), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    nickname = Column(String(255))
    weight_class = Column(String(64))
    nationality = Column(String(128))
    date_of_birth = Column(Date)
    height_cm = Column(Numeric(5,1))
    reach_cm = Column(Numeric(5,1))
    stance = Column(String(32))
    record_wins = Column(Integer, default=0)
    record_losses = Column(Integer, default=0)
    record_draws = Column(Integer, default=0)
    is_active = Column(Boolean, default=False)
    
    elo_ratings = relationship("EloRating", back_populates="fighter")

class Event(Base):
    __tablename__ = "events"
    event_id = Column(Integer, primary_key=True, index=True)
    espn_event_id = Column(String(64), unique=True)
    name = Column(String(255))
    location = Column(String(255))
    event_date = Column(Date)
    
    fights = relationship("Fight", back_populates="event")

class Fight(Base):
    __tablename__ = "fights"
    fight_id = Column(Integer, primary_key=True, index=True)
    espn_fight_id = Column(String(64), unique=True)
    event_id = Column(Integer, ForeignKey("events.event_id"))
    fighter_a_id = Column(Integer, ForeignKey("fighters.fighter_id"))
    fighter_b_id = Column(Integer, ForeignKey("fighters.fighter_id"))
    winner_id = Column(Integer, ForeignKey("fighters.fighter_id"))
    method = Column(String(64))
    round = Column(Integer)
    time = Column(String(8))
    weight_class = Column(String(64))
    is_title_fight = Column(Boolean, default=False)
    fight_date = Column(Date)
    card_order = Column(Integer)
    is_cancelled = Column(Boolean, default=False)
    
    event = relationship("Event", back_populates="fights")
    predictions = relationship("Prediction", back_populates="fight")
    bets = relationship("Bet", back_populates="fight")

class EloRating(Base):
    __tablename__ = "elo_ratings"
    rating_id = Column(Integer, primary_key=True, index=True)
    fighter_id = Column(Integer, ForeignKey("fighters.fighter_id"))
    fight_id = Column(Integer, ForeignKey("fights.fight_id"))
    elo_standard = Column(Numeric(8,2))
    elo_modified = Column(Numeric(8,2))
    elo_standard_pre = Column(Numeric(8,2))
    elo_modified_pre = Column(Numeric(8,2))
    rating_date = Column(Date)
    
    fighter = relationship("Fighter", back_populates="elo_ratings")

class Prediction(Base):
    __tablename__ = "predictions"
    prediction_id = Column(Integer, primary_key=True, index=True)
    fight_id = Column(Integer, ForeignKey("fights.fight_id"))
    predicted_winner_id = Column(Integer, ForeignKey("fighters.fighter_id"))
    win_probability = Column(Numeric(5,4))
    model_version = Column(String(32))
    features_snapshot = Column(JSONB)
    actual_winner_id = Column(Integer, ForeignKey("fighters.fighter_id"))
    was_correct = Column(Boolean)
    
    fight = relationship("Fight", back_populates="predictions")

class Bet(Base):
    __tablename__ = "bets"
    bet_id = Column(Integer, primary_key=True, index=True)
    fight_id = Column(Integer, ForeignKey("fights.fight_id"))
    fighter_backed_id = Column(Integer, ForeignKey("fighters.fighter_id"))
    odds = Column(String(16))
    stake_usd = Column(Numeric(8,2))
    payout_usd = Column(Numeric(8,2))
    result = Column(String(8))
    profit_usd = Column(Numeric(8,2))
    notes = Column(Text)
    
    fight = relationship("Fight", back_populates="bets")
    fighter_backed = relationship("Fighter", foreign_keys=[fighter_backed_id])

# [UNUSED - MARKED FOR DELETION] 
# (Blog routing directly parses markdown frontmatter instead of querying Postgres)
class BlogPost(Base):
    __tablename__ = "blog_posts"
    post_id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(255), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    summary = Column(Text)
    published_at = Column(Date)
    is_published = Column(Boolean, default=False)
