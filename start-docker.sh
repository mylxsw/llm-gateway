#!/usr/bin/env sh
set -eu

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  echo "Error: docker compose (or docker-compose) not found." >&2
  exit 1
}

ensure_env() {
  if [ -f ".env" ]; then
    return
  fi

  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
    return
  fi

  cat > .env <<'EOF'
DEBUG=false
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql+asyncpg://llm_gateway:llm_gateway_password@postgres:5432/llm_gateway
POSTGRES_DB=llm_gateway
POSTGRES_USER=llm_gateway
POSTGRES_PASSWORD=llm_gateway_password
EOF
  echo "Created .env with default settings"
}

ensure_data_dir() {
  mkdir -p ./data
}

cmd="${1:-up}"
shift || true

ensure_env
ensure_data_dir

case "$cmd" in
  up)
    compose up -d --build "$@"
    echo "LLM Gateway is starting..."
    echo "Dashboard/API: http://localhost:8000"
    ;;
  down)
    compose down "$@"
    ;;
  restart)
    compose down
    compose up -d --build "$@"
    ;;
  logs)
    compose logs -f --tail=200 "$@"
    ;;
  ps|status)
    compose ps "$@"
    ;;
  *)
    echo "Usage: $0 [up|down|restart|logs|ps] [docker compose args...]" >&2
    exit 2
    ;;
esac
