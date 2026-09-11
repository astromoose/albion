"""Markdown file storage for scraped posts."""

import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from albion.config import CONTENT_DIR


def slugify(text: str, max_length: int = 60) -> str:
    """Convert text to a filesystem-safe slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text[:max_length].rstrip("-")


def domain_from_url(url: str) -> str:
    """Extract clean domain name from URL."""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    domain = domain.replace("www.", "")
    return domain


def build_post_path(
    source_url: str,
    title: str,
    published_at: datetime | None = None,
) -> Path:
    """Build path: <domain>/<year>/<month>/<day>/<short-title>.md"""
    domain = domain_from_url(source_url)
    dt = published_at or datetime.now()
    slug = slugify(title)
    return Path(domain) / str(dt.year) / f"{dt.month:02d}" / f"{dt.day:02d}" / f"{slug}.md"


def save_post_markdown(
    relative_path: Path,
    title: str,
    url: str,
    author: str | None,
    published_at: datetime | None,
    content_md: str,
    thumbnail: str | None = None,
) -> Path:
    """Save markdown content to disk. Returns the relative path."""
    full_path = CONTENT_DIR / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    frontmatter = [
        "---",
        f"title: \"{title}\"",
        f"url: {url}",
    ]
    if author:
        frontmatter.append(f"author: {author}")
    if published_at:
        frontmatter.append(f"date: {published_at.isoformat()}")
    if thumbnail:
        frontmatter.append(f"thumbnail: {thumbnail}")
    frontmatter.append("---")
    frontmatter.append("")

    header = "\n".join(frontmatter)
    full_path.write_text(f"{header}\n# {title}\n\n{content_md}", encoding="utf-8")
    return relative_path


def read_post_markdown(relative_path: Path) -> str | None:
    """Read markdown content from disk."""
    full_path = CONTENT_DIR / relative_path
    if full_path.exists():
        return full_path.read_text(encoding="utf-8")
    return None
