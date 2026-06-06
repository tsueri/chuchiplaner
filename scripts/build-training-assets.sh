#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# build-training-assets.sh — throwaway Docker container to generate training
#   data and fine-tune the NER model (docs/ingredient-cleanup.md steps 1-2).
#
# Usage:
#   export DEEPSEEK_API_KEY="sk-…"
#   ./scripts/build-training-assets.sh              # default: 100 recipes, 3 epochs
#   ./scripts/build-training-assets.sh --limit 50   # fewer recipes
#   ./scripts/build-training-assets.sh --epochs 5   # more training epochs
#
# Output (written to host):
#   backend/data/training_pairs.jsonl
#   backend/data/training_pairs_review.jsonl
#   backend/models/ingredient_ner/
#
# Dependencies: docker
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

IMAGE="python:3.12-slim"
WORKDIR="/workspace/backend"

# Parse optional flags — pass through to the inner scripts
GENERATE_ARGS=()
FINE_TUNE_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --limit|--api-key|--output|--review-output)
            GENERATE_ARGS+=("$1" "$2"); shift 2 ;;
        --data|--output-dir|--model-name|--epochs|--batch-size|--learning-rate)
            FINE_TUNE_ARGS+=("$1" "$2"); shift 2 ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1 ;;
    esac
done

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "Error: DEEPSEEK_API_KEY environment variable is required." >&2
    exit 1
fi

echo "=== Building training assets in throwaway container ==="

mkdir -p "$REPO_ROOT/backend/data" "$REPO_ROOT/backend/models"

# Reusable caches to avoid re-downloading packages/models every run
docker volume create chuchiplaner-uv-cache 2>/dev/null || true
docker volume create chuchiplaner-hf-cache 2>/dev/null || true

docker run --rm \
    --name chuchiplaner-training \
    -v "$REPO_ROOT:/workspace" \
    -v chuchiplaner-uv-cache:/root/.cache/uv \
    -v chuchiplaner-hf-cache:/tmp/huggingface \
    -w "$WORKDIR" \
    -e DEEPSEEK_API_KEY \
    -e HF_HOME=/tmp/huggingface \
    "$IMAGE" \
    bash -c "
        set -euo pipefail
        echo '--- Installing uv and training dependencies ---'
        pip install --quiet --no-cache-dir uv
        uv sync --group training

        echo ''
        echo '--- Step 1: Generating training data ---'
        uv run python -m scripts.generate_training_data ${GENERATE_ARGS[@]}

        echo ''
        echo '--- Step 2: Fine-tuning NER model ---'
        uv run python -m scripts.fine_tune ${FINE_TUNE_ARGS[@]}

        echo ''
        echo '=== Assets ready ==='
        echo 'Data:   backend/data/training_pairs.jsonl'
        echo 'Model:  backend/models/ingredient_ner/'
    "

echo "=== Done ==="
