# SKILL: Database Management

## Purpose
Manage the PostgreSQL database schema migrations, SQLAlchemy ORM connections, and raw SQL data ingestion patterns.

## Files It Owns
```
data/
├── loaders/
│   └── (ingestion scripts connecting to DB)
└── sql/
    └── migrations/
        ├── 001_initial_schema.sql
        ├── 002_add_is_active_flag.sql
        └── 003_add_card_order.sql
api/
└── db/
    └── connection.py
```

## Key Libraries
- `psycopg2` — For raw SQL connections in data loaders
- `sqlalchemy` — ORM used in the FastAPI backend

## Patterns

### Raw SQL Idempotent Upsert (Loaders)
When writing scraping data back to the DB, always use `ON CONFLICT DO UPDATE` or `DO NOTHING` to ensure idempotency.
```sql
INSERT INTO fighters (espn_id, name, weight_class)
VALUES (%s, %s, %s)
ON CONFLICT (espn_id) DO UPDATE
  SET name = EXCLUDED.name,
      weight_class = EXCLUDED.weight_class,
      last_scraped_at = NOW();
```

### SQLAlchemy Setup (API)
```python
# api/db/connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost:5432/ufc_predictor')

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Migrations
Migrations are managed manually via numbered SQL files inside `data/sql/migrations/`.
```bash
# To run a migration (example)
psql -d ufc_predictor -f data/sql/migrations/004_new_migration.sql
```

## Gotchas
- Always use `snake_case` for table and column names in PostgreSQL.
- Do not use `SELECT *` in production code. Explicitly name the columns.
- Ensure you have a `.env` file properly set up with your `DATABASE_URL` for local development. Make sure not to commit it.

## LLM Instructions
- See Spec Section 5 for the exact table schemas.
- See Spec Section 17.2 for Database Standards.
- Never alter the schema without documenting the migration as a new numbered `.sql` file in `data/sql/migrations/`.

## Status
IN PROGRESS
