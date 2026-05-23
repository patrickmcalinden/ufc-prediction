# Bet Tracker — curl Reference

Write endpoints (`POST /bets`, `PATCH /bets/{id}/settle`) require an `X-API-Key` header.
Set the key in your `.env` as `BET_API_KEY`.

---

## Add a new bet

```bash
curl -X POST http://localhost:8000/bets/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_SECRET_KEY" \
  -d '{
    "fight_id": 123,
    "fighter_backed_id": 456,
    "odds": -150,
    "stake_usd": 50.00,
    "notes": "Strong wrestling advantage"
  }'
```

`odds` uses American format (negative = favourite, positive = underdog).  
`notes` is optional.

---

## Settle a bet

```bash
curl -X PATCH http://localhost:8000/bets/1/settle \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_SECRET_KEY" \
  -d '{
    "result": "WIN",
    "payout_usd": 83.33
  }'
```

`result` must be `"WIN"` or `"LOSS"`.  
`payout_usd` is total returned (stake + profit). For a loss, pass `0`.  
`profit_usd` is calculated automatically by the server.

---

## View all bets (public — no key needed)

```bash
curl http://localhost:8000/bets/
```

Optional pagination: `?skip=0&limit=50`

---

## Generate a strong API key

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Add the output to your `.env`:

```
BET_API_KEY=<generated value>
```
