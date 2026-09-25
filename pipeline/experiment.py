"""Model lab: backtest candidate feature sets against a registered model.

    python -m pipeline.experiment experiments/001_reach_height.py
    python -m pipeline.experiment experiments/001_reach_height.py --log
    python -m pipeline.experiment experiments/0NN_final.py --final

An experiment is a small Python file (see experiments/README.md):

    NAME = "reach_height"
    HYPOTHESIS = "Reach/height advantage adds signal on top of v3."
    BASE = "v3"                          # registered v3-family model to beat, or
                                         # {"name", "features", "params"} for an
                                         # unregistered one (e.g. a search leader)

    def add_features(df, engine):        # optional; df = build_v3_frame()
        ...                              # use history.add_pair() for A/B stats
        return df

    CANDIDATES = {                       # or FEATURES = [...] (+ PARAMS = {...})
        "masked": {"features": [...], "params": {"max_depth": 4}},
    }

For each candidate this runs the leak check and the walk-forward backtest,
then compares against BASE on the same fights: accuracy, log loss, Brier,
a paired-bootstrap 95% CI on the log-loss difference, and how many test
years the candidate won. Nothing is saved to model/artifacts or the DB.

Search mode (default) only sees fights before evaluate.HOLDOUT_START.
--final scores on the held-out period instead, in one-year folds. Every
--final run is appended to model/HOLDOUT_LOG.md, no opt-out: the holdout
is only worth anything if we know how many times it's been looked at.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import logging
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from pipeline import evaluate
from pipeline.db import sqlalchemy_url
from pipeline.history import build_v3_frame, mirror
from pipeline.models import get as get_model
from pipeline.train import _build_classifier

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parent.parent
LOG_PATH = REPO / "model" / "EXPERIMENTS.md"
HOLDOUT_LOG_PATH = REPO / "model" / "HOLDOUT_LOG.md"
BOOTSTRAP_ROWS = 2000


def _load(path: Path):
    # Let experiment files import shared helpers (experiments/_lab.py).
    if str(path.resolve().parent) not in sys.path:
        sys.path.insert(0, str(path.resolve().parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _candidates(mod) -> dict[str, dict]:
    if hasattr(mod, "CANDIDATES"):
        return mod.CANDIDATES
    return {"candidate": {"features": mod.FEATURES, "params": getattr(mod, "PARAMS", {})}}


def _row_logloss(y: pd.Series, p: pd.Series) -> np.ndarray:
    p = p.clip(1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p)).to_numpy()


def _paired_ci(diff: np.ndarray, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), size=(BOOTSTRAP_ROWS, len(diff)))
    means = diff[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _verdict(leak_ok: bool, ci: tuple[float, float], years_won: int, n_years: int) -> str:
    if not leak_ok:
        return "LEAK"
    if ci[1] < 0 and years_won >= math.ceil(n_years * 2 / 3):
        return "better"
    if ci[0] > 0:
        return "worse"
    return "inconclusive"


def run(path: Path, final: bool = False) -> dict:
    mod = _load(path)
    base = getattr(mod, "BASE", "v3")
    if isinstance(base, dict):
        # An unregistered base (e.g. the current leader in a search):
        # {"name": ..., "features": [...], "params": {...}} on top of v3.
        base_cfg = dataclasses.replace(get_model(base.get("from", "v3")), name=base["name"],
                                       features=list(base["features"]), **base.get("params", {}))
    else:
        base_cfg = get_model(base)
    if base_cfg.feature_set != "v3":
        raise ValueError("BASE must be a v3-family model (feature_set='v3')")

    engine = create_engine(sqlalchemy_url())
    frame = build_v3_frame(engine)
    if hasattr(mod, "add_features"):
        frame = mod.add_features(frame, engine)
    df = frame[frame["label"].notna()].sort_values("fight_date").reset_index(drop=True)
    df["label"] = df["label"].astype(int)
    y = df["label"]
    search_df = df[pd.to_datetime(df.fight_date) < pd.Timestamp(evaluate.HOLDOUT_START)]

    def backtest(cfg):
        make = lambda: _build_classifier(cfg)  # noqa: E731
        if final:
            return evaluate.holdout(df, cfg.features, make, mirror)
        return evaluate.walk_forward(df, cfg.features, make, mirror, return_preds=True,
                                     end=evaluate.HOLDOUT_START)

    log.info("Backtesting base %s", base_cfg.name)
    base = backtest(base_cfg)
    base_ll = _row_logloss(y[base["preds"].index], base["preds"])

    results = {"name": getattr(mod, "NAME", path.stem), "hypothesis": getattr(mod, "HYPOTHESIS", ""),
               "base": base_cfg.name, "base_eval": base, "candidates": {}, "final": final}
    for cname, spec in _candidates(mod).items():
        cfg = dataclasses.replace(base_cfg, name=cname, features=list(spec["features"]),
                                  **spec.get("params", {}))
        missing = [f for f in cfg.features if f not in df.columns]
        if missing:
            raise KeyError(f"[{cname}] features not in frame: {missing}")
        # Leak check reads outcomes too, so it stays inside the search
        # window unless this is the final holdout run.
        leak = evaluate.leak_check(df if final else search_df, cfg.features)
        log.info("Backtesting %s (%d features)", cname, len(cfg.features))
        ev = backtest(cfg)
        diff = _row_logloss(y[ev["preds"].index], ev["preds"]) - base_ll
        ci = _paired_ci(diff)
        periods = "per_fold" if final else "per_year"
        years = sorted(ev[periods])
        won = sum(ev[periods][yr]["logloss"] < base[periods][yr]["logloss"] for yr in years)
        results["candidates"][cname] = {
            "eval": ev, "leak": leak, "n_features": len(cfg.features),
            "d_logloss": float(diff.mean()), "ci": ci, "years_won": won, "n_years": len(years),
            "verdict": _verdict(leak["passed"], ci, won, len(years)),
        }
    return results


def _window(r: dict) -> str:
    b = r["base_eval"]
    if r["final"]:
        return f"HOLDOUT from {b['start']} (folds: {', '.join(b['per_fold'])})"
    return f"Search backtest {b['test_years'][0]}-{b['test_years'][1]} (fights before {evaluate.HOLDOUT_START})"


def report(r: dict) -> str:
    b = r["base_eval"]
    lines = [
        f"Experiment: {r['name']}",
        f"Hypothesis: {r['hypothesis']}",
        f"{_window(r)}, n={b['n']}",
        "",
        f"{'model':<16}{'acc':>7}{'logloss':>9}{'brier':>8}{'Δlogloss':>10}  {'95% CI':<18}{'yrs won':>8}  verdict",
        f"{r['base'] + ' (base)':<16}{b['accuracy']:>7.3f}{b['logloss']:>9.4f}{b['brier']:>8.4f}",
    ]
    for name, c in r["candidates"].items():
        e = c["eval"]
        lines.append(
            f"{name:<16}{e['accuracy']:>7.3f}{e['logloss']:>9.4f}{e['brier']:>8.4f}{c['d_logloss']:>+10.4f}  "
            f"[{c['ci'][0]:+.4f}, {c['ci'][1]:+.4f}]{c['years_won']:>4}/{c['n_years']}    {c['verdict']}"
        )
        for f in c["leak"]["flagged"]:
            lines.append(f"    leak: {f['feature']} — present side wins {f['present_side_win_rate']:.1%} of {f['n']} one-sided fights")
    unit = "folds" if r["final"] else "years"
    lines += ["", f"Δlogloss < 0 is better. 'better' needs the CI entirely below 0 AND a win in ≥2/3 of test {unit}."]
    return "\n".join(lines)


_HOLDOUT_HEADER = f"""# Holdout log

