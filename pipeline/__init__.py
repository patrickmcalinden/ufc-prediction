"""UFC prediction pipeline.

Two entrypoints, one command:
    python -m pipeline.run --pre-event [--event-id N]   # lock predictions for upcoming event
    python -m pipeline.run --post-event                  # grade + Elo update + export

See REWRITE_PLAN.md for architecture.
"""
