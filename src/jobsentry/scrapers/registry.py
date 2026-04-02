"""Scraper registry — discover and instantiate scrapers by name."""

from playwright.async_api import BrowserContext

from jobsentry.scrapers.base import BaseScraper

_SCRAPERS: dict[str, type[BaseScraper]] = {}


def register(name: str):
    """Decorator to register a scraper class."""

    def wrapper(cls: type[BaseScraper]):
        _SCRAPERS[name] = cls
        return cls

    return wrapper


def get_scraper(name: str, browser_context: BrowserContext) -> BaseScraper:
    if name not in _SCRAPERS:
        available = ", ".join(_SCRAPERS.keys()) or "none"
        raise ValueError(f"Unknown scraper '{name}'. Available: {available}")
    return _SCRAPERS[name](browser_context)


def get_all_scrapers(browser_context: BrowserContext) -> list[BaseScraper]:
    return [cls(browser_context) for cls in _SCRAPERS.values()]


def list_scrapers() -> list[str]:
    return list(_SCRAPERS.keys())