Every scoring run on the held-out fights (on/after {evaluate.HOLDOUT_START}).
Written automatically by `pipeline.experiment --final`. Each extra look at
the holdout makes it a little less honest, so keep this list short.

| Date | Experiment / candidate | Base | # feat | Acc | Log loss | Δlogloss [95% CI] | Folds won | Verdict | Hypothesis |
|---|---|---|---|---|---|---|---|---|---|
"""


def append_log(r: dict, path: Path = LOG_PATH) -> None:
    b = r["base_eval"]
    if r["final"]:
        path = HOLDOUT_LOG_PATH
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_HOLDOUT_HEADER, encoding="utf-8")
    rows = []
    for name, c in r["candidates"].items():
        e = c["eval"]
        rows.append(
            f"| {date.today()} | {r['name']} / {name} | {r['base']} | {c['n_features']} "
            f"| {e['accuracy']:.3f} | {e['logloss']:.4f} | {c['d_logloss']:+.4f} "
            f"[{c['ci'][0]:+.4f}, {c['ci'][1]:+.4f}] | {c['years_won']}/{c['n_years']} "
            f"| {c['verdict']} | {r['hypothesis']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(rows) + "\n")
    log.info("Appended %d row(s) to %s (base %s acc=%.3f ll=%.4f)", len(rows), path.name,
             r["base"], b["accuracy"], b["logloss"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("experiment", type=Path, help="path to an experiments/*.py file")
    ap.add_argument("--log", action="store_true", help=f"append results to {LOG_PATH.relative_to(REPO)}")
    ap.add_argument("--final", action="store_true",
                    help="score on the HOLDOUT instead (always logged to model/HOLDOUT_LOG.md). Once per search.")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("pipeline.evaluate",):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    r = run(args.experiment, final=args.final)
    print("\n" + report(r))
    if args.log or args.final:
        append_log(r)


if __name__ == "__main__":
    main()
