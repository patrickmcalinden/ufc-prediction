"""Model lab: backtest candidate feature sets against a registered model.

    python -m pipeline.experiment experiments/001_reach_height.py
    python -m pipeline.experiment experiments/001_reach_height.py --log

An experiment is a small Python file (see experiments/README.md):

    NAME = "reach_height"
    HYPOTHESIS = "Reach/height advantage adds signal on top of v3."
    BASE = "v3"                          # registered v3-family model to beat

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
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import logging
import math
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
BOOTSTRAP_ROWS = 2000


def _load(path: Path):
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


def run(path: Path) -> dict:
    mod = _load(path)
    base_cfg = get_model(getattr(mod, "BASE", "v3"))
    if base_cfg.feature_set != "v3":
        raise ValueError("BASE must be a v3-family model (feature_set='v3')")

    engine = create_engine(sqlalchemy_url())
    frame = build_v3_frame(engine)
    if hasattr(mod, "add_features"):
        frame = mod.add_features(frame, engine)
    df = frame[frame["label"].notna()].sort_values("fight_date").reset_index(drop=True)
    df["label"] = df["label"].astype(int)
    y = df["label"]

    def backtest(cfg):
        return evaluate.walk_forward(df, cfg.features, lambda: _build_classifier(cfg), mirror, return_preds=True)

    log.info("Backtesting base %s", base_cfg.name)
    base = backtest(base_cfg)
    base_ll = _row_logloss(y[base["preds"].index], base["preds"])

    results = {"name": getattr(mod, "NAME", path.stem), "hypothesis": getattr(mod, "HYPOTHESIS", ""),
               "base": base_cfg.name, "base_eval": base, "candidates": {}}
    for cname, spec in _candidates(mod).items():
        cfg = dataclasses.replace(base_cfg, name=cname, features=list(spec["features"]),
                                  **spec.get("params", {}))
        missing = [f for f in cfg.features if f not in df.columns]
        if missing:
            raise KeyError(f"[{cname}] features not in frame: {missing}")
        leak = evaluate.leak_check(df, cfg.features)
        log.info("Backtesting %s (%d features)", cname, len(cfg.features))
        ev = backtest(cfg)
        diff = _row_logloss(y[ev["preds"].index], ev["preds"]) - base_ll
        ci = _paired_ci(diff)
        years = sorted(ev["per_year"])
        won = sum(ev["per_year"][yr]["logloss"] < base["per_year"][yr]["logloss"] for yr in years)
        results["candidates"][cname] = {
            "eval": ev, "leak": leak, "n_features": len(cfg.features),
            "d_logloss": float(diff.mean()), "ci": ci, "years_won": won, "n_years": len(years),
            "verdict": _verdict(leak["passed"], ci, won, len(years)),
        }
    return results


def report(r: dict) -> str:
    b = r["base_eval"]
    lines = [
        f"Experiment: {r['name']}",
        f"Hypothesis: {r['hypothesis']}",
        f"Backtest {b['test_years'][0]}-{b['test_years'][1]}, n={b['n']}",
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
    lines += ["", "Δlogloss < 0 is better. 'better' needs the CI entirely below 0 AND a win in ≥2/3 of test years."]
    return "\n".join(lines)


def append_log(r: dict, path: Path = LOG_PATH) -> None:
    b = r["base_eval"]
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
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("pipeline.evaluate",):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    r = run(args.experiment)
    print("\n" + report(r))
    if args.log:
        append_log(r)


if __name__ == "__main__":
    main()
