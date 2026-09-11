"""WordPress/RSS-based scraper for standard blog sites."""

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
from bs4 import BeautifulSoup

from albion.scrapers.base import BaseScraper, ScrapedPost

log = logging.getLogger(__name__)


class WordPressScraper(BaseScraper):
    """Scraper for WordPress blogs using RSS feeds with HTML fallback."""

    async def discover_posts(self) -> list[ScrapedPost]:
        """Discover posts via RSS feed."""
        if not self.feed_url:
            return await self._discover_from_html()

        try:
            raw = await self.fetch(self.feed_url)
        except RuntimeError:
            log.warning("RSS feed unavailable for %s, falling back to HTML", self.source_url)
            return await self._discover_from_html()

        feed = feedparser.parse(raw)
        posts = []
        for entry in feed.entries:
            published = self._parse_feed_date(entry)
            # Extract thumbnail from media content or enclosures
            thumbnail = self._extract_feed_thumbnail(entry)
            excerpt = entry.get("summary", "")
            if excerpt:
                excerpt = BeautifulSoup(excerpt, "lxml").get_text(separator=" ")[:300]

            posts.append(ScrapedPost(
                title=entry.get("title", "Untitled"),
                url=entry.get("link", ""),
                author=entry.get("author"),
                published_at=published,
                thumbnail=thumbnail,
                excerpt=excerpt,
                content_html=entry.get("content", [{}])[0].get("value", "")
                if entry.get("content") else "",
            ))
        return posts

    async def _discover_from_html(self) -> list[ScrapedPost]:
        """Fallback: discover posts by scraping the homepage."""
        html = await self.fetch(self.source_url)
        soup = BeautifulSoup(html, "lxml")
        posts = []

        # Common WordPress article selectors
        articles = (
            soup.select("article")
            or soup.select(".post")
            or soup.select(".entry")
            or soup.select(".blog-post")
        )

        for article in articles[:20]:
            link_tag = article.find("a", href=True)
            title_tag = article.find(["h1", "h2", "h3"])
            img_tag = article.find("img")

            if not link_tag:
                continue

            url = link_tag["href"]
            if not url.startswith("http"):
                url = self.source_url.rstrip("/") + "/" + url.lstrip("/")

            title = title_tag.get_text(strip=True) if title_tag else "Untitled"
            thumbnail = img_tag.get("src") or img_tag.get("data-src") if img_tag else None

            posts.append(ScrapedPost(
                title=title,
                url=url,
                thumbnail=thumbnail,
            ))
        return posts

    async def scrape_post(self, url: str) -> ScrapedPost:
        """Scrape full content of a single post page."""
        html = await self.fetch(url)
        soup = BeautifulSoup(html, "lxml")

        # Check subscriber-only
        subscriber_only = self.detect_subscriber_only(soup, url)

        title = self._extract_title(soup)
        author = self._extract_author(soup)
        published = self._extract_date(soup)
        thumbnail = self._extract_thumbnail(soup)
        content_html = self._extract_content(soup)
        content_md = self.html_to_markdown(content_html)

        return ScrapedPost(
            title=title,
            url=url,
            author=author,
            published_at=published,
            content_html=content_html,
            thumbnail=thumbnail,
            excerpt=self._extract_excerpt(content_md),
            subscriber_only=subscriber_only,
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        for selector in [".entry-title", ".post-title", "h1.title", "article h1", "h1"]:
            tag = soup.select_one(selector)
            if tag:
                return tag.get_text(strip=True)
        title_tag = soup.find("title")
        return title_tag.get_text(strip=True) if title_tag else "Untitled"

    def _extract_author(self, soup: BeautifulSoup) -> str | None:
        for selector in [".author", ".entry-author", ".post-author", '[rel="author"]']:
            tag = soup.select_one(selector)
            if tag:
                return tag.get_text(strip=True)
        return None

    def _extract_date(self, soup: BeautifulSoup) -> datetime | None:
        # Try time/datetime elements
        time_tag = soup.find("time", {"datetime": True})
        if time_tag:
            try:
                return datetime.fromisoformat(time_tag["datetime"].replace("Z", "+00:00"))
            except ValueError:
                pass
        # Try meta tags
        for meta_name in ["article:published_time", "datePublished", "date"]:
            meta = soup.find("meta", {"property": meta_name}) or soup.find(
                "meta", {"name": meta_name}
            )
            if meta and meta.get("content"):
                try:
                    return datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
                except ValueError:
                    pass
        return None

    def _extract_thumbnail(self, soup: BeautifulSoup) -> str | None:
        og = soup.find("meta", {"property": "og:image"})
        if og and og.get("content"):
            return og["content"]
        featured = soup.select_one(".wp-post-image, .featured-image img, .post-thumbnail img")
        if featured:
            return featured.get("src") or featured.get("data-src")
        return None

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Extract main article content HTML."""
        # Try common WordPress content containers
        for selector in [
            ".entry-content",
            ".post-content",
            ".td-post-content",
            ".article-content",
            "article .content",
            ".post-body",
            "article",
            ".hentry",
            ".type-post",
        ]:
            content = soup.select_one(selector)
            if content:
                # Remove nav, sidebar, comments, sharing widgets
                for unwanted in content.select(
                    "nav, .sidebar, .comments, .share, .social, .related-posts, "
                    ".post-navigation, .author-bio, script, style, .ad, .advertisement, "
                    ".content-sidebar, .tagcloud"
                ):
                    unwanted.decompose()
                return str(content)
        return ""

    def _parse_feed_date(self, entry) -> datetime | None:
        for field in ["published", "updated"]:
            raw = entry.get(field)
            if raw:
                try:
                    return parsedate_to_datetime(raw).replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    try:
                        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
                    except ValueError:
                        pass
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        return None

    def _extract_feed_thumbnail(self, entry) -> str | None:
        # Media content
        media = entry.get("media_content", [])
        for m in media:
            if m.get("url"):
                return m["url"]
        # Media thumbnail
        thumb = entry.get("media_thumbnail", [])
        for t in thumb:
            if t.get("url"):
                return t["url"]
        # Enclosures
        for enc in entry.get("enclosures", []):
            if enc.get("type", "").startswith("image"):
                return enc.get("href") or enc.get("url")
        # Parse from summary HTML
        summary = entry.get("summary", "")
        if summary:
            soup = BeautifulSoup(summary, "lxml")
            img = soup.find("img")
            if img:
                return img.get("src")
        return None
