#!/usr/bin/env sh
set -eu

if docker compose version >/dev/null 2>&1; then
  docker compose down "$@"
  exit 0
fi

if command -v docker-compose >/dev/null 2>&1; then
  docker-compose down "$@"
  exit 0
fi

echo "Error: docker compose (or docker-compose) not found." >&2
exit 1

