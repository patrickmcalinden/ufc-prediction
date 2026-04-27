# model/features/elo.py
def expected_score(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400.0))

def update_standard_elo(
    winner_rating: float,
    loser_rating: float,
    k: float = 32.0
) -> tuple[float, float]:
    exp = expected_score(winner_rating, loser_rating)
    return winner_rating + k * (1.0 - exp), loser_rating + k * (0.0 - (1.0 - exp))

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
    return winner_rating + k_w * (1.0 - exp), loser_rating + k_l * (0.0 - (1.0 - exp))
