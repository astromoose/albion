"""Base scraper with HTTP client, retries, and markdown conversion."""

import logging
from dataclasses import dataclass, field
from datetime import datetime

import html2text
import httpx
from bs4 import BeautifulSoup

from albion.config import MAX_RETRIES, RETRY_TIMEOUT_SECONDS, USER_AGENT

log = logging.getLogger(__name__)

SUBSCRIBER_KEYWORDS = [
    "subscriber-only",
    "subscribers only",
    "members only",
    "member-only",
    "premium content",
    "exclusive content",
    "locked",
    "paywall",
    "login to view",
    "sign in to read",
    "subscribe to read",
]


@dataclass
class ScrapedPost:
    title: str
    url: str
    author: str | None = None
    published_at: datetime | None = None
    content_html: str = ""
    thumbnail: str | None = None
    excerpt: str | None = None
    subscriber_only: bool = False
    tags: list[str] = field(default_factory=list)


class BaseScraper:
    """Base class all site scrapers inherit from."""

    def __init__(self, source_url: str, feed_url: str | None = None):
        self.source_url = source_url
        self.feed_url = feed_url
        self._converter = html2text.HTML2Text()
        self._converter.body_width = 0
        self._converter.ignore_links = False
        self._converter.ignore_images = False
        self._converter.protect_links = True
        self._converter.wrap_links = False

    async def fetch(self, url: str) -> str:
        """Fetch URL with retries. Falls back to curl_cffi for Cloudflare-protected sites."""
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(RETRY_TIMEOUT_SECONDS),
                    follow_redirects=True,
                    headers={"User-Agent": USER_AGENT},
                ) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    # Cloudflare sometimes returns 200/202 with empty body
                    if resp.text.strip():
                        return resp.text
                    raise httpx.HTTPStatusError(
                        "Empty response (likely Cloudflare)",
                        request=resp.request,
                        response=resp,
                    )
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                last_error = exc
                log.warning("Attempt %d/%d failed for %s: %s", attempt, MAX_RETRIES, url, exc)

        # Fallback: curl_cffi with browser TLS fingerprint
        log.info("Trying curl_cffi for Cloudflare bypass: %s", url)
        try:
            from curl_cffi import requests as cffi_requests

            resp = cffi_requests.get(
                url, impersonate="chrome", timeout=RETRY_TIMEOUT_SECONDS, allow_redirects=True,
            )
            resp.raise_for_status()
            if resp.text.strip():
                return resp.text
        except Exception as exc:
            log.warning("curl_cffi also failed for %s: %s", url, exc)

        raise RuntimeError(f"Failed to fetch {url} after {MAX_RETRIES} attempts: {last_error}")

    def html_to_markdown(self, html: str) -> str:
        """Convert HTML content to clean markdown."""
        return self._converter.handle(html).strip()

    def detect_subscriber_only(self, soup: BeautifulSoup, url: str = "") -> bool:
        """Check if a page is subscriber/member-only content."""
        text_lower = soup.get_text(separator=" ").lower()
        for keyword in SUBSCRIBER_KEYWORDS:
            if keyword in text_lower:
                return True
        # Check for common paywall CSS classes
        paywall_classes = ["paywall", "subscriber-wall", "members-only", "locked-content"]
        for cls in paywall_classes:
            if soup.find(class_=lambda c: c and cls in c):
                return True
        return False

    async def discover_posts(self) -> list[ScrapedPost]:
        """Discover recent posts from the source. Override in subclasses."""
        raise NotImplementedError

    async def scrape_post(self, url: str) -> ScrapedPost:
        """Scrape full content of a single post. Override in subclasses."""
        raise NotImplementedError

    def _extract_excerpt(self, markdown: str, max_length: int = 300) -> str:
        """Extract first paragraph as excerpt."""
        lines = [l for l in markdown.split("\n") if l.strip() and not l.startswith("#")]
        text = " ".join(lines)
        if len(text) > max_length:
            text = text[:max_length].rsplit(" ", 1)[0] + "..."
        return text
