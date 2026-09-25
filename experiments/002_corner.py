"""Does ESPN's listing order (fighter A = red corner / billed first) carry signal?

Fighter A wins ~57% historically and 55.3% of our locked picks. Order is
stable pre vs post fight: 0 of 98 locked v1 snapshots whose Elo could be
matched had A/B swapped. v3 mirrors every fight, which erases this.

d_corner = +1 on every listed row; history.mirror negates d_* columns, so
mirrored rows get -1. The model can then learn a corner effect while
training stays symmetric. At prediction time d_corner is +1.
"""

from pipeline.history import FEATURES_V3

NAME = "corner"
HYPOTHESIS = "ESPN's A/B listing order (A wins ~57%) adds signal v3 mirrors away."
BASE = "v3"


def add_features(df, engine):
    df["d_corner"] = 1.0
    return df


CANDIDATES = {"corner": {"features": FEATURES_V3 + ["d_corner"]}}
