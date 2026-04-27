# SKILL: Markdown Blog

## Purpose
Write and publish blog posts as markdown files. Sync post metadata to PostgreSQL. Serve content via the FastAPI blog router.

## Files It Owns
```
blog/
└── YYYY-MM-DD-slug.md     # All posts live here

data/loaders/
└── sync_blog.py           # Parses frontmatter, upserts into blog_posts table
```

## Key Libraries
- `python-frontmatter` — parse YAML frontmatter from .md files
- `sqlalchemy` — upsert into blog_posts table

## Patterns

### File Naming Convention
```
YYYY-MM-DD-slug.md

Examples:
  2025-03-15-how-modified-elo-works.md
  2025-04-02-first-card-results.md
  2025-04-20-xgboost-tuning-notes.md
```

The `slug` is the URL-safe identifier used in `/blog/{slug}` API routes and frontend routing.
The date prefix enforces chronological ordering in the file system.

### Frontmatter Template
```yaml
---
title: How the Modified Elo System Works
summary: A breakdown of how opponent quality changes the Elo K-factor and why it matters for predictions.
tags: [elo, model, methodology]
published_at: 2025-03-15
is_published: true
---

Post body starts here in standard markdown.

## Section Heading

Regular paragraph text. You can use all standard markdown features.
```

### Sync Script
```python
# data/loaders/sync_blog.py
import frontmatter
from pathlib import Path
from sqlalchemy.orm import Session

BLOG_DIR = Path(__file__).parent.parent.parent / "blog"

def sync_blog_posts(db: Session, dry_run: bool = True) -> None:
    posts = []
    for path in sorted(BLOG_DIR.glob("*.md")):
        post = frontmatter.load(str(path))
        # Extract slug: strip date prefix (YYYY-MM-DD-)
        slug = "-".join(path.stem.split("-")[3:])
        posts.append({
            "slug": slug,
            "title": post.metadata.get("title", ""),
            "summary": post.metadata.get("summary", ""),
            "tags": post.metadata.get("tags", []),
            "published_at": post.metadata.get("published_at"),
            "is_published": post.metadata.get("is_published", False),
        })

    if dry_run:
        print(f"Would upsert {len(posts)} posts:")
        for p in posts:
            print(f"  {p['slug']} — published: {p['is_published']}")
        return

    for p in posts:
        db.execute("""
            INSERT INTO blog_posts (slug, title, summary, tags, published_at, is_published)
            VALUES (:slug, :title, :summary, :tags, :published_at, :is_published)
            ON CONFLICT (slug) DO UPDATE SET
                title = EXCLUDED.title,
                summary = EXCLUDED.summary,
                tags = EXCLUDED.tags,
                published_at = EXCLUDED.published_at,
                is_published = EXCLUDED.is_published
        """, p)
    db.commit()
    print(f"Synced {len(posts)} posts.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-dry-run", action="store_true")
    args = parser.parse_args()
    # ... connect db and call sync_blog_posts(db, dry_run=not args.no_dry_run)
```

## Gotchas
- Set `is_published: false` in frontmatter while drafting. Only set `true` when ready to go live. The API should filter for `is_published = TRUE` on list endpoints.
- The slug in the filename must match what the frontend uses in the URL. Keep it lowercase, hyphens only, no special characters.
- `python-frontmatter` returns `post.metadata` as a dict and `post.content` as the markdown body string.
- Tags are stored as a PostgreSQL `TEXT[]` array. Pass them as a Python list when inserting.

## LLM Instructions
- See spec Section 12 for the blog design decisions.
- See spec Section 5 for the `blog_posts` table schema.
- The blog post body is never stored in the database — only metadata. The API reads the .md file directly for content.
- The sync script uses `dry_run=True` by default. Always run with dry run first to verify what will be upserted.
- Do not build a CMS, admin interface, or file upload endpoint. Posts are written locally and committed to the repo.

## Status
NOT STARTED
