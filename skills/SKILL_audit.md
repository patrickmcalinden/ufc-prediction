# SKILL: Codebase Audit (Dead Code & Streamlining)

## Purpose
Find code that can be deleted, simplified, or consolidated without
changing behavior. The codebase is a mix of Python (FastAPI + ETL +
ML training) and a Vite/React frontend, so the audit must look in
both halves and recognise the static-export contract documented in
`SKILL_codebase_additions.md` (some "unused" Python is actually
called by the static exporter, and some "unused" frontend files are
loaded as JSON at runtime — verify before deleting).

Use this skill whenever the user asks to "audit", "clean up", "find
dead code", "find unused", "simplify", "refactor for clarity", or
"trim" the codebase.

## Output Contract
Always produce a single Markdown report with these sections, in this
order. Skip a section only if it has zero findings — never invent
filler. Each finding cites a file path and line range so the user
can jump straight to it.

```
# Codebase Audit — <YYYY-MM-DD>

## 1. Safe to delete
   <file:line> — <what it is> — <why it's unused>

## 2. Likely dead, verify first
   <file:line> — <what it is> — <what to check before deleting>

## 3. Duplicated logic
   <files> — <the duplication> — <suggested consolidation>

## 4. Streamline opportunities
   <file:line> — <current shape> — <simpler shape>

## 5. Stale config / deps
   <file> — <entry> — <why it's stale>

## Summary
   - Lines deletable (high confidence): <N>
   - Files deletable (high confidence): <N>
   - Top 3 wins by impact: <bullets>
```

Confidence matters: section 1 is for things you are sure about
(no references anywhere, obvious leftover scripts, commented-out
blocks, `__pycache__` artefacts in git). Section 2 is for the rest.
Never put a finding in section 1 if you only grepped one folder.

## What to look for

### Python
- Top-level scripts that look like one-off debugging (`debug_*.py`,
  `investigate_*.py`, `test_*.py` outside `tests/`). Check if any
  Makefile, `.bat`/`.sh` script, GitHub workflow, or other Python
  module imports them. If nothing references them, they're dead.
- Functions/classes/constants defined but never imported. Use Grep
  to search for the symbol name across the repo (exclude the
  defining file). Watch out for dynamic dispatch (`getattr`,
  FastAPI route registration, SQLAlchemy model discovery) — these
  look unused but aren't.
- Unused imports at the top of files.
- `requirements.txt` entries that don't appear in any `import`
  statement (grep for the package name).
- Duplicate helpers — e.g. two functions that both convert a
  fighter slug to a display name, or two date-parsing helpers.
- Long `if/elif` chains over a fixed set of strings → dict lookup.
- Nested loops building a dict that could be a comprehension.
- Try/except blocks that silently swallow then re-raise, or that
  catch `Exception` only to `pass`.

### Frontend (React + Vite)
- Components in `frontend/src/components/` and pages in
  `frontend/src/pages/` that no other file imports. Check
  `App.jsx` and the router for the page set.
- Dead CSS classes — class names that don't appear in any JSX.
- API methods in `frontend/src/lib/api.js` that no component calls.
  Note: write methods (`createBet`, `settleBet`) that throw in
  static mode are *not* dead — they're guarded by `IS_STATIC`.
- Duplicated fetch/loading/error scaffolding across pages — pull
  into a hook (`useStaticJson`).
- `useEffect` blocks with empty bodies, or whose deps array
  causes re-runs that the author clearly didn't intend.

### Data / model layer
- Unused columns in dataframes (assigned, never read).
- Feature builders not referenced by any training script.
- Pickled/joblib artefacts in `data/` or `model/` that aren't
  loaded by current code paths.
- SQL files in `data/sql/` whose names don't appear in any loader
  or migration runner.

### Config & infra
- `.env.example` keys not read by any code.
- Docker services in `docker-compose.yml` not used by current
  workflow.
- GitHub workflow steps that reference deleted scripts.
- Entries in `.gitignore` for paths that no longer exist (low
  priority — only flag if it adds noise).

## How to actually do the audit

Work in this order. Don't skip ahead — early steps surface findings
that change later ones (e.g. deleting a script removes the only
caller of a helper, promoting that helper into "safe to delete").

1. **Map the entry points.** Read `api/main.py`, `frontend/src/App.jsx`,
   any CLI entry in `scripts/` and `data/`, and the GitHub workflow
   files. These are the roots of the live call graph. Anything not
   reachable from a root is a candidate.

2. **Sweep for orphan files.** For each Python file outside the
   entry-point set, grep for `from <module>` and `import <module>`.
   Zero hits = candidate. Do the same for JSX/JS files: grep for
   the basename (without extension) in import statements.

3. **Sweep for orphan symbols.** For each top-level `def`/`class`/
   `const` in non-trivial modules, grep for the symbol. One hit
   (the definition) = candidate.

4. **Pattern-scan for streamlining.** Read each non-trivial file
   once and note: long if-chains, nested loops, repeated try/except,
   repeated fetch boilerplate, copy-pasted JSX.

5. **Check requirements.** Cross-reference `requirements.txt` and
   `frontend/package.json` against actual imports.

6. **Write the report.** Put the highest-confidence wins first.
   Include a short summary at the bottom so the user can see the
   shape of the result without reading every finding.

## Things the audit must NOT do
- Don't delete anything. The deliverable is the report; the user
  decides what to remove.
- Don't flag style preferences (var naming, single vs double
  quotes, line length). That's a linter's job.
- Don't suggest splitting a working module into smaller modules
  unless there's a concrete duplication payoff. Premature
  modularisation is its own form of bloat.
- Don't propose new abstractions to "make future changes easier".
  Three similar lines is fine; only flag duplication when the
  consolidation is obviously net-shorter and clearer.
- Don't recommend changes that would break the static-site
  contract (see `SKILL_codebase_additions.md`). Anything reading
  from `frontend/public/data/` or writing into it is load-bearing
  even if it looks ad-hoc.

## Edge cases to remember
- `data/loaders/export_static_api.py` may be the only caller of
  several "unused-looking" exporters. Check it before flagging
  anything in `data/loaders/`.
- FastAPI route handlers can look unreferenced because they're
  registered via decorators. Don't flag handlers in
  `api/routers/`.
- Pydantic schemas in `api/schemas/` are referenced by string
  type hints in some FastAPI versions — verify before flagging.
- Files under `model/training/` may be invoked by shell scripts
  (`scripts/update_data.sh`, `scripts/update_data.bat`) rather
  than imported.
