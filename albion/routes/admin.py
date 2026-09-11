"""Admin routes - source management, logs, settings."""

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from albion.database import PollLog, Post, Source, get_db
from albion.scheduler import schedule_all_sources

router = APIRouter(prefix="/admin")


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
):
    """Admin dashboard with overview."""
    sources = db.query(Source).order_by(Source.name).all()
    total_posts = db.query(Post).count()
    recent_errors = (
        db.query(PollLog)
        .filter(PollLog.status == "error")
        .order_by(desc(PollLog.timestamp))
        .limit(10)
        .all()
    )

    # Get last poll status per source
    source_stats = {}
    for source in sources:
        last_log = (
            db.query(PollLog)
            .filter(PollLog.source_id == source.id)
            .order_by(desc(PollLog.timestamp))
            .first()
        )
        post_count = db.query(Post).filter(Post.source_id == source.id).count()
        source_stats[source.id] = {
            "last_log": last_log,
            "post_count": post_count,
        }

    return request.app.state.templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "sources": sources,
            "total_posts": total_posts,
            "recent_errors": recent_errors,
            "source_stats": source_stats,
        },
    )


@router.get("/sources/add", response_class=HTMLResponse)
async def add_source_form(request: Request):
    """Show form to add a new source."""
    return request.app.state.templates.TemplateResponse(
        "admin/add_source.html",
        {"request": request},
    )


@router.post("/sources/add")
async def add_source(
    name: str = Form(...),
    url: str = Form(...),
    feed_url: str = Form(""),
    scraper_type: str = Form("wordpress"),
    poll_interval: int = Form(60),
    db: Session = Depends(get_db),
):
    """Add a new source."""
    source = Source(
        name=name,
        url=url,
        feed_url=feed_url or None,
        scraper_type=scraper_type,
        poll_interval_minutes=poll_interval,
        enabled=True,
    )
    db.add(source)
    db.commit()
    schedule_all_sources()
    return RedirectResponse("/admin", status_code=303)


@router.post("/sources/{source_id}/toggle")
async def toggle_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    """Enable/disable a source."""
    source = db.query(Source).get(source_id)
    if source:
        source.enabled = not source.enabled
        db.commit()
        schedule_all_sources()
    return RedirectResponse("/admin", status_code=303)


@router.post("/sources/{source_id}/delete")
async def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
):
    """Delete a source and its posts."""
    source = db.query(Source).get(source_id)
    if source:
        db.delete(source)
        db.commit()
        schedule_all_sources()
    return RedirectResponse("/admin", status_code=303)


@router.post("/sources/{source_id}/poll")
async def poll_now(
    source_id: int,
    db: Session = Depends(get_db),
):
    """Trigger an immediate poll for a source."""
    from albion.scheduler import poll_source
    import asyncio
    asyncio.ensure_future(poll_source(source_id))
    return RedirectResponse("/admin", status_code=303)


@router.get("/logs", response_class=HTMLResponse)
async def view_logs(
    request: Request,
    source_id: int | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """View poll logs with filtering."""
    per_page = 50
    query = db.query(PollLog)

    if source_id:
        query = query.filter(PollLog.source_id == source_id)
    if status:
        query = query.filter(PollLog.status == status)

    total = query.count()
    logs = (
        query.order_by(desc(PollLog.timestamp))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    sources = db.query(Source).order_by(Source.name).all()

    return request.app.state.templates.TemplateResponse(
        "admin/logs.html",
        {
            "request": request,
            "logs": logs,
            "sources": sources,
            "current_source": source_id,
            "current_status": status,
            "page": page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        },
    )
