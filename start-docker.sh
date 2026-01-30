#!/usr/bin/env bash
set -eu

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# PostgreSQL image version (must match docker-compose.yml)
PG_IMAGE="postgres:16-alpine"

# Local container configuration
LOCAL_DB_NAME="${POSTGRES_DB:-llm_gateway}"
LOCAL_DB_USER="${POSTGRES_USER:-llm_gateway}"
LOCAL_DB_PASSWORD="${POSTGRES_PASSWORD:-llm_gateway_password}"

# Remote database configuration (read from environment variables with SYNC_DB_ prefix)
SYNC_DB_HOST="${SYNC_DB_HOST:-}"
SYNC_DB_PORT="${SYNC_DB_PORT:-5432}"
SYNC_DB_NAME="${SYNC_DB_NAME:-llm_gateway}"
SYNC_DB_USER="${SYNC_DB_USER:-}"
SYNC_DB_PASSWORD="${SYNC_DB_PASSWORD:-}"

# Sync mode flags
SYNC_DB=false
SYNC_DB_CLEAN=false

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

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

load_env() {
  if [ -f ".env" ]; then
    set -a
    . ./.env
    set +a
  fi
}

# Wait for PostgreSQL container to be ready
wait_for_postgres() {
    local container_name="$1"
    local max_attempts=30
    local attempt=1

    log_info "Waiting for PostgreSQL container to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if docker exec "${container_name}" pg_isready -U "${LOCAL_DB_USER}" -d "${LOCAL_DB_NAME}" >/dev/null 2>&1; then
            log_info "PostgreSQL container is ready"
            return 0
        fi
        printf "."
        sleep 1
        attempt=$((attempt + 1))
    done
    echo ""
    log_error "PostgreSQL container startup timeout"
    return 1
}

# Clean local database data
clean_local_database() {
    local postgres_container="$1"

    log_info "Cleaning local database data..."

    # Use DROP SCHEMA ... CASCADE to clear all tables, then recreate schema
    # This approach doesn't require disconnecting connections or dropping the database
    if ! docker exec "$postgres_container" \
        psql -U "${LOCAL_DB_USER}" -d "${LOCAL_DB_NAME}" -c \
        "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO ${LOCAL_DB_USER}; GRANT ALL ON SCHEMA public TO public;" >/dev/null 2>&1; then
        log_error "Failed to clean database"
        return 1
    fi

    log_info "Local database cleaned"
}

# Sync data from remote database
sync_remote_database() {
    # Validate required environment variables
    if [ -z "$SYNC_DB_HOST" ]; then
        log_error "Missing remote database host address (SYNC_DB_HOST)"
        log_info "Please set the following environment variables:"
        log_info "  SYNC_DB_HOST     - Remote database host address (required)"
        log_info "  SYNC_DB_PORT     - Remote database port (default: 5432)"
        log_info "  SYNC_DB_NAME     - Remote database name (default: llm_gateway)"
        log_info "  SYNC_DB_USER     - Remote database username (required)"
        log_info "  SYNC_DB_PASSWORD - Remote database password (required)"
        return 1
    fi

    if [ -z "$SYNC_DB_USER" ]; then
        log_error "Missing remote database username (SYNC_DB_USER)"
        return 1
    fi

    if [ -z "$SYNC_DB_PASSWORD" ]; then
        log_error "Missing remote database password (SYNC_DB_PASSWORD)"
        return 1
    fi

    # Get postgres container name
    local postgres_container
    postgres_container=$(docker compose ps -q postgres 2>/dev/null || compose ps -q postgres)

    if [ -z "$postgres_container" ]; then
        log_error "Unable to find PostgreSQL container"
        return 1
    fi

    # Wait for container to be ready
    wait_for_postgres "$postgres_container" || return 1

    # Temporary file
    local dump_file="/tmp/pg_dump_$(date +%Y%m%d_%H%M%S).sql"

    log_info "Exporting data from remote database..."
    log_info "Remote host: ${SYNC_DB_HOST}:${SYNC_DB_PORT}"
    log_info "Remote database: ${SYNC_DB_NAME}"

    # Use pg_dump in Docker container to export remote database
    # --no-owner --no-privileges: Don't export permission-related information
    # --disable-triggers: Disable triggers during import to avoid foreign key constraint issues
    local pg_dump_opts="--no-owner --no-privileges --disable-triggers"
    if [ "$SYNC_DB_CLEAN" = false ]; then
        pg_dump_opts="--clean --if-exists ${pg_dump_opts}"
    fi

    local dump_error_file="/tmp/pg_dump_error_$$.log"
    # Execute pg_dump directly in docker compose's postgres container
    # This ensures proper network connectivity (avoids --network host issues on macOS)
    if ! docker exec \
        -e PGPASSWORD="${SYNC_DB_PASSWORD}" \
        "$postgres_container" \
        pg_dump \
        -h "${SYNC_DB_HOST}" \
        -p "${SYNC_DB_PORT}" \
        -U "${SYNC_DB_USER}" \
        -d "${SYNC_DB_NAME}" \
        --format=plain \
        --inserts \
        $pg_dump_opts \
        > "${dump_file}" 2>"${dump_error_file}"; then
        log_error "Database export failed"
        if [ -s "$dump_error_file" ]; then
            log_error "Error details: $(cat "$dump_error_file")"
        fi
        rm -f "$dump_file" "$dump_error_file"
        return 1
    fi
    rm -f "$dump_error_file"

    if [ ! -s "$dump_file" ]; then
        log_error "Database export failed or data is empty"
        rm -f "$dump_file"
        return 1
    fi

    local dump_size
    dump_size=$(du -h "$dump_file" | cut -f1)
    log_info "Data export completed, file size: ${dump_size}"

    # After successful export, clean local database if clean option is specified
    # This reduces system downtime
    if [ "$SYNC_DB_CLEAN" = true ]; then
        clean_local_database "$postgres_container" || {
            rm -f "$dump_file"
            return 1
        }
    fi

    log_info "Importing data to local container..."
    if ! docker exec -i "$postgres_container" \
        psql -U "${LOCAL_DB_USER}" -d "${LOCAL_DB_NAME}" \
        < "${dump_file}" >/dev/null 2>&1; then
        log_error "Data import failed"
        rm -f "$dump_file"
        return 1
    fi

    rm -f "$dump_file"
    log_info "Data sync completed!"
}

