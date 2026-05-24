# Bet Tracker API Reference

All write endpoints require the `X-API-Key` header. Set `BET_API_KEY` in `.env`.

---

## GET `/bets/`
List all bets. No auth required.

**Query params (optional)**
- `skip` — offset (default `0`)
- `limit` — max results (default `50`)

**Response fields**

| Field | Type | Notes |
|---|---|---|
| `bet_id` | int | Auto-assigned primary key |
| `fight_id` | int | |
| `fighter_backed_id` | int | |
| `fighter_backed_name` | string | Resolved from fighter ID |
| `event_name` | string | Resolved from fight → event |
| `odds` | string | American format e.g. `"-180"` |
| `stake_usd` | float | |
| `payout_usd` | float or null | |
| `result` | string or null | `"WIN"` or `"LOSS"` |
| `profit_usd` | float or null | |
| `notes` | string or null | |

---

## POST `/bets/`
Create a new bet. Requires `X-API-Key`.

Get `fight_id` and fighter IDs from the Predictions page (expand a card) or `GET /predictions/`.

**Body**

| Field | Required | Type | Notes |
|---|---|---|---|
| `fight_id` | ✅ | int | From predictions |
| `fighter_backed_id` | ✅ | int | `fighter_a_id` or `fighter_b_id` from predictions |
| `odds` | ✅ | string | American format — must be quoted e.g. `"-180"`, `"+135"` |
| `stake_usd` | ✅ | float | Amount wagered |
| `notes` | ❌ | string | Optional free text |

```json
{
  "fight_id": 65,
  "fighter_backed_id": 129,
  "odds": "-180",
  "stake_usd": 25.00,
  "notes": "Strong title defence"
}
```

---

## PUT `/bets/{id}`
Update any fields on an existing bet. Requires `X-API-Key`. Only fields included in the body are changed.

⚠️ Do not mix with PATCH `/settle` on the same bet — they overwrite each other. Use PUT to set everything at once.

⚠️ If you change `stake_usd` on an already-settled bet, manually recalculate `profit_usd`:
- WIN: `profit_usd = payout_usd - stake_usd`
- LOSS: `profit_usd = -stake_usd`

**Body (all optional)**

| Field | Type | Notes |
|---|---|---|
| `fight_id` | int | |
| `fighter_backed_id` | int | |
| `odds` | string | e.g. `"-180"` |
| `stake_usd` | float | |
| `notes` | string | |
| `result` | string | `"WIN"` or `"LOSS"` |
| `payout_usd` | float | Total returned including stake |
| `profit_usd` | float | Set manually when using PUT to settle |

```json
{
  "odds": "-180",
  "stake_usd": 25.00,
  "payout_usd": 28.00,
  "profit_usd": 3.00,
  "result": "WIN",
  "notes": "updated"
}
```

---

## PATCH `/bets/{id}/settle`
Settle a bet as WIN or LOSS. `profit_usd` is calculated automatically. Requires `X-API-Key`.

**Body**

| Field | Required | Type | Notes |
|---|---|---|---|
| `result` | ✅ | string | `"WIN"` or `"LOSS"` |
| `payout_usd` | ✅ | float | Total returned. Use `0` for a loss |

WIN example:
```json
{
  "result": "WIN",
  "payout_usd": 28.00
}
```

LOSS example:
```json
{
  "result": "LOSS",
  "payout_usd": 0
}
```

---

## DELETE `/bets/{id}`
Delete a single bet. Requires `X-API-Key`. No body needed.

---

## DELETE `/bets/bulk`
Delete multiple bets in one request. Requires `X-API-Key`.

**Body** — plain array of bet IDs:
```json
[1, 2, 3]
```

---

## Auth

All write endpoints check the `X-API-Key` header:

```
X-API-Key: your-secret-key
```

Generate a key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Add to `.env`:
```
BET_API_KEY=<generated value>
```
