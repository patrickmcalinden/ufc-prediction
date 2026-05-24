"""Elo math + config. DB I/O lives in pipeline/elo_update.py.

Two formulations:
  * standard: classic Elo with a fixed K-factor
  * modified: K-factor scales by opponent strength — wins over elite
              opponents move you more, wins over scrubs move you less
"""

from __future__ import annotations

ELO_CONFIG = {
    "starting_rating": 1500.0,
    "base_k": 32.0,
    "elite_threshold": 1600.0,
    "elite_multiplier": 1.5,
    "weak_threshold": 1400.0,
    "weak_multiplier": 0.75,
}


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400.0))


def update_standard_elo(
    winner_rating: float,
    loser_rating: float,
    k: float = 32.0,
) -> tuple[float, float]:
    exp = expected_score(winner_rating, loser_rating)
    return (
        winner_rating + k * (1.0 - exp),
        loser_rating + k * (0.0 - (1.0 - exp)),
    )


def _modified_k(opponent_rating: float, config: dict) -> float:
    if opponent_rating >= config["elite_threshold"]:
        return config["base_k"] * config["elite_multiplier"]
    if opponent_rating <= config["weak_threshold"]:
        return config["base_k"] * config["weak_multiplier"]
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
    config: dict = ELO_CONFIG,
) -> tuple[float, float]:
    k_w = _modified_k(loser_rating, config)
    k_l = _modified_k(winner_rating, config)
    exp = expected_score(winner_rating, loser_rating)
    return (
        winner_rating + k_w * (1.0 - exp),
        loser_rating + k_l * (0.0 - (1.0 - exp)),
    )
