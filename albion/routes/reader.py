"""Reader routes - feed view, grid view, post view."""

from pathlib import Path

import markdown
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from albion.database import Post, Source, get_db
from albion.storage import read_post_markdown

_md = markdown.Markdown(extensions=["tables", "fenced_code", "nl2br"])

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    view: str = Query("feed", pattern="^(feed|grid)$"),
    source_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """Main reader page with feed or grid view."""
    per_page = 20
    query = db.query(Post).filter(Post.subscriber_only.is_(False))

    if source_id:
        query = query.filter(Post.source_id == source_id)

    total = query.count()
    posts = (
        query.order_by(desc(Post.published_at), desc(Post.scraped_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    sources = db.query(Source).filter(Source.enabled.is_(True)).order_by(Source.name).all()

    template = "reader/feed.html" if view == "feed" else "reader/grid.html"
    return request.app.state.templates.TemplateResponse(
        template,
        {
            "request": request,
            "posts": posts,
            "sources": sources,
            "current_source": source_id,
            "current_view": view,
            "page": page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        },
    )


@router.get("/post/{post_id}", response_class=HTMLResponse)
async def read_post(
    request: Request,
    post_id: int,
    db: Session = Depends(get_db),
):
    """Read a single post rendered from markdown."""
    post = db.query(Post).get(post_id)
    if not post:
        return HTMLResponse("<h1>Post not found</h1>", status_code=404)

    markdown_content = read_post_markdown(Path(post.file_path))
    if not markdown_content:
        markdown_content = "*Content not available.*"

    # Strip frontmatter for display
    if markdown_content.startswith("---"):
        parts = markdown_content.split("---", 2)
        if len(parts) >= 3:
            markdown_content = parts[2].strip()

    _md.reset()
    content_html = _md.convert(markdown_content)

    return request.app.state.templates.TemplateResponse(
        "reader/post.html",
        {
            "request": request,
            "post": post,
            "content": content_html,
        },
    )
