"""ALBION - Tabletop hobby blog aggregator/reader."""

import html
import logging
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from albion.config import CONTENT_DIR, STATIC_DIR, TEMPLATES_DIR


_RE_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_RE_MD_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_RE_HTML_TAG = re.compile(r"<[^>]+>")
_RE_MULTI_SPACE = re.compile(r"\s+")


def _strip_markup(text: str | None) -> str:
    """Strip markdown and HTML markup down to plain text."""
    if not text:
        return ""
    s = _RE_MD_IMG.sub("", text)           # remove images
    s = _RE_MD_LINK.sub(r"\1", s)          # [text](url) -> text
    s = _RE_HTML_TAG.sub("", s)            # strip HTML tags
    s = html.unescape(s)                   # &amp; -> &
    s = s.replace("**", "").replace("__", "")  # bold
    s = s.replace("*", "").replace("_", "")    # italic (standalone)
    s = _RE_MULTI_SPACE.sub(" ", s).strip()
    return s
from albion.database import init_db
from albion.routes.admin import router as admin_router
from albion.routes.reader import router as reader_router
from albion.scheduler import schedule_all_sources, scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    init_db()
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    schedule_all_sources()
    scheduler.start()
    logging.getLogger(__name__).info("ALBION started - scheduler running")
    yield
    scheduler.shutdown(wait=False)
    logging.getLogger(__name__).info("ALBION shutting down")


app = FastAPI(title="ALBION", lifespan=lifespan)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
app.state.templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.state.templates.env.filters["plaintext"] = _strip_markup

# Routes
app.include_router(reader_router)
app.include_router(admin_router)
