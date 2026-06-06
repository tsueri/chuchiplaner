"""Generate labeled training data for ingredient name cleaning.

Scrapes recipe sitemaps, extracts ingredient lines using the existing
RecipeScraper and IngredientLineParser, calls the DeepSeek API to produce
dirty→clean pairs, and saves them as JSONL. Flags ~5% for manual review.
"""

import json
import os
import random
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.services.scraper import RecipeScraper

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]

RECIPE_PATH_PATTERNS = ("/rezept/", "/rezepte/", "/recipe/")
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SITEMAP_URLS = [
    "https://www.swissmilk.ch/de/sitemap.xml",
    "https://www.bettybossi.ch/sitemap.xml",
]
FOOBY_RECIPE_URLS: list[str] = []
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = str(_REPO_ROOT / "backend/data/training_pairs.jsonl")
DEFAULT_REVIEW_PATH = str(_REPO_ROOT / "backend/data/training_pairs_review.jsonl")
DEFAULT_RECIPE_LIMIT = 100
MAX_LINES_PER_BATCH = 8


def fetch_sitemap_urls(sitemap_url: str) -> list[str]:
    """Fetch a sitemap XML and extract absolute recipe URLs.

    Parses the sitemap, finds all <url><loc> entries, filters to URLs
    whose path contains a recipe pattern, and resolves any relative URLs
    against the sitemap base.

    Args:
        sitemap_url: Full URL to a sitemap XML document.

    Returns:
        Absolute URLs of recipe pages extracted from the sitemap.

    Raises:
        httpx.HTTPStatusError: If the HTTP response is a 4xx or 5xx error.
        httpx.RequestError: On network-level failures.
    """
    with httpx.Client() as client:
        response = client.get(sitemap_url)
        response.raise_for_status()
        xml_text = response.text

    root = ET.fromstring(xml_text)
    loc_elements = root.findall(f".//{{{SITEMAP_NS}}}loc")

    recipe_urls: list[str] = []
    for loc in loc_elements:
        raw_url = (loc.text or "").strip()
        if not raw_url:
            continue
        resolved = urljoin(sitemap_url, raw_url)
        path = urlparse(resolved).path
        if any(pattern in path for pattern in RECIPE_PATH_PATTERNS):
            recipe_urls.append(resolved)

    return recipe_urls


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

REQUIRED_KEYS = frozenset({"dirty", "clean", "reasoning"})


