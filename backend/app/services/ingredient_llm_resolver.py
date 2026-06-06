from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

from app.schemas.recipe import ScrapedIngredientItem

logger = logging.getLogger("chuchiplaner")

EQUIPMENT_DENYLIST: set[str] = {
    "backpapier",
    "backform",
    "backblech",
    "blech",
    "pfanne",
    "kochtopf",
    "topf",
    "schüssel",
    "schuessel",
    "schale",
    "form",
    "folie",
    "deckel",
    "sieb",
    "tuch",
    "teller",
    "gabel",
    "löffel",
    "loffel",
    "messer",
    "becher",
    "glas",
}

_equipment_alternation = "|".join(
    re.escape(w) for w in sorted(EQUIPMENT_DENYLIST, key=len, reverse=True)
)
_CRITICAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\boder\b", re.IGNORECASE),
    re.compile(r"[àa]\s*\d"),
    re.compile(r"\b(" + _equipment_alternation + r")\b", re.IGNORECASE),
    re.compile(
        r"\b(eins?|einen?|einem?|zwei|drei|vier|fünf|fuenf"
        r"|sechs|sieben|acht|neun|zehn)\b",
        re.IGNORECASE,
    ),
]

_LLM_PROMPT_TEMPLATE = """\
Parsing-Hilfe für Kochzutaten. Analysiere jede Zeile und gib ein JSON-Array \
mit einem Objekt pro Zeile zurück.

Verfügbare Zutaten (Name → ID):
{ingredients_list}

Zutatenzeilen:
{raw_lines}

Gib NUR gültiges JSON zurück, kein Markdown. Format pro Zeile:
{{
  "cleaned_name": "Zutat ohne Mengen/Einheiten/Zubereitung",
  "corrected_quantity": <Zahl oder null>,
  "corrected_unit": "Einheit oder null",
  "ingredient_id": <ID aus der Liste oder null>,
  "confidence": <0.0-1.0>,
  "is_equipment": <true/false>,
  "suggested_ingredient_name": "Zutatenname falls keine ID gefunden oder null"
}}

Regeln:
- "oder" = Alternativen, wähle die wahrscheinlichste Zutat.
- "à" / "a" nach Mengenangabe = "pro Stück", interpretiere Menge.
- "ein", "zwei", etc. = meist "etwas" oder Teil der Beschreibung.
- Küchenutensilien (Backpapier, Pfanne, ...) = is_equipment: true.
"""


def is_critical_line(raw: str) -> bool:
    """Check whether a raw ingredient line matches critical Tier 2 patterns."""
    for pattern in _CRITICAL_PATTERNS:
        if pattern.search(raw):
            return True
    return False


def _build_prompt(
    raw_lines: list[str],
    ingredients: dict[str, int],
) -> str:
    ingredients_list = "\n".join(
        f"  {name} → {iid}" for name, iid in sorted(ingredients.items())
    )
    if not ingredients_list:
        ingredients_list = "  (keine)"
    raw_lines_text = "\n".join(f"  [{i}] {line}" for i, line in enumerate(raw_lines))
    return _LLM_PROMPT_TEMPLATE.format(
        ingredients_list=ingredients_list,
        raw_lines=raw_lines_text,
    )


def _parse_llm_response(raw_text: str, item_count: int) -> list[dict[str, Any]]:
    """Parse the LLM JSON response, returning one dict per item.

    Returns empty dicts for unparseable responses so callers always get
    item_count entries.
    """
    empty: list[dict[str, Any]] = [{}] * item_count

    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return empty

    if isinstance(parsed, list):
        result: list[dict[str, Any]] = []
        for item in parsed:
            if isinstance(item, dict):
                result.append(item)
            else:
                result.append({})
        while len(result) < item_count:
            result.append({})
        return result[:item_count]

    return empty


class IngredientLLMResolver:
    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        model: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self._timeout = timeout

    def resolve_batch(
        self,
        items: list[ScrapedIngredientItem],
        ingredients: dict[str, int],
    ) -> list[dict[str, Any]]:
        """Send a batch of hard lines to the Ollama LLM for resolution.

        Returns one dict per input item with keys matching the Tier 2
        schema fields.  On any error, returns dicts with ``confidence=0``
        so the pipeline degrades gracefully.
        """
        if not items:
            return []

        raw_lines = [item.raw for item in items]
        prompt = _build_prompt(raw_lines, ingredients)

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": self._model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                    },
                )
                response.raise_for_status()
                data = response.json()
                raw_text: str = data.get("response", "")
        except Exception:
            logger.exception("LLM resolver request failed")
            return [{} for _ in items]

        parsed = _parse_llm_response(raw_text, len(items))
        return parsed

    @staticmethod
    def needs_tier2(item: ScrapedIngredientItem) -> bool:
        """Determine whether an item should be routed to Tier 2.

        Routes lines that match critical regex patterns or have
        low Tier 1 confidence with no resolved ingredient.
        """
        if is_critical_line(item.raw):
            return True
        if item.confidence < 0.7 and item.ingredient_id is None:
            return True
        return False

    @staticmethod
    def apply_tier2_result(
        item: ScrapedIngredientItem,
        result: dict[str, Any],
    ) -> ScrapedIngredientItem:
        """Merge Tier 2 LLM result into a ScrapedIngredientItem.

        Only overrides fields with non-None / truthy values from the LLM.
        """
        if not result:
            return item

        cleaned = result.get("cleaned_name")
        if cleaned and isinstance(cleaned, str):
            item.tier2_cleaned_name = cleaned

        qty = result.get("corrected_quantity")
        if qty is not None:
            try:
                item.corrected_quantity = float(qty)
            except (TypeError, ValueError):
                pass

        unit = result.get("corrected_unit")
        if unit and isinstance(unit, str):
            item.corrected_unit = unit

        ing_id = result.get("ingredient_id")
        if ing_id is not None:
            try:
                item.ingredient_id = int(ing_id)
            except (TypeError, ValueError):
                pass

        conf = result.get("confidence")
        if conf is not None:
            try:
                item.confidence = float(conf)
            except (TypeError, ValueError):
                pass

        is_eq = result.get("is_equipment")
        if isinstance(is_eq, bool):
            item.is_equipment = is_eq
        elif isinstance(is_eq, str):
            item.is_equipment = is_eq.lower() in ("true", "yes", "1")

        suggested = result.get("suggested_ingredient_name")
        if suggested and isinstance(suggested, str):
            item.suggested_ingredient_name = suggested

        return item
