# SKILL: ESPN Data Scraper

## Purpose
Scrape UFC fighter profiles, fight results, event data, and per-fight stats from ESPN and load them into PostgreSQL.

## Files It Owns
```
data/
├── scrapers/
│   ├── fighters.py       # Scrapes fighter index + profiles
│   ├── fights.py         # Scrapes fight results + events
│   ├── stats.py          # Scrapes per-fight stats
│   └── utils.py          # Shared HTTP session, retry logic, headers
└── loaders/
    ├── upsert_fighters.py
    ├── upsert_fights.py
    └── upsert_stats.py
```

## Key Libraries
- `requests` — HTTP calls (try this before Selenium)
- `beautifulsoup4` — HTML parsing
- `psycopg2` or `sqlalchemy` — PostgreSQL writes
- `python-dotenv` — load DATABASE_URL from .env

## Patterns

### Shared HTTP Session with Retry
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1.5,
                  status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; research bot)"
    })
    return session
```

### Dry Run Pattern (required on all scrapers)
```python
def scrape_fighters(dry_run: bool = True) -> list[dict]:
    session = make_session()
    fighters = []
    # ... scraping logic ...
    if dry_run:
        print(f"Would insert {len(fighters)} fighters")
        for f in fighters[:3]:
            print(f)
    else:
        upsert_fighters(fighters)
    return fighters
```

### Upsert Pattern
```sql
INSERT INTO fighters (espn_id, name, weight_class, ...)
VALUES (%s, %s, %s, ...)
ON CONFLICT (espn_id) DO UPDATE
  SET name = EXCLUDED.name,
      weight_class = EXCLUDED.weight_class,
      last_scraped_at = NOW();
```

### Staging Table Pattern
Write raw scraped data to `raw_fighters` first. Run a transform step to populate the clean `fighters` table. This lets you re-run transforms without re-scraping.

## Gotchas
- ESPN may return 200 with an empty body or redirect for missing fighters. Always check `len(soup.find_all(...)) > 0` before assuming data exists.
- **RATE LIMITING (403 Forbidden)**: If scraping too fast, ESPN (via CloudFront) will block the request with a 403 Forbidden ("The request could not be satisfied... There might be too much traffic"). 
- **Required Mitigation**: Introduce a strict `time.sleep(1)` between EVERY page request, and implement exponential backoff if a 403 or "too much traffic" phrasing is triggered.
- Some ESPN pages require a cookie consent header. If you get redirected, inspect the actual response URL.
- Fight dates on ESPN are in US Eastern time. Store all timestamps in UTC using `datetime.timezone.utc`.
- Per-fight stats are on a separate URL from the fight result. You need two requests per fight.

## LLM Instructions
- See spec Section 6 for the full scraping flow and idempotency requirements.
- See spec Section 5 for the exact table schemas you are writing into.
- All scrapers accept `dry_run=True` by default. Never make the default `False`.
- Do not use Selenium unless requests-based scraping fails. Document the reason if you switch.
- Log every failed request: URL, status code, and fighter/fight ID. Do not abort the full run on a single failure.
- Sort fights by `fight_date ASC` before any processing that depends on order (Elo computation depends on this).

## Status
NOT STARTED
