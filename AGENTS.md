# ALBION - Project Notes

## Run
```bash
source .venv/bin/activate
python -m uvicorn albion.main:app --port 8420 --reload
```

## Test
```bash
source .venv/bin/activate
pytest
```

## Architecture
- Python 3.11+ / FastAPI / SQLAlchemy / SQLite
- Scrapers in `albion/scrapers/` - add new scraper types by subclassing `BaseScraper`
- Templates in `templates/` using Jinja2 + HTMX
- Scraped content stored as markdown in `content/<domain>/<year>/<month>/<day>/<slug>.md`
- Polling via APScheduler with configurable per-source intervals
- Notifications via ntfy.sh (topic: `albion-posts`)
