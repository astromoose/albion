"""Scraper for Warhammer Community site (non-WordPress, custom CMS)."""

import json
import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from albion.scrapers.base import BaseScraper, ScrapedPost

log = logging.getLogger(__name__)

WHCOM_BASE = "https://www.warhammer-community.com"
WHCOM_HOME = f"{WHCOM_BASE}/en-gb/"


class WarhammerCommunityScraper(BaseScraper):
    """Scraper for warhammer-community.com which uses a custom CMS/Next.js."""

    async def discover_posts(self) -> list[ScrapedPost]:
        """Discover posts from the Warhammer Community homepage."""
        posts = []
        try:
            html = await self.fetch(WHCOM_HOME)
            soup = BeautifulSoup(html, "lxml")

            # Try to extract from Next.js __NEXT_DATA__ JSON
            next_data = soup.find("script", {"id": "__NEXT_DATA__"})
            if next_data:
                posts = self._parse_next_data(next_data.string)
                if posts:
                    return posts

            # Fallback: parse article links from homepage
            posts = self._parse_article_cards(soup)
        except Exception as exc:
            log.error("Failed to discover WarCom posts: %s", exc)
        return posts

    def _parse_next_data(self, json_str: str) -> list[ScrapedPost]:
        """Parse Next.js server-side data for articles."""
        posts = []
        try:
            data = json.loads(json_str)
            # Navigate the Next.js page props structure
            page_props = data.get("props", {}).get("pageProps", {})
            articles = (
                page_props.get("articles")
                or page_props.get("posts")
                or page_props.get("content", [])
            )
            if isinstance(articles, dict):
                articles = articles.get("items", [])

            for article in articles[:20]:
                title = article.get("title", "Untitled")
                slug = article.get("slug", "")
                url = f"{WHCOM_BASE}/en-gb/{slug}" if slug else ""
                thumbnail = article.get("image", {}).get("url") if isinstance(
                    article.get("image"), dict
                ) else article.get("image", article.get("thumbnail"))
                pub_date = self._parse_date(article.get("date") or article.get("publishedAt"))
                excerpt = article.get("excerpt", article.get("description", ""))

                if url:
                    posts.append(ScrapedPost(
                        title=title,
                        url=url,
                        published_at=pub_date,
                        thumbnail=thumbnail,
                        excerpt=excerpt[:300] if excerpt else None,
                    ))
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            log.warning("Failed to parse __NEXT_DATA__: %s", exc)
        return posts

    def _parse_article_cards(self, soup: BeautifulSoup) -> list[ScrapedPost]:
        """Parse article links from homepage HTML."""
        posts = []
        seen_urls = set()

        # Find all links to /en-gb/articles/ pages
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "/en-gb/articles/" not in href:
                continue

            url = href if href.startswith("http") else WHCOM_BASE + href
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Walk up to find the containing card/element for title and image
            parent = a_tag
            for _ in range(5):
                if parent.parent and parent.parent.name not in ("body", "html", "[document]"):
                    parent = parent.parent
                else:
                    break

            # Title: prefer the link's own text, then slug from URL
            title = a_tag.get_text(strip=True)
            # If the link text is a generic section header, derive from URL slug
            if not title or len(title) < 10 or title.endswith(":"):
                slug = url.rstrip("/").rsplit("/", 1)[-1]
                title = slug.replace("-", " ").title()
            if not title or len(title) < 5:
                continue

            # Thumbnail
            img = parent.find("img")
            thumbnail = None
            if img:
                thumbnail = img.get("src") or img.get("data-src")

            posts.append(ScrapedPost(
                title=title,
                url=url,
                thumbnail=thumbnail,
            ))
        return posts

    async def scrape_post(self, url: str) -> ScrapedPost:
        """Scrape a single Warhammer Community article."""
        html = await self.fetch(url)
        soup = BeautifulSoup(html, "lxml")

        subscriber_only = self.detect_subscriber_only(soup, url)

        title = self._extract_title(soup)
        published = self._extract_date_from_page(soup)
        thumbnail = self._extract_thumbnail(soup)
        content_html = self._extract_content(soup)
        content_md = self.html_to_markdown(content_html)

        return ScrapedPost(
            title=title,
            url=url,
            published_at=published,
            content_html=content_html,
            thumbnail=thumbnail,
            excerpt=self._extract_excerpt(content_md),
            subscriber_only=subscriber_only,
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        for selector in ["h1", "article h1", ".article-title", "[class*='Title']"]:
            tag = soup.select_one(selector)
            if tag:
                text = tag.get_text(strip=True)
                if text:
                    return text
        title = soup.find("title")
        return title.get_text(strip=True).split("|")[0].strip() if title else "Untitled"

    def _extract_date_from_page(self, soup: BeautifulSoup) -> datetime | None:
        # Try structured data
        time_tag = soup.find("time", {"datetime": True})
        if time_tag:
            return self._parse_date(time_tag["datetime"])
        for prop in ["article:published_time", "datePublished"]:
            meta = soup.find("meta", {"property": prop}) or soup.find("meta", {"name": prop})
            if meta and meta.get("content"):
                return self._parse_date(meta["content"])
        # Try Next.js data
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script:
            try:
                data = json.loads(script.string)
                article = data.get("props", {}).get("pageProps", {}).get("article", {})
                return self._parse_date(article.get("date") or article.get("publishedAt"))
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        return None

    def _extract_thumbnail(self, soup: BeautifulSoup) -> str | None:
        og = soup.find("meta", {"property": "og:image"})
        if og and og.get("content"):
            return og["content"]
        hero = soup.select_one(
            '.hero-image img, .article-image img, [class*="HeroImage"] img, article img'
        )
        if hero:
            return hero.get("src") or hero.get("data-src")
        return None

    def _extract_content(self, soup: BeautifulSoup) -> str:
        for selector in [
            "article",
            ".article-content",
            ".post-content",
            '[class*="ArticleContent"]',
            '[class*="article-body"]',
            "main",
        ]:
            content = soup.select_one(selector)
            if content:
                for unwanted in content.select(
                    "nav, header, footer, .sidebar, .comments, .share, .social, "
                    ".related, script, style, .ad, .newsletter, [class*='Newsletter']"
                ):
                    unwanted.decompose()
                return str(content)
        return ""

    def _parse_date(self, date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            pass
        # Try common formats
        for fmt in ["%Y-%m-%dT%H:%M:%S", "%d %B %Y", "%B %d, %Y", "%Y-%m-%d"]:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None