usage() {
    cat <<EOF
Usage: $0 [command] [options] [docker compose args...]

Commands:
  up        Start services (default)
  down      Stop services
  restart   Restart services
  logs      View logs
  ps|status View service status

Options:
  --sync-db       Sync data from remote database after startup
  --sync-clean    Clean local database data before sync (requires --sync-db)
  --help          Show this help message

Database sync environment variables:
  SYNC_DB_HOST     Remote database host address (required)
  SYNC_DB_PORT     Remote database port (default: 5432)
  SYNC_DB_NAME     Remote database name (default: llm_gateway)
  SYNC_DB_USER     Remote database username (required)
  SYNC_DB_PASSWORD Remote database password (required)

Examples:
  $0 up
  $0 up --sync-db
  $0 up --sync-db --sync-clean
  SYNC_DB_HOST=db.example.com SYNC_DB_USER=admin SYNC_DB_PASSWORD=secret $0 up --sync-db
  $0 down
  $0 logs
EOF
}

# Parse arguments
cmd=""
compose_args=""

while [ $# -gt 0 ]; do
    case "$1" in
        --sync-db)
            SYNC_DB=true
            shift
            ;;
        --sync-clean)
            SYNC_DB_CLEAN=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        up|down|restart|logs|ps|status)
            if [ -z "$cmd" ]; then
                cmd="$1"
            else
                compose_args="$compose_args $1"
            fi
            shift
            ;;
        *)
            compose_args="$compose_args $1"
            shift
            ;;
    esac
done

# Default command is up
cmd="${cmd:-up}"

ensure_env
ensure_data_dir
load_env

case "$cmd" in
  up)
    compose up -d --force-recreate --build $compose_args
    echo "Squirrel LLM Gateway is starting..."
    RUNNING_URL="${SQUIRREL_RUNNING_URL:-http://127.0.0.1:${LLM_GATEWAY_PORT:-8000}}"
    echo "Dashboard/API: $RUNNING_URL"

    if [ "$SYNC_DB" = true ]; then
        echo ""
        sync_remote_database
    fi
    ;;
  down)
    compose down $compose_args
    ;;
  restart)
    compose down
    compose up -d --build $compose_args

    if [ "$SYNC_DB" = true ]; then
        echo ""
        sync_remote_database
    fi
    ;;
  logs)
    compose logs -f --tail=200 $compose_args
    ;;
  ps|status)
    compose ps $compose_args
    ;;
  *)
    usage
    exit 2
    ;;
esac
