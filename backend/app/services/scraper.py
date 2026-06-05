"""
Recipe scraper with SSRF hardening.

Deliberate constraints (do not relax):
- **Synchronous only.**  The module uses blocking ``time.sleep`` and a
  ``threading.Lock`` for rate-limiting.  An async HTTP client or custom
  resolver would break those guards and is therefore rejected.
- **Resolved‑IP + Host header.**  On every redirect hop we resolve the
  hostname once with ``socket.getaddrinfo``, pin the returned public IP
  before the actual HTTP request, and let ``httpx`` set the ``Host``
  header from the original URL.  This closes the DNS‑rebinding window
  between the security check and the outbound connection.
"""

import ipaddress
import json
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from recipe_scrapers import scrape_html


class SSRFBlockedError(Exception):
    pass


def validate_url_syntax(raw_url: str) -> str:
    parsed = urlparse(raw_url)

    if parsed.scheme not in ("http", "https"):
        raise SSRFBlockedError(f"Invalid scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFBlockedError("Missing hostname")

    if hostname == "localhost":
        raise SSRFBlockedError("localhost is not allowed")

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return parsed.geturl()

    if not _is_public_ip(ip):
        raise SSRFBlockedError(f"Non-public IP: {hostname}")

    return parsed.geturl()


def resolve_and_validate_host(hostname: str) -> str:
    addrinfo = socket.getaddrinfo(hostname, None)
    first_public_ip: str | None = None

    for family, _socktype, _proto, _canonname, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if not _is_public_ip(ip):
            raise SSRFBlockedError(f"Non-public IP: {ip_str}")
        if first_public_ip is None:
            first_public_ip = ip_str  # type: ignore[assignment]  # sockaddr[0] is str at runtime

    if first_public_ip is None:
        raise SSRFBlockedError("No public IP resolved for hostname")
    return first_public_ip


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


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
    description: str | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    total_time_minutes: int | None = None
    perform_time_minutes: int | None = None
    nutrients: dict[Any, Any] | None = None
    cuisine: str | None = None
    category: str | None = None
    keywords: str | None = None
    author: str | None = None
    date_published: date | None = None
    ratings: float | None = None
    suitable_for_diet: list[str] = field(default_factory=list)


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self.og_image: str | None = None
        self.og_description: str | None = None
        self._in_title = False
        self._title_data = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            attr_map = {k: v for k, v in attrs if v is not None}
            prop = attr_map.get("property")
            content = attr_map.get("content")
            if prop == "og:image":
                self.og_image = content
            elif prop == "og:description":
                self.og_description = content

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_data += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
            self.title = self._title_data.strip() or None


class _JsonLdRecipeParser:
    @staticmethod
    def extract(html: str) -> dict[str, Any] | None:
        pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
        for match in re.finditer(pattern, html, re.DOTALL):
            try:
                data = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            recipe = _JsonLdRecipeParser._find_recipe(data)
            if recipe:
                return _JsonLdRecipeParser._parse_recipe(recipe)
        return None

    @staticmethod
    def _find_recipe(data: Any) -> dict[str, Any] | None:
        if isinstance(data, dict):
            if _jsonld_is_type(data, "Recipe"):
                return data
            graph = data.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict) and _jsonld_is_type(item, "Recipe"):
                        return item
            return None
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and _jsonld_is_type(item, "Recipe"):
                    return item
        return None

    @staticmethod
    def _parse_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}

        result["title"] = recipe.get("name", "")
        result["description"] = recipe.get("description")
        result["keywords"] = recipe.get("keywords")
        result["author"] = _jsonld_extract_author(recipe.get("author"))

        date_pub = recipe.get("datePublished")
        if isinstance(date_pub, str):
            result["date_published"] = date_pub

        image = recipe.get("image")
        if isinstance(image, str):
            result["image_url"] = image
        elif isinstance(image, list) and image and isinstance(image[0], str):
            result["image_url"] = image[0]

        result["category"] = recipe.get("recipeCategory")
        result["cuisine"] = recipe.get("recipeCuisine")

        result["prep_time"] = recipe.get("prepTime")
        result["cook_time"] = recipe.get("cookTime")
        result["total_time"] = recipe.get("totalTime")

        yield_val = recipe.get("recipeYield")
        if isinstance(yield_val, list):
            yield_val = yield_val[0] if yield_val else None
        result["servings"] = yield_val

        ingredients = recipe.get("recipeIngredient", [])
        if isinstance(ingredients, list):
            result["ingredients"] = [str(i) for i in ingredients]
        else:
            result["ingredients"] = []

        instructions = recipe.get("recipeInstructions", [])
        if isinstance(instructions, list):
            steps: list[str] = []
            for step in instructions:
                if isinstance(step, dict):
                    steps.append(step.get("text", ""))
                elif isinstance(step, str):
                    steps.append(step)
            result["instructions"] = "\n".join(steps)
        elif isinstance(instructions, str):
            result["instructions"] = instructions
        else:
            result["instructions"] = ""

        result["nutrients"] = recipe.get("nutrition")

        sfd = recipe.get("suitableForDiet")
        if isinstance(sfd, str):
            sfd = [sfd]
        result["suitable_for_diet"] = sfd if isinstance(sfd, list) else []

        aggr = recipe.get("aggregateRating")
        if isinstance(aggr, dict):
            rating = aggr.get("ratingValue")
            if rating is not None:
                try:
                    result["ratings"] = float(rating)
                except (TypeError, ValueError):
                    pass

        return result


