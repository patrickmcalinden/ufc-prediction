"""Single CLI entrypoint for the whole pipeline.

  python -m pipeline.run --pre-event [--event-id N] [--model NAME] [--skip-train]
      Lock predictions for an upcoming event. By default trains and
      predicts every registered model (see pipeline.models.MODELS); pass
      --model NAME (repeatable) to limit to a subset.

  python -m pipeline.run --post-event [--skip-stats]
      Reconcile a completed event: scrape results, grade picks, update Elo.

  python -m pipeline.run --export-only        # rebuild site JSON
  python -m pipeline.run --elo-rebuild        # full Elo rebuild from scratch
"""

from __future__ import annotations

import argparse
import logging
import sys

from pipeline import elo_update, export, grade, ingest, predict, train
from pipeline.models import all_names


def _log_setup() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    )


def _heading(label: str) -> None:
    logging.info("─" * 60)
    logging.info(label)
    logging.info("─" * 60)


def run_pre_event(event_id: int | None, models: list[str], skip_train: bool, force: bool) -> None:
    _heading("1/4  INGEST upcoming events")
    ingest.ingest_events(mode="recent")

    if skip_train:
        logging.info("Skipping training (--skip-train)")
    else:
        _heading("2/4  TRAIN models: " + ", ".join(models))
        train.train_all(only=models)

    _heading("3/4  PREDICT upcoming event")
    summary = predict.predict_event(event_id=event_id, models=models, force=force)
    logging.info("predict: %s", summary)

    _heading("4/4  EXPORT site JSON")
    export.export_all()


def run_post_event(skip_stats: bool) -> None:
    _heading("1/5  INGEST results (reconcile)")
    ingest.ingest_events(mode="reconcile")

    if skip_stats:
        logging.info("Skipping stats (--skip-stats)")
    else:
        _heading("2/5  INGEST per-fight stats")
        stats_summary = ingest.ingest_stats(active_only=True)
        logging.info("stats: %s", stats_summary)

    _heading("3/5  GRADE locked predictions")
    grade_summary = grade.grade_predictions()
    logging.info("grade: %s", grade_summary)

    _heading("4/5  UPDATE Elo + refresh fighters.current_elo_*")
    elo_summary = elo_update.update_elo()
    logging.info("elo: %s", elo_summary)

    _heading("5/5  EXPORT site JSON")
    export.export_all()


def main() -> int:
    parser = argparse.ArgumentParser(description="UFC predictor pipeline")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pre-event", action="store_true", help="Lock predictions for the next event")
    mode.add_argument("--post-event", action="store_true", help="Grade results + update Elo")
    mode.add_argument("--export-only", action="store_true", help="Just rebuild site JSON")
    mode.add_argument("--elo-rebuild", action="store_true", help="Full Elo rebuild from scratch")

    parser.add_argument("--event-id", type=int, help="(--pre-event) explicit event_id; default = next upcoming")
    parser.add_argument(
        "--model",
        action="append",
        default=None,
        help="(--pre-event) limit to named model(s). Repeatable. Defaults to all registered models.",
    )
    parser.add_argument("--skip-train", action="store_true", help="(--pre-event) skip retraining")
    parser.add_argument("--skip-stats", action="store_true", help="(--post-event) skip the slow stats scrape")
    parser.add_argument("--force", action="store_true", help="(--pre-event) replace existing locked snapshots")

    args = parser.parse_args()
    _log_setup()

    if args.pre_event:
        models = args.model or all_names()
        run_pre_event(args.event_id, models, args.skip_train, args.force)
    elif args.post_event:
        run_post_event(args.skip_stats)
    elif args.export_only:
        _heading("EXPORT site JSON")
        export.export_all()
    elif args.elo_rebuild:
        _heading("FULL Elo rebuild")
        summary = elo_update.update_elo(full_rebuild=True)
        logging.info("elo: %s", summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
