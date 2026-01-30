#!/usr/bin/env bash
set -eu

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

RUNNING_URL="${SQUIRREL_RUNNING_URL:-http://127.0.0.1:8000}"

# PostgreSQL 镜像版本（与 docker-compose.yml 保持一致）
PG_IMAGE="postgres:16-alpine"

# 本地容器配置
LOCAL_DB_NAME="${POSTGRES_DB:-llm_gateway}"
LOCAL_DB_USER="${POSTGRES_USER:-llm_gateway}"
LOCAL_DB_PASSWORD="${POSTGRES_PASSWORD:-llm_gateway_password}"

# 远程数据库配置（从环境变量读取，使用 SYNC_DB_ 前缀）
SYNC_DB_HOST="${SYNC_DB_HOST:-}"
SYNC_DB_PORT="${SYNC_DB_PORT:-5432}"
SYNC_DB_NAME="${SYNC_DB_NAME:-llm_gateway}"
SYNC_DB_USER="${SYNC_DB_USER:-}"
SYNC_DB_PASSWORD="${SYNC_DB_PASSWORD:-}"

# 同步模式标志
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

# 等待 PostgreSQL 容器就绪
wait_for_postgres() {
    local container_name="$1"
    local max_attempts=30
    local attempt=1

    log_info "等待 PostgreSQL 容器就绪..."
    while [ $attempt -le $max_attempts ]; do
        if docker exec "${container_name}" pg_isready -U "${LOCAL_DB_USER}" -d "${LOCAL_DB_NAME}" >/dev/null 2>&1; then
            log_info "PostgreSQL 容器已就绪"
            return 0
        fi
        printf "."
        sleep 1
        attempt=$((attempt + 1))
    done
    echo ""
    log_error "PostgreSQL 容器启动超时"
    return 1
}

# 清理本地数据库数据
clean_local_database() {
    local postgres_container="$1"

    log_info "清理本地数据库数据..."

    # 使用 DROP SCHEMA ... CASCADE 清空所有表，然后重建 schema
    # 这种方式不需要断开连接，也不需要删除数据库
    if ! docker exec "$postgres_container" \
        psql -U "${LOCAL_DB_USER}" -d "${LOCAL_DB_NAME}" -c \
        "DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO ${LOCAL_DB_USER}; GRANT ALL ON SCHEMA public TO public;" >/dev/null 2>&1; then
        log_error "清理数据库失败"
        return 1
    fi

    log_info "本地数据库已清理"
}

# 从远程数据库同步数据
sync_remote_database() {
    # 验证必需的环境变量
    if [ -z "$SYNC_DB_HOST" ]; then
        log_error "缺少远程数据库主机地址 (SYNC_DB_HOST)"
        log_info "请设置以下环境变量:"
        log_info "  SYNC_DB_HOST     - 远程数据库主机地址 (必需)"
        log_info "  SYNC_DB_PORT     - 远程数据库端口 (默认: 5432)"
        log_info "  SYNC_DB_NAME     - 远程数据库名称 (默认: llm_gateway)"
        log_info "  SYNC_DB_USER     - 远程数据库用户名 (必需)"
        log_info "  SYNC_DB_PASSWORD - 远程数据库密码 (必需)"
        return 1
    fi

    if [ -z "$SYNC_DB_USER" ]; then
        log_error "缺少远程数据库用户名 (SYNC_DB_USER)"
        return 1
    fi

    if [ -z "$SYNC_DB_PASSWORD" ]; then
        log_error "缺少远程数据库密码 (SYNC_DB_PASSWORD)"
        return 1
    fi

    # 获取 postgres 容器名称
    local postgres_container
    postgres_container=$(docker compose ps -q postgres 2>/dev/null || compose ps -q postgres)

    if [ -z "$postgres_container" ]; then
        log_error "无法找到 PostgreSQL 容器"
        return 1
    fi

    # 等待容器就绪
    wait_for_postgres "$postgres_container" || return 1

    # 临时文件
    local dump_file="/tmp/pg_dump_$(date +%Y%m%d_%H%M%S).sql"

    log_info "从远程数据库导出数据..."
    log_info "远程主机: ${SYNC_DB_HOST}:${SYNC_DB_PORT}"
    log_info "远程数据库: ${SYNC_DB_NAME}"

    # 使用 Docker 容器中的 pg_dump 来导出远程数据库
    # --no-owner --no-privileges: 不导出权限相关信息
    # --disable-triggers: 导入时禁用触发器，避免外键约束问题
    local pg_dump_opts="--no-owner --no-privileges --disable-triggers"
    if [ "$SYNC_DB_CLEAN" = false ]; then
        pg_dump_opts="--clean --if-exists ${pg_dump_opts}"
    fi

    local dump_error_file="/tmp/pg_dump_error_$$.log"
    # 直接在 docker compose 的 postgres 容器中执行 pg_dump
    # 这样可以确保网络连接正常（避免 macOS 上 --network host 的问题）
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
        log_error "数据库导出失败"
        if [ -s "$dump_error_file" ]; then
            log_error "错误详情: $(cat "$dump_error_file")"
        fi
        rm -f "$dump_file" "$dump_error_file"
        return 1
    fi
    rm -f "$dump_error_file"

    if [ ! -s "$dump_file" ]; then
        log_error "数据库导出失败或数据为空"
        rm -f "$dump_file"
        return 1
    fi

    local dump_size
    dump_size=$(du -h "$dump_file" | cut -f1)
    log_info "数据导出完成，文件大小: ${dump_size}"

    # 导出成功后，如果指定了清理选项，再清理本地数据库
    # 这样可以减少系统停机时间
    if [ "$SYNC_DB_CLEAN" = true ]; then
        clean_local_database "$postgres_container" || {
            rm -f "$dump_file"
            return 1
        }
    fi

    log_info "将数据导入到本地容器..."
    if ! docker exec -i "$postgres_container" \
        psql -U "${LOCAL_DB_USER}" -d "${LOCAL_DB_NAME}" \
        < "${dump_file}" >/dev/null 2>&1; then
        log_error "数据导入失败"
        rm -f "$dump_file"
        return 1
    fi

    rm -f "$dump_file"
    log_info "数据同步完成！"
}

usage() {
    cat <<EOF
用法: $0 [命令] [选项] [docker compose 参数...]

命令:
  up        启动服务 (默认)
  down      停止服务
  restart   重启服务
  logs      查看日志
  ps|status 查看服务状态

选项:
  --sync-db       启动后从远程数据库同步数据
  --sync-clean    同步前清理本地数据库数据 (需配合 --sync-db 使用)
  --help          显示此帮助信息

数据库同步环境变量:
  SYNC_DB_HOST     远程数据库主机地址 (必需)
  SYNC_DB_PORT     远程数据库端口 (默认: 5432)
  SYNC_DB_NAME     远程数据库名称 (默认: llm_gateway)
  SYNC_DB_USER     远程数据库用户名 (必需)
  SYNC_DB_PASSWORD 远程数据库密码 (必需)

示例:
  $0 up
  $0 up --sync-db
  $0 up --sync-db --sync-clean
  SYNC_DB_HOST=db.example.com SYNC_DB_USER=admin SYNC_DB_PASSWORD=secret $0 up --sync-db
  $0 down
  $0 logs
EOF
}

# 解析参数
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

# 默认命令为 up
cmd="${cmd:-up}"

ensure_env
ensure_data_dir

case "$cmd" in
  up)
    compose up -d --force-recreate --build $compose_args
    echo "Squirrel LLM Gateway is starting..."
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
