# Ingredient Cleanup Pipeline (Issue #90)

Two-tier intelligent extraction that cleans ingredient names before normalization. The existing `IngredientLineParser` handles quantity/unit extraction; the pipeline cleans only the name field.

```
Parser → Pattern Router → Tier 1 NER → (Tier 2 LLM dispatch) → IngredientNormalizer fallback
```

| Tier | What | When |
|---|---|---|
| 1 | Fine-tuned German NER model (distilbert-base-german-cased) | Always, on every scraped line |
| 2 | Local LLM via Ollama sidecar (qwen3.5:2b) | Lines matching critical patterns (oder, à, equipment, word-form numbers) OR Tier 1 confidence < 0.7 with normalizer failure |
| Fallback | Current `IngredientNormalizer` fuzzy matching | Tier 2 unavailable (timeout, sidecar down) |

## Tier 1 — NER Model Setup

The Tier 1 pipeline code is implemented in `backend/app/services/ingredient_name_cleaner.py` and `backend/app/services/ingredient_cleanup_pipeline.py`. The model does not exist yet — it must be generated from raw training data.

### Prerequisites

Install the training dependency group:

```bash
cd backend
uv sync --group training
```

Set the DeepSeek API key environment variable:

```bash
export DEEPSEEK_API_KEY="sk-..."
```

### Step 1: Generate training data

Scrapes ~200 recipe URLs from swissmilk.ch and bettybossi.ch, extracts ingredient lines, calls the DeepSeek API for dirty→clean labeling, and saves ~3000-5000 labeled pairs.

```bash
cd backend
python -m scripts.generate_training_data --api-key "$DEEPSEEK_API_KEY"
```

Output:
- `backend/data/training_pairs.jsonl` — labeled pairs for training
- `backend/data/training_pairs_review.jsonl` — ~5% flagged for manual spot-check

The script is idempotent — skips if `training_pairs.jsonl` already exists.

### Step 2: Fine-tune the model

Trains `distilbert-base-german-cased` on the labeled data using token classification (B-ING/I-ING/O labels) and saves the model artifact.

```bash
cd backend
python -m scripts.fine_tune --data backend/data/training_pairs.jsonl
```

Output: `backend/models/ingredient_ner/` containing:
- `config.json`
- `model.safetensors` (or `pytorch_model.bin`)
- `tokenizer.json`, `tokenizer_config.json`
- `vocab.txt`, `special_tokens_map.json`

The script is idempotent — skips if `config.json` already exists.

Optional flags: `--epochs 3`, `--batch-size 16`, `--learning-rate 2e-5`.

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

## Tier 2 — Ollama LLM Setup

The Tier 2 code is implemented in `backend/app/services/ingredient_llm_resolver.py`. The Ollama sidecar is already defined in `docker-compose.yml`.

### Prerequisites

The Ollama sidecar is only in production compose (`docker-compose.yml`), **not** in `docker-compose.dev.yml`. For local dev testing, either:
- Use `docker compose up` (production compose), or
- Add the ollama service to `docker-compose.dev.yml` manually, or
- Run Ollama standalone: `ollama serve` and point `OLLAMA_BASE_URL=http://localhost:11434`

### Step 1: Pull the model

```bash
# If using docker compose sidecar:
docker compose exec ollama ollama pull qwen3.5:2b

# If running Ollama directly:
ollama pull qwen3.5:2b
```

The model is ~0.5 GB (q4 quantized). Takes 1-3 minutes depending on network.

### Step 2: Configure environment

In `.env` (or directly in docker-compose environment):

```bash
OLLAMA_BASE_URL=http://ollama:11434   # already set in docker-compose.yml
OLLAMA_MODEL=qwen3.5:2b            # defaults to qwen3.5:2b, override if needed
```

### Step 3: Start the stack

```bash
docker compose up -d
```

Verify Ollama is reachable:

```bash
curl http://ollama:11434/api/tags
```

### Verifying Tier 2

Import a recipe with known hard patterns — lines containing "oder", "à", equipment terms, or word-form numbers. These should route through Tier 2 and show corrected names in the import form.

### Fallback behavior

When Ollama is unreachable or times out (10s timeout), Tier 2 returns empty results and the pipeline falls through to the current `IngredientNormalizer`. Imports never block on Tier 2. Check logs for:

```
LLM resolver batch request failed: ...  # connection error or timeout
```

---

## Environment Variables Reference

| Variable | Default | Used by |
|---|---|---|
| `DEEPSEEK_API_KEY` | *(required, no default)* | `generate_training_data.py` |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | `IngredientLLMResolver` |
| `OLLAMA_MODEL` | `qwen3.5:2b` | `IngredientLLMResolver` |

---

## Troubleshooting

### "NER model not found" at startup
The `backend/models/ingredient_ner/` directory does not exist or `config.json` is missing. Run the fine-tuning script (Step 2 above) and rebuild the Docker image.

### "LLM resolver batch request failed"
Ollama sidecar is not running or not reachable at `OLLAMA_BASE_URL`. Check `docker compose ps ollama` and verify the URL. Imports still work — Tier 2 degrades gracefully.

### Model loading crashes app at startup
This is intentional (fail-fast). Check that all model files are present and not corrupted. Remove `backend/models/ingredient_ner/` and re-run fine-tuning.

### Training data generation fails
Ensure `DEEPSEEK_API_KEY` is set and the key has credits. The script uses the `deepseek-chat` model at `https://api.deepseek.com/v1`.

### Ollama model not found
Run `docker compose exec ollama ollama list` to see pulled models. Pull the model if missing: `docker compose exec ollama ollama pull qwen3.5:2b`.

---

## Test Files

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
