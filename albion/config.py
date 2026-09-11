"""Application configuration."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = BASE_DIR / "content"
DB_PATH = BASE_DIR / "albion.db"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

DEFAULT_POLL_INTERVAL_MINUTES = 60
MAX_RETRIES = 3
RETRY_TIMEOUT_SECONDS = 300  # 5 minutes

NTFY_TOPIC = "albion-posts"
NTFY_SERVER = "https://ntfy.sh"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
