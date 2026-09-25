"""Re-tune the Elo honestly, with method weights.

ELO3_CONFIG was tuned on 2019+ log loss, which overlaps both the search
test years and the holdout. Here the grid is scored ONLY on 2012-2020
fights (before every test year), using the raw Elo win probability, and
adds per-method K weights: KO/TKO, submission, unanimous and split/majority
decisions can move ratings by different amounts.

The chosen config becomes d_elo_rt (d_ prefix so mirroring negates it).
"""

import itertools
import logging

import numpy as np
import pandas as pd

import _lab
from _leader import LEADER, add_leader_features
from pipeline.history import FEATURES_V3

NAME = "elo_retune"
HYPOTHESIS = "An Elo tuned only on pre-2021 fights, with per-method K weights, beats ELO3_CONFIG."
BASE = LEADER
log = logging.getLogger(__name__)


def _elo(F, K, decay, w):
    start, R, last, out = 1500.0, {}, {}, np.empty(len(F))
    for i, r in enumerate(F.itertuples()):
        a, b = r.fighter_a_id, r.fighter_b_id
        for f in (a, b):
            if decay and f in last:
                yrs = (r.fight_date - last[f]).days / 365.25
                if yrs > 1:
                    R[f] = start + (R.get(f, start) - start) * (1 - decay) ** (yrs - 1)
        ra, rb = R.get(a, start), R.get(b, start)
        out[i] = ra - rb
        if pd.isna(r.winner_id):
            if r.method is not None:
                last[a] = last[b] = r.fight_date
            continue
        m = str(r.method)
        mw = w["ko"] if "KO" in m else w["sub"] if "Sub" in m else w["udec"] if m.startswith("U") else w["sdec"]
        s = 1.0 if r.winner_id == a else 0.0
        ea = 1 / (1 + 10 ** ((rb - ra) / 400))
        R[a], R[b] = ra + K * mw * (s - ea), rb + K * mw * ((1 - s) - (1 - ea))
        last[a] = last[b] = r.fight_date
    return out


def add_features(df, engine):
    df = add_leader_features(df, engine)
    F = _lab.load_fights(engine)
    y = np.where(F.winner_id == F.fighter_a_id, 1.0, np.where(F.winner_id == F.fighter_b_id, 0.0, np.nan))
    tune = (F.fight_date.dt.year >= 2012) & (F.fight_date.dt.year <= 2020) & ~np.isnan(y)
    best = None
    for K, decay, ko, sub, sdec in itertools.product((48, 64, 80), (0.1, 0.2, 0.3), (1.25, 1.5, 1.75), (1.25, 1.5), (0.5, 0.75, 1.0)):
        w = {"ko": ko, "sub": sub, "udec": 1.0, "sdec": sdec}
        d = _elo(F, K, decay, w)
        p = np.clip(1 / (1 + 10 ** (-d[tune] / 400)), 1e-6, 1 - 1e-6)
        ll = -np.mean(y[tune] * np.log(p) + (1 - y[tune]) * np.log(1 - p))
        if best is None or ll < best[0]:
            best = (ll, K, decay, w, d)
    ll, K, decay, w, d = best
    print(f"[006] chosen on 2012-2020: K={K} decay={decay} weights={w} raw-Elo logloss={ll:.4f}")
    df["d_elo_rt"] = df.fight_id.map(pd.Series(d, index=F.fight_id))
    return df


F_NO_ELO = [f for f in FEATURES_V3 if f != "elo3_diff"] + ["d_corner"]
CANDIDATES = {
    "replace": {"features": F_NO_ELO + ["d_elo_rt"]},
    "add": {"features": LEADER["features"] + ["d_elo_rt"]},
}
