"""Tests for the fine-tuning script."""

import importlib
import tempfile
from pathlib import Path

import pytest


def test_import_succeeds() -> None:
    """The script module must be importable without errors."""
    importlib.import_module("scripts.fine_tune")


# --- load_training_data tests ---

def test_load_training_data_parses_jsonl() -> None:
    """load_training_data reads JSONL and returns list of dicts."""
    from scripts.fine_tune import load_training_data

    content = (
        '{"dirty": "a", "clean": "b", "reasoning": "c"}\n'
        '{"dirty": "d", "clean": "e", "reasoning": "f"}\n'
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        result = load_training_data(path)
        assert len(result) == 2
        assert result[0] == {"dirty": "a", "clean": "b", "reasoning": "c"}
        assert result[1] == {"dirty": "d", "clean": "e", "reasoning": "f"}
    finally:
        Path(path).unlink()


def test_load_training_data_empty_file() -> None:
    """load_training_data returns empty list for empty file."""
    from scripts.fine_tune import load_training_data

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        result = load_training_data(path)
        assert result == []
    finally:
        Path(path).unlink()


def test_load_training_data_file_not_found() -> None:
    """load_training_data raises FileNotFoundError for missing file."""
    from scripts.fine_tune import load_training_data

    with pytest.raises(FileNotFoundError):
        load_training_data("/nonexistent/path.jsonl")


def test_load_training_data_skips_empty_lines() -> None:
    """load_training_data skips blank lines."""
    from scripts.fine_tune import load_training_data

    content = (
        '{"dirty": "a", "clean": "b", "reasoning": "c"}\n'
        '\n'
        '{"dirty": "d", "clean": "e", "reasoning": "f"}\n'
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        result = load_training_data(path)
        assert len(result) == 2
    finally:
        Path(path).unlink()


# --- get_bio_labels tests ---

def test_get_bio_labels_simple_match() -> None:
    """get_bio_labels labels single-word ingredient correctly."""
    from scripts.fine_tune import get_bio_labels

    dirty = "600g Kalbfleisch"
    clean = "Kalbfleisch"
    # Tokenization: ["600", "g", "Kalbfleisch"] → spans: [(0,3), (3,4), (5,16)]
    spans = [(0, 3), (3, 4), (5, 16)]
    labels = get_bio_labels(dirty, clean, spans)
    assert labels == ["O", "O", "B-ING"]


def test_get_bio_labels_multi_word_ingredient() -> None:
    """get_bio_labels labels multi-word ingredient with B-ING and I-ING."""
    from scripts.fine_tune import get_bio_labels

    dirty = "1 Dose gehackte Tomaten, aus der Dose"
    clean = "gehackte Tomaten"
    # Tokens: ["1", "Dose", "gehackte", "Tomaten", ",", "aus", "der", "Dose"]
    spans = [(0, 1), (2, 6), (7, 15), (16, 23), (23, 24), (25, 28), (29, 32), (33, 37)]
    labels = get_bio_labels(dirty, clean, spans)
    assert labels == ["O", "O", "B-ING", "I-ING", "O", "O", "O", "O"]


def test_get_bio_labels_no_match() -> None:
    """get_bio_labels returns all O when clean name not found."""
    from scripts.fine_tune import get_bio_labels

    dirty = "Salz und Pfeffer"
    clean = "Zucker"
    spans = [(0, 4), (5, 8), (9, 16)]
    labels = get_bio_labels(dirty, clean, spans)
    assert labels == ["O", "O", "O"]


def test_get_bio_labels_case_insensitive() -> None:
    """get_bio_labels matches case-insensitively."""
    from scripts.fine_tune import get_bio_labels

    dirty = "2 EL Olivenöl"
    clean = "olivenöl"
    spans = [(0, 1), (2, 4), (5, 13)]
    labels = get_bio_labels(dirty, clean, spans)
    assert labels == ["O", "O", "B-ING"]


def test_get_bio_labels_clean_name_at_start() -> None:
    """get_bio_labels works when clean name is at the beginning."""
    from scripts.fine_tune import get_bio_labels

    dirty = "Petersilie, gehackt"
    clean = "Petersilie"
    spans = [(0, 10), (10, 11), (12, 19)]
    labels = get_bio_labels(dirty, clean, spans)
    assert labels == ["B-ING", "O", "O"]


def test_get_bio_labels_clean_name_at_end() -> None:
    """get_bio_labels works when clean name is at the end."""
    from scripts.fine_tune import get_bio_labels

    dirty = "etwas Olivenöl"
    clean = "Olivenöl"
    spans = [(0, 5), (6, 14)]
    labels = get_bio_labels(dirty, clean, spans)
    assert labels == ["O", "B-ING"]


# --- create_training_dataset tests ---


def test_create_training_dataset_basic() -> None:
    """create_training_dataset returns a Dataset with expected columns."""
    from unittest.mock import MagicMock, patch

    from scripts.fine_tune import create_training_dataset

    pairs = [
        {"dirty": "200g Tomaten", "clean": "Tomaten", "reasoning": "ok"},
        {"dirty": "1 Zwiebel, gehackt", "clean": "Zwiebel", "reasoning": "ok"},
    ]

    # Mock tokenizer
    mock_tokenizer = MagicMock()
    mock_tokenizer.return_value = {
        "input_ids": [[101, 200, 201, 102], [101, 300, 301, 302, 102]],
        "attention_mask": [[1, 1, 1, 1], [1, 1, 1, 1, 1]],
        "offset_mapping": [
            [(0, 0), (0, 4), (4, 11), (0, 0)],  # 200g Tomaten
            [(0, 0), (0, 1), (2, 9), (9, 10), (11, 18)],  # 1 Zwiebel, gehackt
        ],
    }

    label2id = {"O": 0, "B-ING": 1, "I-ING": 2}

    # Mock the optional Dataset import
    mock_dataset = MagicMock()
    mock_dataset.column_names = ["input_ids", "attention_mask", "labels"]
    mock_dataset.__len__.return_value = 2

    with patch("scripts.fine_tune.Dataset") as mock_ds_cls:
        mock_ds_cls.from_dict.return_value = mock_dataset
        dataset = create_training_dataset(pairs, mock_tokenizer, label2id)

    # Should have the expected columns
    assert "input_ids" in dataset.column_names
    assert "attention_mask" in dataset.column_names
    assert "labels" in dataset.column_names
    assert len(dataset) == 2


# --- fine_tune tests ---


def test_fine_tune_skips_if_model_exists(tmp_path: Path) -> None:
    """fine_tune warns and returns 0 if model directory exists (idempotent)."""
    from scripts.fine_tune import fine_tune

    # Create a dummy model directory
    model_dir = tmp_path / "ingredient_ner"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")

    # Create dummy training data
    data_file = tmp_path / "training.jsonl"
    data_file.write_text('{"dirty": "a", "clean": "b", "reasoning": "c"}\n')

    result = fine_tune(str(data_file), str(model_dir))
    assert result == 0


def test_fine_tune_full_pipeline(tmp_path: Path) -> None:
    """End-to-end fine_tune with mocked transformers."""
    import json
    from unittest.mock import MagicMock, patch

    from scripts.fine_tune import fine_tune

    # Create training data
    data_file = tmp_path / "training.jsonl"
    pairs = [
        {"dirty": "200g Tomaten, gehackt", "clean": "Tomaten", "reasoning": "ok"},
        {"dirty": "1 Zwiebel", "clean": "Zwiebel", "reasoning": "ok"},
        {"dirty": "Salz und Pfeffer", "clean": "Salz", "reasoning": "ok"},
    ]
    data_file.write_text("\n".join(json.dumps(p) for p in pairs))

    model_dir = tmp_path / "model"

    # Mock the entire transformer setup
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()

    def _mock_tokenize(texts: str | list[str], **kwargs: object) -> dict[str, object]:
        """Simulate a HuggingFace tokenizer returning batched outputs."""
        if isinstance(texts, str):
            texts = [texts]
        n = len(texts)
        # 5 tokens per sequence: [CLS, tok1, tok2, tok3, SEP]
        return {
            "input_ids": [[101, 200, 201, 202, 102] for _ in range(n)],
            "attention_mask": [[1, 1, 1, 1, 1] for _ in range(n)],
            "offset_mapping": [
                [(0, 0), (0, 4), (4, 8), (8, 12), (0, 0)]
                for _ in range(n)
            ],
        }

    mock_tokenizer.side_effect = _mock_tokenize
    mock_model.config.id2label = {0: "O", 1: "B-ING", 2: "I-ING"}
    mock_model.config.label2id = {"O": 0, "B-ING": 1, "I-ING": 2}

    # Mock Trainer
    mock_trainer = MagicMock()
    mock_trainer.train.return_value = None

    # Create mock classes with from_pretrained returning our mocks
    mock_tok_cls = MagicMock()
    mock_tok_cls.from_pretrained.return_value = mock_tokenizer
    mock_mod_cls = MagicMock()
    mock_mod_cls.from_pretrained.return_value = mock_model

    # Mock dataset: from_dict returns a dataset, train_test_split returns split
    mock_ds = MagicMock()
    mock_ds.train_test_split.return_value = {"train": mock_ds, "test": mock_ds}

    with patch("scripts.fine_tune.AutoTokenizer", mock_tok_cls):
        with patch("scripts.fine_tune.AutoModelForTokenClassification", mock_mod_cls):
            with patch("scripts.fine_tune.Trainer", return_value=mock_trainer):
                with patch("scripts.fine_tune.TrainingArguments"):
                    with patch("scripts.fine_tune.Dataset") as mock_ds_cls:
                        mock_ds_cls.from_dict.return_value = mock_ds
                        result = fine_tune(str(data_file), str(model_dir))

    assert result == 3  # 3 training examples
    mock_trainer.train.assert_called_once()
    mock_model.save_pretrained.assert_called_once_with(str(model_dir))
    mock_tokenizer.save_pretrained.assert_called_once_with(str(model_dir))
