#!/usr/bin/env bash

set -e

trap "trap - SIGINT SIGTERM EXIT; kill -- -$$" SIGINT SIGTERM EXIT

(
  cd frontend
  PORT=3000 npm run dev
) &

(
  cd backend
  uv sync && uv run python -m app.main
) &

wait

