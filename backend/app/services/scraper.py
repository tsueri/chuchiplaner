import threading
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
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
    is_partial: bool = False


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.og_image: str | None = None
        self._in_title = False
        self._title_data = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            attr_map = {k: v for k, v in attrs if v is not None}
            if attr_map.get("property") == "og:image":
                self.og_image = attr_map.get("content")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_data += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            self.title = self._title_data.strip() or None


class RecipeScraper:
    _cache: dict[str, ScrapedRecipe | None] = {}
    _last_request_time: float = 0.0
    _lock = threading.Lock()
    _rate_limit_seconds: float = 2.0

    _http_headers: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    }

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
            return cls._partial_scrape(url)

        try:
            title = scraper.title()  # type: ignore[no-untyped-call]
            ingredients = scraper.ingredients()  # type: ignore[no-untyped-call]
            instructions = scraper.instructions()
            image_url = scraper.image()  # type: ignore[no-untyped-call]
            yields = scraper.yields()  # type: ignore[no-untyped-call]
        except Exception:
            return None

        servings = cls._parse_servings(yields)

        domain = urlparse(url).netloc

        return ScrapedRecipe(
            title=title,
            ingredients=ingredients,
            instructions=instructions,
            image_url=image_url,
            servings=servings,
            source_url=url,
            source_domain=domain,
            is_partial=False,
        )

    @classmethod
    def _partial_scrape(cls, url: str) -> ScrapedRecipe | None:
        try:
            with httpx.Client(
                timeout=10.0,
                headers=cls._http_headers,
                follow_redirects=True,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                html = response.text
        except Exception:
            return None

        parser = _MetaParser()
        parser.feed(html)

        if not parser.title and not parser.og_image:
            return None

        domain = urlparse(url).netloc

        return ScrapedRecipe(
            title=parser.title or "",
            ingredients=[],
            instructions="",
            image_url=parser.og_image,
            servings=4,
            source_url=url,
            source_domain=domain,
            is_partial=True,
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
