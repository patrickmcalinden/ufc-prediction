from fastapi import APIRouter, HTTPException
import frontmatter
from pathlib import Path

router = APIRouter()
BLOG_DIR = Path(__file__).parent.parent.parent / "blog"

@router.get("/")
def list_posts():
    if not BLOG_DIR.exists():
        return []
    posts = []
    for file in BLOG_DIR.glob("*.md"):
        post = frontmatter.load(str(file))
        posts.append({
            "slug": post.metadata.get("slug", file.stem.split("-")[-1]),
            "title": post.metadata.get("title", file.stem),
            "published_at": post.metadata.get("date", None),
            "summary": post.metadata.get("summary", "")
        })
    return sorted(posts, key=lambda x: str(x["published_at"]), reverse=True)

@router.get("/{slug}")
def get_post(slug: str):
    if not BLOG_DIR.exists():
        raise HTTPException(status_code=404, detail="Blog directory not found")
        
    # Match precise slug or date-prefixed slug
    matches = list(BLOG_DIR.glob(f"*-{slug}.md")) + list(BLOG_DIR.glob(f"{slug}.md"))
    if not matches:
        raise HTTPException(status_code=404, detail="Post not found")
        
    post = frontmatter.load(str(matches[0]))
    return {
        "slug": slug, 
        "metadata": post.metadata, 
        "content": post.content
    }
