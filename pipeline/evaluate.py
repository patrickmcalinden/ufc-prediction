"""Honest model evaluation: walk-forward backtest + missingness leak check.

Walk-forward: for each test year Y, train on every fight before Jan 1 of Y
(mirrored), score on Y's fights as-listed. This mirrors how the model is
actually used — trained on the past, predicting the next card.

Leak check: for every A/B feature pair, take the fights where exactly one
fighter has a value. If "has a value" alone predicts the winner, the
feature's *coverage* carries information the model won't have at prediction
time. This is what sank v2: fighters with stats history won 75.6% of those
fights, because stats only exist for fighters still active today.
"""

from __future__ import annotations

import logging
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss

log = logging.getLogger(__name__)

FIRST_TEST_YEAR = 2021
LEAK_MIN_ROWS = 100
LEAK_MAX_EDGE = 0.10   # flag if present-side win rate is outside 0.5 ± this


def _ab_pairs(features: list[str]) -> list[tuple[str, str]]:
    pairs = []
    for c in features:
        if c.startswith("a_") and f"b_{c[2:]}" in features:
            pairs.append((c, f"b_{c[2:]}"))
        elif c.endswith("_pre_a") and f"{c[:-1]}b" in features:
            pairs.append((c, f"{c[:-1]}b"))
    return pairs


def leak_check(df: pd.DataFrame, features: list[str]) -> dict:
    """df: one row per fight (not mirrored), NaN = no data, `label` = A won."""
    flagged = []
    for a, b in _ab_pairs(features):
        one_sided = df[a].notna() ^ df[b].notna()
        n = int(one_sided.sum())
        if n < LEAK_MIN_ROWS:
            continue
        sub = df[one_sided]
        present_won = np.where(sub[a].notna(), sub.label, 1 - sub.label)
        rate = float(present_won.mean())
        if abs(rate - 0.5) > LEAK_MAX_EDGE:
            flagged.append({"feature": a[2:] if a.startswith("a_") else a[:-6],
                            "n": n, "present_side_win_rate": round(rate, 3)})
    return {"passed": not flagged, "flagged": flagged}


def _scores(y, p) -> dict:
    y, p = np.asarray(y), np.asarray(p)
    return {
        "accuracy": float(accuracy_score(y, p >= 0.5)),
        "logloss": float(log_loss(y, p, labels=[0, 1])),
        "brier": float(brier_score_loss(y, p)),
        "n": int(len(y)),
    }


def walk_forward(
    df: pd.DataFrame,
    features: list[str],
    make_model: Callable[[], object],
    mirror: Callable[[pd.DataFrame], pd.DataFrame],
    clean_mask: pd.Series | None = None,
) -> dict:
    """df: one row per decided fight with `fight_date`, `label`, features.

    clean_mask: optional per-row bool; if given, also report scores on just
    those test rows (used for leak-flagged models, to estimate how they do
    on fights where the leak can't help them).
    """
    years = pd.to_datetime(df.fight_date).dt.year
    last_year = int(years.max())
    P, Y, C = [], [], []
    per_year = {}
    for yr in range(FIRST_TEST_YEAR, last_year + 1):
        train, test = df[years < yr], df[years == yr]
        if test.empty:
            continue
        tr = mirror(train)
        m = make_model()
        m.fit(tr[features], tr["label"])
        p = m.predict_proba(test[features])[:, 1]
        per_year[yr] = _scores(test["label"], p)
        P.extend(p)
        Y.extend(test["label"])
        if clean_mask is not None:
            C.extend(clean_mask[test.index])
        log.info("  %d: acc=%.3f logloss=%.3f n=%d", yr, per_year[yr]["accuracy"],
                 per_year[yr]["logloss"], per_year[yr]["n"])

    out = {
        "method": "walk_forward",
        "test_years": [FIRST_TEST_YEAR, last_year],
        **_scores(Y, P),
        "per_year": per_year,
    }
    if clean_mask is not None:
        C = np.asarray(C, dtype=bool)
        out["clean_subset"] = _scores(np.asarray(Y)[C], np.asarray(P)[C])
    return out
