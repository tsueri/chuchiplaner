"""Fine-tune a German NER model for ingredient name cleaning.

Loads labeled training data (JSONL), tokenizes with B-ING/I-ING/O labels,
trains distilbert-base-german-cased, and saves the model artifact.
"""

import json
import sys
from pathlib import Path
from typing import Any, NoReturn

_REPO_ROOT = Path(__file__).resolve().parents[2]

_ML_DEPS_MESSAGE = (
    "ML dependencies required. "
    "Install with: pip install transformers torch datasets"
)


def _import_ml_deps() -> tuple[Any, Any, Any, Any, Any]:
    """Import optional ML packages; exits with error if unavailable."""
    try:
        import torch  # noqa: F401 — required by transformers at runtime
        from datasets import Dataset
        from transformers import (
            AutoModelForTokenClassification,
            AutoTokenizer,
            Trainer,
            TrainingArguments,
        )

        return (
            AutoTokenizer,
            AutoModelForTokenClassification,
            Trainer,
            TrainingArguments,
            Dataset,
        )
    except ImportError:
        print(f"Error: {_ML_DEPS_MESSAGE}", file=sys.stderr)
        sys.exit(1)


(
    AutoTokenizer,
    AutoModelForTokenClassification,
    Trainer,
    TrainingArguments,
    Dataset,
) = _import_ml_deps()


def load_training_data(jsonl_path: str) -> list[dict[str, str]]:
    """Load labeled training data from a JSONL file.

    Args:
        jsonl_path: Path to the JSONL file.

    Returns:
        List of dicts with dirty, clean, reasoning keys.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"Training data not found: {jsonl_path}")

    pairs: list[dict[str, str]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            pairs.append(json.loads(line))
    return pairs


def get_bio_labels(
    dirty_text: str, clean_name: str, token_spans: list[tuple[int, int]]
) -> list[str]:
    """Map tokens to B-ING/I-ING/O labels via character-span alignment.

    Finds the character span of clean_name within dirty_text (case-insensitive),
    then labels tokens whose character spans overlap with the clean_name span as
    B-ING (first matching token) or I-ING (subsequent matching tokens). All
    other tokens are labeled O.

    Args:
        dirty_text: The full dirty ingredient line.
        clean_name: The cleaned ingredient name to find.
        token_spans: List of (start_char, end_char) for each token.

    Returns:
        List of BIO label strings, one per token span.
    """
    dirty_lower = dirty_text.lower()
    clean_lower = clean_name.lower()
    pos = dirty_lower.find(clean_lower)
    if pos == -1:
        return ["O"] * len(token_spans)

    clean_start = pos
    clean_end = pos + len(clean_lower)
    labels: list[str] = []
    seen_first = False

    for start, end in token_spans:
        if start < clean_end and end > clean_start:
            if not seen_first:
                labels.append("B-ING")
                seen_first = True
            else:
                labels.append("I-ING")
        else:
            labels.append("O")

    return labels


def create_training_dataset(
    pairs: list[dict[str, str]],
    tokenizer: Any,
    label2id: dict[str, int],
    max_length: int = 128,
) -> Any:
    """Convert labeled pairs to a token classification Dataset.

    Tokenizes each dirty line with offset mapping, aligns BIO labels from
    get_bio_labels to subword tokens (special tokens get -100, ignored in
    loss), and returns a HuggingFace Dataset with input_ids, attention_mask,
    and labels columns.

    Args:
        pairs: List of dicts with dirty, clean, reasoning keys.
        tokenizer: HuggingFace tokenizer (callable).
        label2id: Mapping from label string to integer id.
        max_length: Maximum sequence length for padding/truncation.

    Returns:
        HuggingFace Dataset ready for Trainer.
    """
    if Dataset is None:
        raise RuntimeError(
            "datasets package is required. Install with: pip install datasets"
        )

    dirty_texts = [p["dirty"] for p in pairs]
    clean_names = [p["clean"] for p in pairs]

    tokenized = tokenizer(
        dirty_texts,
        truncation=True,
        padding="max_length",
        max_length=max_length,
        return_offsets_mapping=True,
    )

    all_labels: list[list[int]] = []
    for i, dirty in enumerate(dirty_texts):
        offsets = tokenized["offset_mapping"][i]
        # Filter to only real token offsets (skip special tokens with (0,0))
        real_offsets = [(s, e) for s, e in offsets if not (s == 0 and e == 0)]
        bio_labels = get_bio_labels(dirty, clean_names[i], real_offsets)
        # Map back to full token list (special tokens get -100 ignored in loss)
        label_ids: list[int] = []
        bio_idx = 0
        for s, e in offsets:
            if s == 0 and e == 0:
                label_ids.append(-100)
            else:
                if bio_idx < len(bio_labels):
                    label_ids.append(label2id.get(bio_labels[bio_idx], 0))
                else:
                    label_ids.append(label2id["O"])
                bio_idx += 1
        all_labels.append(label_ids)

    dataset_dict = {
        "input_ids": tokenized["input_ids"],
        "attention_mask": tokenized["attention_mask"],
        "labels": all_labels,
    }
    return Dataset.from_dict(dataset_dict)


def fine_tune(
    data_path: str,
    output_dir: str,
    model_name: str = "distilbert-base-german-cased",
    epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
) -> int:
    """Fine-tune a German NER model on labeled ingredient data.

    Idempotent: if output_dir already contains a model (config.json),
    warns and returns 0 without training.

    Args:
        data_path: Path to JSONL training data file.
        output_dir: Directory to save the fine-tuned model.
        model_name: Pretrained model identifier from HuggingFace hub.
        epochs: Number of training epochs.
        batch_size: Training batch size.
        learning_rate: Learning rate for the optimizer.

    Returns:
        Number of training examples used (0 if skipped).
    """
    output = Path(output_dir)
    if output.exists() and (output / "config.json").exists():
        print(f"Model already exists at {output_dir}, skipping.")
        return 0

    pairs = load_training_data(data_path)
    if not pairs:
        print("No training data found.")
        return 0

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForTokenClassification.from_pretrained(
        model_name,
        num_labels=3,
        id2label={0: "O", 1: "B-ING", 2: "I-ING"},
        label2id={"O": 0, "B-ING": 1, "I-ING": 2},
    )

    label2id = {"O": 0, "B-ING": 1, "I-ING": 2}
    dataset = create_training_dataset(pairs, tokenizer, label2id)

    # 90/10 train/eval split
    split = dataset.train_test_split(test_size=0.1, seed=42)
    train_dataset = split["train"]
    eval_dataset = split["test"]

    training_args = TrainingArguments(
        output_dir=str(output / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=10,
        learning_rate=learning_rate,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
    )

    trainer.train()

    # Save final model
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(output))
    tokenizer.save_pretrained(str(output))

    print(f"Model saved to {output_dir} ({len(pairs)} training examples)")
    return len(pairs)


def main() -> NoReturn:
    """Entry point: train and save the NER model."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fine-tune a German NER model for ingredient name cleaning"
    )
    parser.add_argument(
        "--data",
        default=str(_REPO_ROOT / "backend/data/training_pairs.jsonl"),
        help="Path to training JSONL file",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_REPO_ROOT / "backend/models/ingredient_ner"),
        help="Directory to save the fine-tuned model",
    )
    parser.add_argument(
        "--model-name",
        default="distilbert-base-german-cased",
        help="Pretrained model name or path",
    )
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    args = parser.parse_args()

    try:
        count = fine_tune(
            data_path=args.data,
            output_dir=args.output_dir,
            model_name=args.model_name,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
        )
        print(f"Fine-tuning complete. Trained on {count} examples.")
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
