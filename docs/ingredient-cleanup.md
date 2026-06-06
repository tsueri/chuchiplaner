# Ingredient Cleanup Pipeline (Issue #90)

Two-tier intelligent extraction that cleans ingredient names before normalization. The existing `IngredientLineParser` handles quantity/unit extraction; the pipeline cleans only the name field.

```
Parser → Tier 1 NER → Regex post-processing → IngredientNormalizer
```

| Tier | What | When |
|---|---|---|
| 1 | Fine-tuned German NER model (distilbert-base-german-cased) + regex post-processing | Always, on every scraped line |
| Fallback | Current `IngredientNormalizer` fuzzy matching | NER model unavailable |

## Tier 1 — NER Model Setup

The Tier 1 pipeline code is implemented in `backend/app/services/ingredient_name_cleaner.py` and `backend/app/services/ingredient_cleanup_pipeline.py`. The model does not exist yet — it must be generated from raw training data.

### Prerequisites

An LLM API key (OpenAI-compatible). [DeepSeek](https://platform.deepseek.com/) is the default provider.

Set the API configuration:

```bash
export CHUCHI_LLM_API_KEY="sk-..."
export CHUCHI_LLM_API_URL="https://api.deepseek.com/v1"    # default
export CHUCHI_LLM_MODEL="deepseek-chat"                     # default
```

### Quick start (recommended)

Run both steps in a throwaway Docker container — no need to install `transformers`, `torch`, or `datasets` on the host:

```bash
./scripts/build-training-assets.sh
```

Optional flags pass through: `--limit 50`, `--epochs 5`, `--batch-size 8`, etc.

### Step 1: Generate training data

Scrapes ~200 recipe URLs from swissmilk.ch and bettybossi.ch, extracts ingredient lines, calls the DeepSeek API for dirty→clean labeling, and saves ~3000-5000 labeled pairs.

```bash
cd backend
python -m scripts.generate_training_data --api-key "$CHUCHI_LLM_API_KEY"
```

Output:
- `backend/data/training_pairs.jsonl` — labeled pairs for training
- `backend/data/training_pairs_review.jsonl` — ~5% flagged for manual spot-check

The script is idempotent — skips if `training_pairs.jsonl` already exists.

### Step 2: Fine-tune the model

Trains `distilbert-base-german-cased` on the labeled data using token classification (B-ING/I-ING/O labels) and saves the model artifact.

```bash
cd backend
python -m scripts.fine_tune
```

Output: `backend/models/ingredient_ner/` containing:
- `config.json`
- `model.safetensors` (or `pytorch_model.bin`)
- `tokenizer.json`, `tokenizer_config.json`
- `vocab.txt`, `special_tokens_map.json`

The script is idempotent — skips if `config.json` already exists.

Optional flags: `--epochs 3`, `--batch-size 16`, `--learning-rate 2e-5`.

> **Local alternative:** Run steps 1-2 directly on the host by installing the training
> dependency group first: `cd backend && uv sync --group training`.

### Step 3: Rebuild Docker image

The model is bundled into the image at build time via `COPY backend/ ./` in the Dockerfile. After fine-tuning, rebuild:

```bash
docker compose build app
```

### Verifying Tier 1

After rebuild and restart, check startup logs:

```
NER model loaded from backend/models/ingredient_ner  # model found
NER model not found at backend/models/ingredient_ner — ingredient name cleaning disabled  # model missing
```

Import a Swiss recipe (e.g. from swissmilk.ch) via the UI. Ingredient lines should show cleaned names (e.g. "gehackter Peterli" → "Peterli").

---

## Regex Post-Processing

After NER cleaning, regex rules handle remaining edge cases:

| Rule | Pattern | Example → Result |
|---|---|---|
| Alternatives | `X oder Y` → `X` | "Weisswein oder Zitronensaft" → "Weisswein" |
| Embedded weight | `à Ng` → stripped | "Camembert Suisse à 300 g" → "Camembert" |
| Parentheticals | `(X)` → stripped | "Rahmjoghurt (griechische Art)" → "Rahmjoghurt" |
| Slash alternatives | `X / Y` → `X` | "Gratinform / Kuchenblech" → "Gratinform" |
| Prep notes | `, X` at end → stripped | "Brot, in Sticks geschnitten" → "Brot" |
| Equipment detection | Denylist match → `is_equipment: true` | "Backpapier" → flagged |

---

## Environment Variables Reference

| Variable | Default | Used by |
|---|---|---|
| `CHUCHI_LLM_API_URL` | `https://api.deepseek.com/v1` | `generate_training_data.py` |
| `CHUCHI_LLM_API_KEY` | *(falls back to `DEEPSEEK_API_KEY`)* | `generate_training_data.py` |
| `CHUCHI_LLM_MODEL` | `deepseek-chat` | `generate_training_data.py` |

---

## Troubleshooting

### "NER model not found" at startup
The `backend/models/ingredient_ner/` directory does not exist or `config.json` is missing. Run the fine-tuning script (Step 2 above) and rebuild the Docker image.

### "LLM resolver batch request failed"
This was the old Tier 2 (Ollama LLM) which has been removed. Regex post-processing now handles these cases. Tier 1 NER + regex replaces the LLM pipeline.

### Model loading crashes app at startup
This is intentional (fail-fast). Check that all model files are present and not corrupted. Remove `backend/models/ingredient_ner/` and re-run fine-tuning.

### Training data generation fails
Ensure `CHUCHI_LLM_API_KEY` is set and the key has credits. The script uses the OpenAI-compatible API at the configured `CHUCHI_LLM_API_URL`.

### Test Files

| File | Scope |
|---|---|
| `backend/tests/test_ingredient_name_cleaner.py` | Tier 1 NER cleaning (mock model) |
| `backend/tests/test_ingredient_llm_resolver.py` | Tier 2 LLM resolver (mock HTTP) |
| `backend/tests/test_ingredient_cleanup_pipeline.py` | Pipeline integration tests |
| `backend/tests/test_recipes.py` | Import endpoint integration |

Run all related tests:

```bash
cd backend && uv run pytest tests/test_ingredient_name_cleaner.py tests/test_ingredient_llm_resolver.py tests/test_ingredient_cleanup_pipeline.py
```
