import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("chuchiplaner")


def model_available(model_dir: str) -> bool:
    path = Path(model_dir)
    return path.is_dir() and (path / "config.json").exists()


def _import_torch() -> Any:
    try:
        import torch

        return torch
    except ImportError:
        raise RuntimeError(
            "PyTorch is required for NER model inference. "
            "Install with: pip install torch"
        )


def _import_transformers() -> Any:
    try:
        import transformers

        return transformers
    except ImportError:
        raise RuntimeError(
            "transformers is required for NER model inference. "
            "Install with: pip install transformers"
        )


def _load_model(model_dir: str) -> tuple[Any, Any]:
    """Load tokenizer and model from model_dir. Raises on failure."""
    transformers = _import_transformers()
    tokenizer = transformers.AutoTokenizer.from_pretrained(model_dir)
    model = transformers.AutoModelForTokenClassification.from_pretrained(model_dir)
    model.eval()
    return tokenizer, model


class IngredientNameCleaner:
    def __init__(
        self,
        model: Any = None,
        tokenizer: Any = None,
        model_dir: str = "backend/models/ingredient_ner",
    ) -> None:
        self._model_dir = model_dir
        if model is not None and tokenizer is not None:
            self._model = model
            self._tokenizer = tokenizer
        else:
            self._tokenizer, self._model = _load_model(model_dir)

    def clean(self, name: str) -> str:
        if not name:
            return ""

        torch = _import_torch()

        try:
            encoding = self._tokenizer(
                name,
                return_tensors="pt",
                return_offsets_mapping=True,
            )
            offsets = encoding.pop("offset_mapping")

            with torch.no_grad():
                outputs = self._model(**encoding)

            predictions = torch.argmax(outputs.logits, dim=2)[0]

            kept_ranges: list[tuple[int, int]] = []
            for i, (start, end) in enumerate(offsets[0]):
                s, e = start.item(), end.item()
                if s == e:
                    continue
                label_id = predictions[i].item()
                label = self._model.config.id2label[label_id]
                if label in ("B-ING", "I-ING"):
                    kept_ranges.append((s, e))

            if not kept_ranges:
                return name

            pieces: list[str] = []
            last_end = -1
            for s, e in kept_ranges:
                if last_end >= 0 and s > last_end:
                    pieces.append(name[last_end:s])
                pieces.append(name[s:e])
                last_end = e
            return "".join(pieces)

        except Exception:
            logger.exception("NER inference failed for ingredient name %r", name)
            return name
