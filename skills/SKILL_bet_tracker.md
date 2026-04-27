# SKILL: Bet Tracker

## Purpose
Manage user functionality to track placed bets, calculate Return on Investment (ROI), handle odds formatting, and compare performance against model predictions.

## Files It Owns
```
frontend/
└── src/
    ├── pages/
    │   └── Bets.jsx             # Public Bet Tracker Dashboard
    └── components/
        └── BetTable.jsx         # Sortable table component for bets
api/
└── routers/
    └── bets.py                  # Endpoints to create and settle bets
```

## Key Libraries
- `recharts` — For rendering the running profit/loss chart over time in the React frontend.
- `tanstack/react-query` — For fetching and mutating bet data.

## Patterns

### American to Decimal Odds Conversion
Odds are stored in American format (string). The frontend or backend (depending on computational need) handles conversion to decimal odds to easily compute ROI.
```python
def american_to_decimal(odds_str: str) -> float:
    odds = int(odds_str)
    if odds > 0:
        return (odds / 100) + 1
    else:
        return (100 / abs(odds)) + 1
```

### Bet Outcomes
Bets will have specific settled states in the `result` column, usually: `WIN`, `LOSS`, `PUSH`, or `NULL` (pending).

## Gotchas
- The Tracker is public by default for version 1. No auth is needed.
- Treat negative profit correctly (loss = `-stake_usd`).
- Always remember to compare the bet alongside the `predicted_winner` to calculate model-aligned tracking.

## LLM Instructions
- See Spec Section 11 for the Bet Tracker outline.
- Expose basic stats: Total Bets, Win/Loss Rate, ROI, and Total Profit.
- Use simple manual endpoints to create and resolve bets via a REST client (e.g. `POST /bets` and `PATCH /bets/{id}/settle`).

## Status
IN PROGRESS
