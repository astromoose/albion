"""Scraper registry and base classes."""

from albion.scrapers.base import BaseScraper, ScrapedPost
from albion.scrapers.warhammer_community import WarhammerCommunityScraper
from albion.scrapers.wordpress import WordPressScraper

SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "wordpress": WordPressScraper,
    "warhammer_community": WarhammerCommunityScraper,
}


def get_scraper(scraper_type: str) -> type[BaseScraper]:
    return SCRAPER_REGISTRY.get(scraper_type, WordPressScraper)


__all__ = ["BaseScraper", "ScrapedPost", "get_scraper", "SCRAPER_REGISTRY"]
