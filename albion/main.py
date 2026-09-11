"""ALBION - Tabletop hobby blog aggregator/reader."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from albion.config import CONTENT_DIR, STATIC_DIR, TEMPLATES_DIR
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

# Routes
app.include_router(reader_router)
app.include_router(admin_router)
