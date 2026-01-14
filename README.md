# LLM Gateway

[ [**English**](README.md) | [**中文**](README_zh-CN.md) ]

**LLM Gateway** is a high-performance, enterprise-grade proxy service designed to unify and manage access to Large Language Model (LLM) providers like OpenAI and Anthropic. It provides intelligent routing, robust failover strategies, comprehensive logging, and a modern management dashboard.

## ✨ Key Features

- **Unified Interface**: Compatible with OpenAI and Anthropic API protocols. Clients can use standard SDKs without modification.
- **Intelligent Routing**: Route requests based on models, rules, and strategies.
- **Transparent Proxy**: Forwards requests with minimal interference—only the model name is dynamically replaced based on routing rules.
- **High Availability**:
  - **Automatic Retries**: Configurable retries for upstream server errors (HTTP 500+).
  - **Failover**: Automatically switches to backup providers/nodes if the primary fails.
- **Observability**:
  - **Detailed Logging**: Records metrics for every request including latency, status, and retries.
  - **Token Usage**: Tracks input/output tokens using standard counting methods.
  - **Security**: Automatically redacts sensitive information (like `Authorization` headers) in logs.
- **Modern Management Dashboard**:
  - Built with **Next.js** and **shadcn/ui**.
  - Manage Providers, Models, and API Keys.
  - Inspect request logs with advanced filtering.

## 🏗 Architecture

The system consists of a Python (FastAPI) backend and a Next.js frontend.

- **Backend**: Handles request proxying, rule evaluation, and database interactions. Supports **SQLite** (default) and **PostgreSQL**.
- **Frontend**: A web interface for configuration and monitoring.

For a deep dive, check the [Architecture Documentation](docs/architecture.md).

## 🚀 Getting Started

### Prerequisites

- **Python**: 3.12+
- **Node.js**: 18+ (for Frontend)
- **Package Managers**: `uv` or `pip` (Python), `pnpm` (Node.js)

### 1. Backend Setup

1.  Navigate to the backend directory:
    ```bash
    cd backend
    ```

2.  Install dependencies:
    ```bash
    # Recommended: using uv
    uv sync

    # Or using standard pip
    pip install -r requirements.txt
    ```

3.  Configure Environment:
    Copy the example configuration (or just rely on defaults for SQLite):
    ```bash
    # Create a .env file if you need custom settings (e.g., for PostgreSQL)
    touch .env
    ```

4.  Initialize the Database:
    ```bash
    alembic upgrade head
    ```

5.  Start the Server:
    ```bash
    uvicorn app.main:app --reload
    ```
    The API will be available at `http://localhost:8000`.

### 2. Frontend Setup

1.  Navigate to the frontend directory:
    ```bash
    cd frontend
    ```

2.  Install dependencies:
    ```bash
    pnpm install
    ```

3.  Start the Development Server:
    ```bash
    pnpm dev
    ```
    The Dashboard will be available at `http://localhost:3000`.

## 🐳 Docker

Build a single image containing both backend and frontend:

```bash
docker build -t llm-gateway .
docker run --rm -p 8000:8000 -v $(pwd)/data:/data llm-gateway
```

- Dashboard: `http://localhost:8000`
- API: `http://localhost:8000/v1/...` and `http://localhost:8000/api/admin/...`
- Persist SQLite DB by mounting `/data` (or set `DATABASE_URL` to an external DB).

### Docker Compose (one-click)

```bash
cp .env.example .env
./start.sh
```

- Stop: `./stop.sh` (or `./start.sh down`)
- Default DB: PostgreSQL (service `postgres`)
- SQLite: set `DATABASE_TYPE/DATABASE_URL` in `.env` (see `.env.example`)

## ⚙️ Configuration

Configuration is managed via environment variables or a `.env` file in the `backend/` directory.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `APP_NAME` | LLM Gateway | Name of the application. |
| `DEBUG` | False | Enable debug mode. |
| `DATABASE_TYPE` | sqlite | Database backend: `sqlite` or `postgresql`. |
| `DATABASE_URL` | sqlite+aiosqlite:///./llm_gateway.db | Database connection string. |
| `RETRY_MAX_ATTEMPTS` | 3 | Max retries for 500+ errors on the same provider. |
| `RETRY_DELAY_MS` | 1000 | Delay between retries in milliseconds. |
| `HTTP_TIMEOUT` | 60 | Upstream request timeout in seconds. |

## 📚 Documentation

- [Architecture Design](docs/architecture.md)
- [Project Requirements](req.md)
- [Backend Structure](backend/README.md)

## 📄 License

[MIT](LICENSE)
