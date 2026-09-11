# ALBION

Locally hosted web-based scraper/aggregator/reader for tabletop hobby blogs.

## Features

- **Multi-source scraping** - RSS feeds and HTML scraping for WordPress blogs and custom CMS sites
- **Markdown storage** - Posts saved as `<domain>/<year>/<month>/<day>/<short-title>.md` with frontmatter
- **Feed & grid views** - Toggle between scrollable feed and card grid layouts
- **Source filtering** - Filter posts by source
- **Dark/light mode** - Matches OS preference with manual toggle
- **Admin dashboard** - Add/remove sources, view poll logs and errors, trigger manual polls
- **Configurable polling** - Per-source intervals with 3x retry and 5-minute timeout
- **Subscriber-only filtering** - Detects and skips paywalled content
- **iOS notifications** - Push notifications via [ntfy.sh](https://ntfy.sh) for new posts

## Default Sources

| Site | Scraper |
|------|---------|
| [Tabletop Battles](https://www.tabletopbattles.com) | WordPress/RSS |
| [Chaosbunker](https://www.chaosbunker.de/en/) | WordPress/RSS |
| [Warhammer Community](https://www.warhammer-community.com/en-gb/) | Custom (HTML) |
| [Tale of Painters](https://taleofpainters.com) | WordPress/RSS |
| [Sprues and Brews](https://spruesandbrews.com) | WordPress/RSS |

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m uvicorn albion.main:app --port 8420
```

Open [http://localhost:8420](http://localhost:8420).

## iOS Notifications

1. Install [ntfy app](https://ntfy.sh) on iOS
2. Subscribe to topic `albion-posts` (or configure custom topic in `albion/config.py`)
3. New posts will push notifications to your device

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy, httpx, BeautifulSoup4, feedparser
- **Frontend**: Jinja2 templates, HTMX, vanilla CSS/JS
- **Storage**: SQLite (metadata), markdown files on disk (content)
- **Scheduling**: APScheduler (AsyncIO)
- **Notifications**: ntfy.sh
