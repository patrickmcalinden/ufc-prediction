# SKILL: FastAPI Backend

## Purpose
Serve fighter data, fight predictions, bet tracker records, model performance metrics, and blog post content as a JSON API consumed by the React frontend.

## Files It Owns
```
api/
├── main.py
├── db/
│   ├── connection.py      # SQLAlchemy engine + session factory
│   └── models.py          # SQLAlchemy ORM models (mirror the schema)
├── routers/
│   ├── fighters.py
│   ├── fights.py
│   ├── predictions.py
│   ├── bets.py
│   ├── blog.py
│   └── model_perf.py
└── schemas/
    ├── fighter.py         # Pydantic request/response models
    ├── fight.py
    ├── prediction.py
    ├── bet.py
    └── blog.py
```

## Key Libraries
- `fastapi` — web framework
- `uvicorn` — ASGI server
- `sqlalchemy` — ORM
- `pydantic` — data validation and response schemas
- `python-dotenv` — env var loading
- `python-frontmatter` — parse YAML frontmatter from blog .md files

## Patterns

### App Setup with CORS
```python
# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import fighters, fights, predictions, bets, blog, model_perf
import os

app = FastAPI(title="UFC Predictor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if os.getenv("ENV") == "development" else [os.environ["FRONTEND_URL"]],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fighters.router, prefix="/fighters", tags=["fighters"])
app.include_router(fights.router, prefix="/fights", tags=["fights"])
app.include_router(predictions.router, prefix="/predictions", tags=["predictions"])
app.include_router(bets.router, prefix="/bets", tags=["bets"])
app.include_router(blog.router, prefix="/blog", tags=["blog"])
app.include_router(model_perf.router, prefix="/model", tags=["model"])
```

### Database Dependency
```python
# api/db/connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os

engine = create_engine(os.environ["DATABASE_URL"])
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Router Pattern with Pagination
```python
# api/routers/fighters.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from api.db.connection import get_db
from api.schemas.fighter import FighterResponse

router = APIRouter()

@router.get("/", response_model=list[FighterResponse])
def list_fighters(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(Fighter).offset(skip).limit(limit).all()

@router.get("/{fighter_id}", response_model=FighterResponse)
def get_fighter(fighter_id: int, db: Session = Depends(get_db)):
    fighter = db.query(Fighter).filter(Fighter.fighter_id == fighter_id).first()
    if not fighter:
        raise HTTPException(status_code=404, detail="Fighter not found")
    return fighter
```

### Blog Endpoint (reads markdown files)
```python
# api/routers/blog.py
import frontmatter
from pathlib import Path

BLOG_DIR = Path(__file__).parent.parent.parent / "blog"

@router.get("/{slug}")
def get_post(slug: str):
    path = BLOG_DIR / f"{slug}.md"
    # Strip the date prefix from filename when matching slug
    matches = list(BLOG_DIR.glob(f"*-{slug}.md"))
    if not matches:
        raise HTTPException(status_code=404, detail="Post not found")
    post = frontmatter.load(str(matches[0]))
    return {"slug": slug, "metadata": post.metadata, "content": post.content}
```

### Bet Settlement Endpoint
```python
@router.patch("/{bet_id}/settle")
def settle_bet(bet_id: int, result: str, payout_usd: float, db: Session = Depends(get_db)):
    bet = db.query(Bet).filter(Bet.bet_id == bet_id).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Bet not found")
    bet.result = result  # "WIN", "LOSS", "PUSH"
    bet.payout_usd = payout_usd
    bet.profit_usd = payout_usd - bet.stake_usd if result == "WIN" else -bet.stake_usd
    db.commit()
    return bet
```

## Gotchas
- FastAPI does not serve static files by default. Blog markdown content is returned as a string in the JSON response — the frontend renders it. Do not set up a static file mount unless explicitly needed.
- SQLAlchemy ORM models and Pydantic schemas are separate things. Define both. ORM models map to DB tables; Pydantic schemas define API input/output shape.
- Pydantic v2 (FastAPI default) uses `model_config = ConfigDict(from_attributes=True)` instead of `class Config: orm_mode = True`.
- Always add `ENV=development` to your .env for local CORS to allow `*`. Without this, the React dev server at port 5173 will be blocked.

## LLM Instructions
- See spec Section 9 for the full route list and design decisions.
- See spec Section 5 for the database schema your ORM models must mirror.
- Never return raw SQLAlchemy model objects — always use Pydantic response schemas.
- All list endpoints must have `skip` and `limit` parameters with defaults `0` and `50`.
- The bet tracker has no authentication. POST /bets and PATCH /bets/{id}/settle are open endpoints.
- Blog post content is returned as a raw markdown string. The frontend handles rendering.

## Status
NOT STARTED
