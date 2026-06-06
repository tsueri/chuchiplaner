from unittest.mock import MagicMock

import pytest

from app.services.ingredient_name_cleaner import (
    IngredientNameCleaner,
    model_available,
)

pytest.importorskip("torch")


class _MockTokenizer:
    def __init__(self) -> None:
        pass

    def __call__(
        self,
        text: str,
        return_tensors: str = "pt",
        return_offsets_mapping: bool = False,
    ):  # type: ignore[no-untyped-def]
        import torch

        offsets_list: list[tuple[int, int]] = []
        input_ids = []
        for i, _ch in enumerate(text):
            input_ids.append(i + 1)
            offsets_list.append((i, i + 1))

        # Add CLS at start, SEP at end for offset mapping
        full_offsets = [(0, 0)] + offsets_list + [(0, 0)]
        full_input_ids = [101] + input_ids + [102]

        result = {
            "input_ids": torch.tensor([full_input_ids]),
            "attention_mask": torch.ones(1, len(full_input_ids), dtype=torch.long),
            "offset_mapping": torch.tensor([full_offsets]),
        }
        return result


class TestIngredientNameCleaner:
    def test_clean_strips_non_ingredient_tokens(self) -> None:
        """AC: clean('grüne Spargeln, in Stücken') returns 'Spargeln'"""
        tokenizer = _MockTokenizer()

        # Configure model to mark 'Spargeln' as ingredient (positions 7-13)
        # "grüne Spargeln, in Stücken"
        #  0123456789...
        #  grüne = O, " " = O, Spargeln = B-ING/I-ING, rest = O
        def predict(input_ids, attention_mask):  # type: ignore[no-untyped-def]
            import torch

            seq_len = input_ids.shape[1]
            labels = torch.zeros(1, seq_len, 3)
            labels[:, :, 0] = 1.0  # all O by default

            text = "grüne Spargeln, in Stücken"
            # Mark "Spargeln" chars as B-ING / I-ING
            spargeln_start = text.index("Spargeln")  # 6
            spargeln_end = spargeln_start + len("Spargeln")  # 14
            # Token indices: CLS=0, then char 0→token 1, char 1→token 2, etc.
            for i in range(spargeln_start, spargeln_end):
                token_idx = i + 1  # +1 for CLS
                if token_idx < seq_len:
                    labels[0, token_idx, 0] = 0.0  # not O
                    if i == spargeln_start:
                        labels[0, token_idx, 1] = 1.0  # B-ING
                    else:
                        labels[0, token_idx, 2] = 1.0  # I-ING

            class _Output:
                def __init__(self, logits):  # type: ignore[no-untyped-def]
                    self.logits = logits

            return _Output(labels)

        model = MagicMock()
        model.config.id2label = {0: "O", 1: "B-ING", 2: "I-ING"}
        model.config.label2id = {"O": 0, "B-ING": 1, "I-ING": 2}
        model.side_effect = predict
        model.eval.return_value = model

        cleaner = IngredientNameCleaner(model=model, tokenizer=tokenizer)
        result = cleaner.clean("grüne Spargeln, in Stücken")
        assert result == "Spargeln"

    def test_clean_returns_ingredient_name_gehackter_peterli(self) -> None:
        """AC: clean('gehackter Peterli') returns 'Peterli'"""
        tokenizer = _MockTokenizer()

        def predict(input_ids, attention_mask):  # type: ignore[no-untyped-def]
            import torch

            seq_len = input_ids.shape[1]
            labels = torch.zeros(1, seq_len, 3)
            labels[:, :, 0] = 1.0  # all O by default

            text = "gehackter Peterli"
            peterli_start = text.index("Peterli")  # 10
            peterli_end = peterli_start + len("Peterli")  # 17
            for i in range(peterli_start, peterli_end):
                token_idx = i + 1  # +1 for CLS
                if token_idx < seq_len:
                    labels[0, token_idx, 0] = 0.0
                    if i == peterli_start:
                        labels[0, token_idx, 1] = 1.0  # B-ING
                    else:
                        labels[0, token_idx, 2] = 1.0  # I-ING

            class _Output:
                def __init__(self, logits):  # type: ignore[no-untyped-def]
                    self.logits = logits

            return _Output(labels)

        model = MagicMock()
        model.config.id2label = {0: "O", 1: "B-ING", 2: "I-ING"}
        model.config.label2id = {"O": 0, "B-ING": 1, "I-ING": 2}
        model.side_effect = predict
        model.eval.return_value = model

        cleaner = IngredientNameCleaner(model=model, tokenizer=tokenizer)
        result = cleaner.clean("gehackter Peterli")
        assert result == "Peterli"

    def test_clean_returns_original_when_no_ingredient_tokens(self) -> None:
        tokenizer = _MockTokenizer()

        def predict(input_ids, attention_mask):  # type: ignore[no-untyped-def]
            import torch

            seq_len = input_ids.shape[1]
            labels = torch.zeros(1, seq_len, 3)
            labels[:, :, 0] = 1.0  # all O

            class _Output:
                def __init__(self, logits):  # type: ignore[no-untyped-def]
                    self.logits = logits

            return _Output(labels)

        model = MagicMock()
        model.config.id2label = {0: "O", 1: "B-ING", 2: "I-ING"}
        model.config.label2id = {"O": 0, "B-ING": 1, "I-ING": 2}
        model.side_effect = predict
        model.eval.return_value = model

        cleaner = IngredientNameCleaner(model=model, tokenizer=tokenizer)
        result = cleaner.clean("irgendein text")
        assert result == "irgendein text"

    def test_clean_returns_original_on_inference_error(self) -> None:
        model = MagicMock()
        model.config.id2label = {0: "O", 1: "B-ING", 2: "I-ING"}
        model.side_effect = RuntimeError("inference failed")
        model.eval.return_value = model

        tokenizer = _MockTokenizer()

        cleaner = IngredientNameCleaner(model=model, tokenizer=tokenizer)
        result = cleaner.clean("Spargeln")
        assert result == "Spargeln"

    def test_clean_preserves_ingredient_name_across_spans(self) -> None:
        """Test that multiple ingredient spans are concatenated."""
        tokenizer = _MockTokenizer()

        def predict(input_ids, attention_mask):  # type: ignore[no-untyped-def]
            import torch

            seq_len = input_ids.shape[1]
            labels = torch.zeros(1, seq_len, 3)
            labels[:, :, 0] = 1.0

            text = "Poulet Schenkel"
            # Mark "Poulet" and "Schenkel" as ingredient
            for i in range(0, len(text)):
                token_idx = i + 1
                if token_idx < seq_len and text[i] != " ":  # skip space
                    labels[0, token_idx, 0] = 0.0
                    if i == 0:
                        labels[0, token_idx, 1] = 1.0  # B-ING
                    else:
                        labels[0, token_idx, 2] = 1.0  # I-ING

            class _Output:
                def __init__(self, logits):  # type: ignore[no-untyped-def]
                    self.logits = logits

            return _Output(labels)

        model = MagicMock()
        model.config.id2label = {0: "O", 1: "B-ING", 2: "I-ING"}
        model.config.label2id = {"O": 0, "B-ING": 1, "I-ING": 2}
        model.side_effect = predict
        model.eval.return_value = model

        cleaner = IngredientNameCleaner(model=model, tokenizer=tokenizer)
        result = cleaner.clean("Poulet Schenkel")
        assert result == "Poulet Schenkel"  # spaces preserved between kept spans

    def test_empty_input_returns_empty(self) -> None:
        tokenizer = _MockTokenizer()
        model = MagicMock()
        model.config.id2label = {0: "O", 1: "B-ING", 2: "I-ING"}
        model.eval.return_value = model

        def predict(input_ids, attention_mask):  # type: ignore[no-untyped-def]
            import torch

            seq_len = input_ids.shape[1]
            labels = torch.zeros(1, seq_len, 3)
            labels[:, :, 0] = 1.0

            class _Output:
                def __init__(self, logits):  # type: ignore[no-untyped-def]
                    self.logits = logits

            return _Output(labels)

        model.side_effect = predict

        cleaner = IngredientNameCleaner(model=model, tokenizer=tokenizer)
        result = cleaner.clean("")
        assert result == ""


class TestModelAvailable:
    def test_model_available_true_when_config_exists(self, tmp_path) -> None:
        model_dir = tmp_path / "ingredient_ner"
        model_dir.mkdir()
        (model_dir / "config.json").write_text("{}")
        assert model_available(str(model_dir)) is True

    def test_model_available_false_when_no_config(self, tmp_path) -> None:
        model_dir = tmp_path / "ingredient_ner"
        model_dir.mkdir()
        assert model_available(str(model_dir)) is False

    def test_model_available_false_when_dir_missing(self, tmp_path) -> None:
        assert model_available("/nonexistent/path") is False
