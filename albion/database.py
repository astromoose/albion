"""Database models and session management."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

from albion.config import DB_PATH


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    url = Column(String(500), nullable=False, unique=True)
    feed_url = Column(String(500), nullable=True)
    scraper_type = Column(String(50), nullable=False, default="generic")
    poll_interval_minutes = Column(Integer, default=60)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    posts = relationship("Post", back_populates="source", cascade="all, delete-orphan")
    poll_logs = relationship("PollLog", back_populates="source", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False, unique=True)
    author = Column(String(200), nullable=True)
    published_at = Column(DateTime, nullable=True)
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    file_path = Column(String(1000), nullable=False)
    thumbnail = Column(String(1000), nullable=True)
    subscriber_only = Column(Boolean, default=False)
    excerpt = Column(Text, nullable=True)

    source = relationship("Source", back_populates="posts")


class PollLog(Base):
    __tablename__ = "poll_logs"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    status = Column(String(20), nullable=False)  # success, error, retry
    message = Column(Text, nullable=True)
    posts_found = Column(Integer, default=0)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    source = relationship("Source", back_populates="poll_logs")


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)


engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables and seed default sources."""
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        _seed_sources(db)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DEFAULT_SOURCES = [
    {
        "name": "Tabletop Battles",
        "url": "https://www.tabletopbattles.com",
        "feed_url": "https://www.tabletopbattles.com/feed/",
        "scraper_type": "wordpress",
    },
    {
        "name": "Chaosbunker",
        "url": "https://www.chaosbunker.de/en/",
        "feed_url": "https://www.chaosbunker.de/en/feed/",
        "scraper_type": "wordpress",
    },
    {
        "name": "Warhammer Community",
        "url": "https://www.warhammer-community.com/en-gb/",
        "feed_url": None,
        "scraper_type": "warhammer_community",
    },
    {
        "name": "Tale of Painters",
        "url": "https://taleofpainters.com",
        "feed_url": "https://taleofpainters.com/feed/",
        "scraper_type": "wordpress",
    },
    {
        "name": "Sprues and Brews",
        "url": "https://spruesandbrews.com",
        "feed_url": "https://spruesandbrews.com/feed/",
        "scraper_type": "wordpress",
    },
]


def _seed_sources(db: Session):
    if db.query(Source).count() > 0:
        return
    for src in DEFAULT_SOURCES:
        db.add(Source(**src))
    db.commit()
