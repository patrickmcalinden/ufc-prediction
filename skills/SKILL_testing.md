# SKILL: Testing

## Purpose
Ensure system reliability and validity by providing a standardized automated testing approach across the Full-Stack ML Project.

## Files It Owns
```
model/
└── evaluation/
    ├── test_elo.py              # Validate Elo logic
    └── test_model.py            # Train/Eval scripts for ML testing
api/
└── tests/                       # Pytest unit tests for the FastAPI routing layer
frontend/
└── src/
    └── __tests__/               # Frontend tests (Vitest/Jest)
```

## Key Libraries
- `pytest` — Primary python testing framework for both API and data ingestion methodologies.
- `vitest` or `jest` — Default testing solution in the React (Vite) ecosystem (dependant on setup).
- `scikit-learn` (TimeSeriesSplit) — Ensure data leakage does not occur via TimeSeries Cross-Validation.

## Patterns

### Machine Learning Testing
```python
from sklearn.model_selection import TimeSeriesSplit

# IMPORTANT: Use TimeSeriesSplit, not random KFold.
# We must not train on future fights to predict past ones.
tscv = TimeSeriesSplit(n_splits=5)
```

### Pytest FastAPI Testing
Used for unit testing API routes offline using Starlette TestClient.

```python
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_read_main():
    response = client.get("/fighters")
    assert response.status_code == 200
```

## Gotchas
- **Data Leakage in Model:** If doing standard KFold on a time-series fight database, you will overfit because training will include future outcomes.
- For testing the scraper logic, utilize the `dry_run=True` behavior implemented on scrapers to test the parsing logic without mutating the database table.

## LLM Instructions
- See Spec Section 8.3 and 17.6 regarding error handling and test methodologies.
- In tests, use mocks on any API calls or file reading that depend on third-party sources (e.g. ESPN).

## Status
NOT STARTED
