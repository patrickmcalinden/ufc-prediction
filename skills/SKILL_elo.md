# SKILL: Elo Rating Computation

## Purpose
Compute and store standard Elo and modified (opponent-quality-weighted) Elo ratings for every fighter after each of their fights, in chronological order.

## Files It Owns
```
model/
└── features/
    ├── elo.py            # Core Elo computation functions
    └── elo_pipeline.py   # Runs full Elo pass over all historical fights
```

## Key Libraries
- `pandas` — loading fights from DB into a DataFrame for ordered processing
- `sqlalchemy` — reading fights, writing elo_ratings rows
- `python-dotenv` — database connection

## Patterns

### Constants File (not magic numbers)
```python
# model/features/elo_config.py
ELO_CONFIG = {
    "starting_rating": 1500,
    "base_k": 32,
    "elite_threshold": 1600,
    "elite_multiplier": 1.5,
    "weak_threshold": 1400,
    "weak_multiplier": 0.75,
}
```

### Standard Elo
```python
def expected_score(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def update_standard_elo(
    winner_rating: float,
    loser_rating: float,
    k: float = 32
) -> tuple[float, float]:
    exp = expected_score(winner_rating, loser_rating)
    return winner_rating + k * (1 - exp), loser_rating + k * (0 - (1 - exp))
```

### Modified Elo (opponent-quality K-factor)
```python
def modified_k(opponent_rating: float, config: dict) -> float:
    if opponent_rating >= config["elite_threshold"]:
        return config["base_k"] * config["elite_multiplier"]
    elif opponent_rating <= config["weak_threshold"]:
        return config["base_k"] * config["weak_multiplier"]
    else:
        t = (opponent_rating - config["weak_threshold"]) / (
            config["elite_threshold"] - config["weak_threshold"]
        )
        return config["base_k"] * (
            config["weak_multiplier"]
            + t * (config["elite_multiplier"] - config["weak_multiplier"])
        )

def update_modified_elo(
    winner_rating: float,
    loser_rating: float,
    config: dict
) -> tuple[float, float]:
    k_w = modified_k(loser_rating, config)
    k_l = modified_k(winner_rating, config)
    exp = expected_score(winner_rating, loser_rating)
    return winner_rating + k_w * (1 - exp), loser_rating + k_l * (0 - (1 - exp))
```

### Full Pipeline Pattern
```python
def run_elo_pipeline(db_session, config: dict) -> None:
    # 1. Load all completed fights sorted chronologically — THIS ORDER IS MANDATORY
    fights = db_session.execute(
        "SELECT * FROM fights WHERE winner_id IS NOT NULL ORDER BY fight_date ASC"
    ).fetchall()

    # 2. Initialize all fighters at starting rating
    ratings_std: dict[int, float] = {}
    ratings_mod: dict[int, float] = {}

    for fight in fights:
        a_id, b_id, winner_id = fight.fighter_a_id, fight.fighter_b_id, fight.winner_id
        a_std = ratings_std.get(a_id, config["starting_rating"])
        b_std = ratings_std.get(b_id, config["starting_rating"])
        a_mod = ratings_mod.get(a_id, config["starting_rating"])
        b_mod = ratings_mod.get(b_id, config["starting_rating"])

        # Store PRE-fight ratings (used as ML features)
        pre_a_std, pre_b_std = a_std, b_std
        pre_a_mod, pre_b_mod = a_mod, b_mod

        if winner_id == a_id:
            a_std, b_std = update_standard_elo(a_std, b_std, config["base_k"])
            a_mod, b_mod = update_modified_elo(a_mod, b_mod, config)
        else:
            b_std, a_std = update_standard_elo(b_std, a_std, config["base_k"])
            b_mod, a_mod = update_modified_elo(b_mod, a_mod, config)

        ratings_std[a_id] = a_std
        ratings_std[b_id] = b_std
        ratings_mod[a_id] = a_mod
        ratings_mod[b_id] = b_mod

        # Upsert both fighters' ratings for this fight
        # ... insert into elo_ratings ...
```

## Gotchas
- **Order is everything.** If fights are not sorted `ASC` by `fight_date`, Elo values will be wrong and there is no obvious error — they will just be meaningless numbers.
- Fights with `winner_id IS NULL` are draws or future fights. Skip them during Elo computation but do not delete them.
- A fighter appearing for the first time starts at `starting_rating` (1500). Do not assume they have a pre-existing row in `elo_ratings`.
- Store `elo_standard_pre` and `elo_modified_pre` (the rating BEFORE the fight) as well as the post-fight ratings. The ML model uses pre-fight ratings as features — using post-fight ratings would be data leakage.

## LLM Instructions
- See spec Section 7 for the full Elo system design including thresholds and multipliers.
- See spec Section 5.1 for the `elo_ratings` table schema.
- All config values (thresholds, multipliers, base K) must come from `elo_config.py`. Never hard-code them.
- The pipeline must be re-runnable (idempotent). Use `ON CONFLICT (fighter_id, fight_id) DO UPDATE` when writing to `elo_ratings`.
- After running the pipeline, do a sanity check: query the top 10 fighters by `elo_modified` and confirm they are recognizable names. If the list looks random, the sort order is wrong.

## Status
NOT STARTED
