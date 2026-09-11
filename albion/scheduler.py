"""Polling scheduler for scraping sources."""

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from albion.config import DEFAULT_POLL_INTERVAL_MINUTES
from albion.database import PollLog, Post, SessionLocal, Source
from albion.notifications import notify_new_post
from albion.scrapers import get_scraper
from albion.storage import build_post_path, save_post_markdown

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def poll_source(source_id: int):
    """Poll a single source for new posts."""
    with SessionLocal() as db:
        source = db.query(Source).get(source_id)
        if not source or not source.enabled:
            return

        scraper_cls = get_scraper(source.scraper_type)
        scraper = scraper_cls(source.url, source.feed_url)
        posts_added = 0

        try:
            discovered = await scraper.discover_posts()
            log.info("Discovered %d posts from %s", len(discovered), source.name)

            for post_data in discovered:
                if not post_data.url:
                    continue
                # Skip already-scraped posts
                existing = db.query(Post).filter(Post.url == post_data.url).first()
                if existing:
                    continue

                try:
                    full_post = await scraper.scrape_post(post_data.url)

                    # Skip subscriber-only content
                    if full_post.subscriber_only:
                        log.info("Skipping subscriber-only: %s", full_post.title)
                        continue

                    # Use feed data for fields the full scrape may miss
                    published = full_post.published_at or post_data.published_at
                    thumbnail = full_post.thumbnail or post_data.thumbnail
                    author = full_post.author or post_data.author

                    content_md = scraper.html_to_markdown(full_post.content_html)
                    rel_path = build_post_path(source.url, full_post.title, published)

                    save_post_markdown(
                        relative_path=rel_path,
                        title=full_post.title,
                        url=full_post.url,
                        author=author,
                        published_at=published,
                        content_md=content_md,
                        thumbnail=thumbnail,
                    )

                    db_post = Post(
                        source_id=source.id,
                        title=full_post.title,
                        url=full_post.url,
                        author=author,
                        published_at=published,
                        file_path=str(rel_path),
                        thumbnail=thumbnail,
                        subscriber_only=False,
                        excerpt=full_post.excerpt or post_data.excerpt,
                    )
                    db.add(db_post)
                    db.commit()
                    posts_added += 1

                    # Send notification
                    await notify_new_post(full_post.title, full_post.url, source.name)

                except Exception as exc:
                    log.error("Failed to scrape post %s: %s", post_data.url, exc)
                    continue

            db.add(PollLog(
                source_id=source.id,
                status="success",
                message=f"Found {len(discovered)} posts, added {posts_added} new",
                posts_found=posts_added,
            ))
            db.commit()
            log.info("Poll complete for %s: %d new posts", source.name, posts_added)

        except Exception as exc:
            log.error("Poll failed for %s: %s", source.name, exc)
            db.add(PollLog(
                source_id=source.id,
                status="error",
                message=str(exc),
                posts_found=0,
            ))
            db.commit()


def schedule_all_sources():
    """Register polling jobs for all enabled sources."""
    # Remove existing jobs
    scheduler.remove_all_jobs()

    with SessionLocal() as db:
        sources = db.query(Source).filter(Source.enabled.is_(True)).all()
        for source in sources:
            interval = source.poll_interval_minutes or DEFAULT_POLL_INTERVAL_MINUTES
            scheduler.add_job(
                _run_poll,
                "interval",
                minutes=interval,
                args=[source.id],
                id=f"poll_{source.id}",
                replace_existing=True,
                next_run_time=datetime.now(timezone.utc),  # Run immediately on startup
            )
            log.info("Scheduled %s every %d minutes", source.name, interval)


async def _run_poll(source_id: int):
    """Async wrapper for the scheduler."""
    await poll_source(source_id)
