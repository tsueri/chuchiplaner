import threading
import time
from dataclasses import dataclass

from recipe_scrapers import scrape_me


@dataclass
class ScrapedRecipe:
    title: str
    ingredients: list[str]
    instructions: str
    image_url: str | None = None
    servings: int = 4
    source_url: str = ""
    source_domain: str = ""


class RecipeScraper:
    _cache: dict[str, ScrapedRecipe | None] = {}
    _last_request_time: float = 0.0
    _lock = threading.Lock()
    _rate_limit_seconds: float = 2.0

    @classmethod
    def scrape(cls, url: str) -> ScrapedRecipe | None:
        if url in cls._cache:
            return cls._cache[url]

        with cls._lock:
            elapsed = time.monotonic() - cls._last_request_time
            if elapsed < cls._rate_limit_seconds:
                time.sleep(cls._rate_limit_seconds - elapsed)

        result = cls._do_scrape(url)
        with cls._lock:
            cls._last_request_time = time.monotonic()

        cls._cache[url] = result
        return result

    @classmethod
    def _do_scrape(cls, url: str) -> ScrapedRecipe | None:
        try:
            scraper = scrape_me(url)
        except Exception:
            return None

        try:
            title = scraper.title()  # type: ignore[no-untyped-call]
            ingredients = scraper.ingredients()  # type: ignore[no-untyped-call]
            instructions = scraper.instructions()
            image_url = scraper.image()  # type: ignore[no-untyped-call]
            yields = scraper.yields()  # type: ignore[no-untyped-call]
        except Exception:
            return None

        servings = cls._parse_servings(yields)

        from urllib.parse import urlparse
        domain = urlparse(url).netloc

        return ScrapedRecipe(
            title=title,
            ingredients=ingredients,
            instructions=instructions,
            image_url=image_url,
            servings=servings,
            source_url=url,
            source_domain=domain,
        )

    @staticmethod
    def _parse_servings(yields: str) -> int:
        if not yields:
            return 4
        import re
        numbers = re.findall(r"\d+", yields)
        if numbers:
            return int(numbers[0])
        return 4