def build_labeling_prompt(recipe_title: str, ingredient_lines: list[str]) -> str:
    """Build a structured prompt for the DeepSeek API to clean ingredient names.

    Produces a German-language prompt that asks the model to strip adjectives,
    preparation notes, parentheticals, embedded weights, and equipment items
    from raw ingredient lines, returning a JSON array of
    ``{"dirty": …, "clean": …, "reasoning": …}`` objects.

    Args:
        recipe_title: Title of the recipe (for context).
        ingredient_lines: Raw ingredient strings to clean.

    Returns:
        A prompt string ready to send to the DeepSeek chat API.
    """
    if not ingredient_lines:
        raise ValueError("ingredient_lines must not be empty")

    numbered_lines = "\n".join(
        f"{i}. {line}" for i, line in enumerate(ingredient_lines, start=1)
    )

    prompt = (
        f"Du bist ein Assistent, der Zutatenzeilen aus Rezepten bereinigt.\n"
        f"\n"
        f"Rezept: {recipe_title}\n"
        f"\n"
        f"Bereinige folgende Zutatenzeilen. Entferne:\n"
        f"- Adjektive und beschreibende Wörter (z. B. «grüne Spargeln» → «Spargeln»)\n"
        f"- Zubereitungshinweise nach Kommas (z. B. «fein gehackt», «in Scheiben»)\n"
        f"- Klammern und deren Inhalt\n"
        f"- Eingebettete Gewichts- oder Mengenangaben\n"
        f"- Ausrüstungsgegenstände\n"
        f"- Alternative Zutaten (behalte die primäre Zutat)\n"
        f"\n"
        f"Gib ausschliesslich ein JSON-Array im folgenden Format zurück "
        f"(kein Markdown, kein zusätzlicher Text):\n"
        f'[{{"dirty": "<Originalzeile>", "clean": "<bereinigter Zutatenname>", '
        f'"reasoning": "<kurze Erklärung>"}}]\n'
        f"\n"
        f"Zutatenzeilen:\n"
        f"{numbered_lines}"
    )
    return prompt


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json and ``` markdown fences from a string."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped[3:]
        newline_idx = stripped.find("\n")
        if newline_idx != -1:
            stripped = stripped[newline_idx + 1:]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def parse_deepseek_response(response_text: str) -> list[dict[str, str]]:
    """Parse the DeepSeek JSON response into labeled pairs.

    Strips markdown code fences, parses the remaining text as JSON,
    and validates that every element contains ``dirty``, ``clean``,
    and ``reasoning`` keys.

    Args:
        response_text: Raw response body from the DeepSeek API.

    Returns:
        A list of dicts, each with ``dirty``, ``clean``, ``reasoning``.

    Raises:
        ValueError: If the response is not valid JSON or if any element
            is missing required keys.
    """
    clean_text = _strip_markdown_fences(response_text)

    try:
        parsed: Any = json.loads(clean_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"DeepSeek response is not valid JSON: {exc}\n"
            f"Response text: {clean_text[:200]}"
        ) from exc

    if not isinstance(parsed, list):
        raise ValueError(
            "DeepSeek response must be a JSON array, got "
            f"{type(parsed).__name__}"
        )

    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            raise ValueError(
                f"Element at index {i} must be a JSON object, "
                f"got {type(item).__name__}"
            )
        missing = REQUIRED_KEYS - item.keys()
        if missing:
            raise ValueError(
                f"Element at index {i} missing required keys: "
                f"{', '.join(sorted(missing))}"
            )

    return parsed


# ---------------------------------------------------------------------------
# Review split
# ---------------------------------------------------------------------------


def split_review_pairs(
    pairs: list[dict[str, str]],
    review_fraction: float = 0.05,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Split labeled pairs into training and manual-review sets.

    Uses a fixed random seed for deterministic output across runs.

    Args:
        pairs: Labeled dirty→clean pairs to split.
        review_fraction: Fraction of pairs to reserve for review.

    Returns:
        A ``(training_pairs, review_pairs)`` tuple. Both are disjoint
        subsets of the input and together cover all input pairs.
    """
    if not pairs:
        return [], []

    rng = random.Random()
    review_count = max(1, round(len(pairs) * review_fraction))
    review_count = min(review_count, len(pairs))

    indices = rng.sample(range(len(pairs)), review_count)
    review_set = frozenset(indices)

    training = [p for i, p in enumerate(pairs) if i not in review_set]
    review = [pairs[i] for i in sorted(review_set)]

    return training, review


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def _collect_recipe_urls() -> list[str]:
    """Gather recipe URLs from all configured sources.

    Returns:
        Deduplicated list of absolute recipe URLs.
    """
    urls: list[str] = []
    seen: set[str] = set()

    for sitemap_url in SITEMAP_URLS:
        try:
            for url in fetch_sitemap_urls(sitemap_url):
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
        except Exception as exc:
            print(f"Warning: failed to fetch sitemap {sitemap_url}: {exc}")

    for url in FOOBY_RECIPE_URLS:
        if url not in seen:
            seen.add(url)
            urls.append(url)

    return urls


def generate_training_data(
    output_path: str,
    review_path: str,
    deepseek_api_key: str | None = None,
    recipe_limit: int = DEFAULT_RECIPE_LIMIT,
) -> int:
    """Run the full training data generation pipeline.

    1. Checks idempotency — skips if *output_path* already exists.
    2. Collects recipe URLs from configured sitemaps and fooby list.
    3. Randomly samples up to *recipe_limit* URLs (with a fixed seed
       for reproducibility).
    4. Scrapes each recipe and extracts ingredient lines.
    5. Batches ingredient lines and calls the DeepSeek API to produce
       dirty→clean labels.
    6. Writes labeled pairs to *output_path* as JSONL.
    7. Splits ~5% into *review_path* for manual inspection.

    Args:
        output_path: Path for the main training JSONL file.
        review_path: Path for the human-review JSONL file.
        deepseek_api_key: DeepSeek API key. If ``None``, falls back to
            the ``DEEPSEEK_API_KEY`` environment variable.
        recipe_limit: Maximum number of recipes to scrape (default 100).
            URLs are randomly sampled from all collected URLs.

    Returns:
        Total number of labeled pairs generated.

    Raises:
        RuntimeError: If the ``openai`` package is not installed or no
            API key is available.
    """
    # --- Idempotency guard ------------------------------------------------
    out = Path(output_path)
    if out.exists():
        print(
            f"Output file already exists ({output_path}), skipping."
        )
        return 0

    # --- Resolve API key --------------------------------------------------
    api_key = deepseek_api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DeepSeek API key is required. Set DEEPSEEK_API_KEY "
            "environment variable or pass --api-key."
        )

    # --- Collect URLs -----------------------------------------------------
    recipe_urls = _collect_recipe_urls()
    if not recipe_urls:
        print("No recipe URLs found. Aborting.")
        return 0

    print(f"Collected {len(recipe_urls)} recipe URLs.")

    # --- Randomly sample recipes --------------------------------------------
    if recipe_limit > 0 and len(recipe_urls) > recipe_limit:
        rng = random.Random()
        recipe_urls = rng.sample(recipe_urls, recipe_limit)
        print(f"Randomly sampled {len(recipe_urls)} recipes (limit={recipe_limit}).")

    # --- Scrape & label ---------------------------------------------------
    all_pairs: list[dict[str, str]] = []
    client = None

    for i, url in enumerate(recipe_urls):
        scraped = RecipeScraper.scrape(url)
        if scraped is None:
            print(f"  [{i + 1}/{len(recipe_urls)}] SKIP (no data): {url}")
            continue

        title = scraped.title or "Unbenanntes Rezept"
        lines = scraped.ingredients
        if not lines:
            print(f"  [{i + 1}/{len(recipe_urls)}] SKIP (no ingredients): {url}")
            continue

        # Lazily initialise DeepSeek client on first successful scrape
        if client is None:
            if OpenAI is None:
                raise RuntimeError(
                    "openai package is required. "
                    "Install with: pip install openai"
                )
            client = OpenAI(
                api_key=api_key, base_url="https://api.deepseek.com/v1"
            )

        domain = urlparse(url).netloc

        # Batch ingredient lines within this recipe
        for batch_start in range(0, len(lines), MAX_LINES_PER_BATCH):
            batch = lines[batch_start : batch_start + MAX_LINES_PER_BATCH]
            prompt = build_labeling_prompt(title, batch)

            try:
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                raw_content = response.choices[0].message.content
                if raw_content is None:
                    print(
                        f"  [{i + 1}/{len(recipe_urls)}] "
                        f"WARN: empty DeepSeek response for {url}"
                    )
                    continue
            except Exception as exc:
                print(
                    f"  [{i + 1}/{len(recipe_urls)}] "
                    f"WARN: DeepSeek API error for {url}: {exc}"
                )
                continue

            try:
                parsed = parse_deepseek_response(raw_content)
            except ValueError as exc:
                print(
                    f"  [{i + 1}/{len(recipe_urls)}] "
                    f"WARN: could not parse response for {url}: {exc}"
                )
                continue

            for pair in parsed:
                pair["recipe_url"] = url
                pair["source_domain"] = domain
                all_pairs.append(pair)

        progress = i + 1
        if progress % 10 == 0 or progress == len(recipe_urls):
            print(
                f"  [{progress}/{len(recipe_urls)}] "
                f"Done ({len(all_pairs)} pairs so far)"
            )

    if not all_pairs:
        print("No pairs generated from any recipe.")
        return 0

    # Write training output
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        for pair in all_pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")

    # --- Split review pairs -----------------------------------------------
    training_pairs, review_pairs = split_review_pairs(all_pairs)

    # Rewrite output file with training-only pairs
    with open(out, "w", encoding="utf-8") as fh:
        for pair in training_pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")

    # Write review file
    rev = Path(review_path)
    rev.parent.mkdir(parents=True, exist_ok=True)
    with open(rev, "w", encoding="utf-8") as fh:
        for pair in review_pairs:
            fh.write(json.dumps(pair, ensure_ascii=False) + "\n")

    print(
        f"Generated {len(all_pairs)} pairs: "
        f"{len(training_pairs)} training, {len(review_pairs)} review."
    )
    return len(all_pairs)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point: scrape, label, save."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate training data for ingredient NER"
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help="Path for training JSONL output",
    )
    parser.add_argument(
        "--review-output",
        default=DEFAULT_REVIEW_PATH,
        help="Path for review JSONL output",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("DEEPSEEK_API_KEY"),
        help="DeepSeek API key (defaults to DEEPSEEK_API_KEY env var)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_RECIPE_LIMIT,
        metavar="N",
        help=f"Max recipes to scrape (default: {DEFAULT_RECIPE_LIMIT})",
    )
    args = parser.parse_args()

    try:
        count = generate_training_data(
            args.output, args.review_output, args.api_key,
            recipe_limit=args.limit,
        )
        print(f"Generated {count} training pairs.")
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
