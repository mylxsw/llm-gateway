#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is not installed. Install uv first: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

echo "[backend] syncing dependencies..."
uv sync

echo "[backend] running pytest..."
uv run pytest "$@"
