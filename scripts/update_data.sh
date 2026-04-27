#!/usr/bin/env bash
# Refresh the static JSON snapshot served by the GitHub Pages site.
#
# What it does:
#   1. Re-exports every API endpoint to frontend/public/data/ using the
#      live local Postgres database.
#   2. Stages the refreshed JSON files for commit.
#
# It does NOT push. Review with `git diff --stat`, then commit and push
# when you're happy.
#
# Requirements: a running local Postgres with DATABASE_URL set in .env
# (only used at export time — never shipped to the deployed site).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Exporting static JSON to frontend/public/data/"
python -m data.loaders.export_static_api

echo "==> Staging refreshed data files"
git add frontend/public/data blog

echo
echo "Done. Review with:"
echo "    git diff --stat --cached"
echo "Then commit + push:"
echo "    git commit -m \"Refresh static data\""
echo "    git push"