def _jsonld_is_type(data: dict[str, Any], type_name: str) -> bool:
    dt = data.get("@type")
    if isinstance(dt, str):
        return dt == type_name
    if isinstance(dt, list):
        return type_name in dt
    return False


def _jsonld_extract_author(author: Any) -> str | None:
    if isinstance(author, str):
        return author
    if isinstance(author, dict):
        return str(author.get("name", "")) or None
    if isinstance(author, list) and author:
        first = author[0]
        if isinstance(first, dict):
            return str(first.get("name", "")) or None
        if isinstance(first, str):
            return first
    return None


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

    @staticmethod
    def _fetch_url_safely(url: str, timeout: float = 10.0) -> httpx.Response:
        max_hops = 5
        hops = 0
        current_url = url

        with httpx.Client(
            timeout=timeout,
            headers=RecipeScraper._http_headers,
            follow_redirects=False,
        ) as client:
            while True:
                if hops > max_hops:
                    raise SSRFBlockedError("Max redirects exceeded")

                parsed = urlparse(current_url)
                hostname = parsed.hostname
                if not hostname:
                    raise SSRFBlockedError(f"Invalid hostname in URL: {current_url}")

                resolved_ip = resolve_and_validate_host(hostname)

                original_getaddrinfo = socket.getaddrinfo

                def _pinned_getaddrinfo(
                    host: str,
                    port: int | None,
                    family: int = 0,
                    typ: int = 0,
                    proto: int = 0,
                    flags: int = 0,
                ) -> list[tuple[Any, ...]]:
                    if host == hostname:
                        return [
                            (
                                socket.AF_INET,
                                socket.SOCK_STREAM,
                                6,
                                "",
                                (resolved_ip, port or 0),
                            )
                        ]
                    return original_getaddrinfo(
                        host, port, family, typ, proto, flags
                    )

                socket.getaddrinfo = _pinned_getaddrinfo  # type: ignore[assignment]
                try:
                    response = client.get(current_url)
                finally:
                    socket.getaddrinfo = original_getaddrinfo

                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if location:
                        current_url = urljoin(current_url, location)
                        hops += 1
                        continue

                return response

    @classmethod
    def scrape(cls, url: str) -> ScrapedRecipe | None:
        if url in cls._cache:
            return cls._cache[url]

        with cls._lock:
            elapsed = time.monotonic() - cls._last_request_time
            if elapsed < cls._rate_limit_seconds:
                time.sleep(cls._rate_limit_seconds - elapsed)

        result = cls._scrape_with_fetch(url)
        with cls._lock:
            cls._last_request_time = time.monotonic()

        cls._cache[url] = result
        return result

    @classmethod
    def _scrape_with_fetch(cls, url: str) -> ScrapedRecipe | None:
        try:
            response = cls._fetch_url_safely(url)
            html = response.text
        except SSRFBlockedError:
            raise
        except Exception:
            return None

        try:
            scraper = scrape_html(html, url)
        except Exception:
            return cls._extract_recipe_from_html(html, url)

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

        description = cls._safe_call(scraper, "description")
        prep_time = cls._safe_call(scraper, "prep_time")
        cook_time = cls._safe_call(scraper, "cook_time")
        total_time = cls._safe_call(scraper, "total_time")
        perform_time = cls._safe_call(scraper, "perform_time")
        nutrients = cls._safe_call(scraper, "nutrients")
        cuisine = cls._safe_call(scraper, "cuisine")
        category = cls._safe_call(scraper, "category")
        keywords = cls._safe_call(scraper, "keywords")
        if isinstance(keywords, list):
            keywords = ", ".join(keywords)
        author = cls._safe_call(scraper, "author")
        date_pub = cls._safe_call(scraper, "date_published")
        ratings_val = cls._safe_call(scraper, "ratings")
        sfd = cls._safe_call(scraper, "suitable_for_diet")

        from app.services.duration_serializer import DurationSerializer

        return ScrapedRecipe(
            title=title,
            ingredients=ingredients,
            instructions=instructions,
            image_url=image_url,
            servings=servings,
            source_url=url,
            source_domain=domain,
            is_partial=False,
            description=description,
            prep_time_minutes=DurationSerializer.from_iso_duration(prep_time),
            cook_time_minutes=DurationSerializer.from_iso_duration(cook_time),
            total_time_minutes=DurationSerializer.from_iso_duration(total_time),
            perform_time_minutes=DurationSerializer.from_iso_duration(perform_time),
            nutrients=nutrients,
            cuisine=cuisine,
            category=category,
            keywords=keywords,
            author=author,
            date_published=cls._parse_date(date_pub),
            ratings=ratings_val,
            suitable_for_diet=sfd if isinstance(sfd, list) else [],
        )

    @staticmethod
    def _safe_call(scraper: object, method_name: str) -> Any:
        try:
            method = getattr(scraper, method_name, None)
            if method is None:
                return None
            return method()
        except Exception:
            return None

    @classmethod
    def _extract_recipe_from_html(cls, html: str, url: str) -> ScrapedRecipe | None:
        parser = _MetaParser()
        parser.feed(html)

        jsonld = _JsonLdRecipeParser.extract(html)

        if jsonld:
            from app.services.duration_serializer import DurationSerializer

            domain = urlparse(url).netloc
            title = jsonld.get("title") or parser.title or ""
            image_url = (
                jsonld.get("image_url") or parser.og_image
            )
            description = (
                jsonld.get("description") or parser.og_description
            )
            servings_str = str(jsonld.get("servings", "4"))

            return ScrapedRecipe(
                title=str(title),
                ingredients=jsonld.get("ingredients", []),
                instructions=jsonld.get("instructions", ""),
                image_url=image_url,
                servings=cls._parse_servings(servings_str),
                source_url=url,
                source_domain=domain,
                is_partial=False,
                description=description,
                prep_time_minutes=DurationSerializer.from_iso_duration(
                    jsonld.get("prep_time")
                ),
                cook_time_minutes=DurationSerializer.from_iso_duration(
                    jsonld.get("cook_time")
                ),
                total_time_minutes=DurationSerializer.from_iso_duration(
                    jsonld.get("total_time")
                ),
                nutrients=jsonld.get("nutrients"),
                cuisine=jsonld.get("cuisine"),
                category=jsonld.get("category"),
                keywords=jsonld.get("keywords"),
                author=jsonld.get("author"),
                date_published=cls._parse_date(
                    jsonld.get("date_published")
                ),
                ratings=jsonld.get("ratings"),
                suitable_for_diet=jsonld.get("suitable_for_diet", []),
            )

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
            description=parser.og_description,
        )

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        if value is None:
            return None
        try:
            return date.fromisoformat(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_servings(yields: str) -> int:
        if not yields:
            return 4
        import re
        numbers = re.findall(r"\d+", yields)
        if numbers:
            return int(numbers[0])
        return 4
