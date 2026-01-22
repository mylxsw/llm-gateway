<p align="center">
  <h1 align="center">Squirrel</h1>
  <p align="center">
    <strong>Enterprise-Grade LLM Gateway</strong>
  </p>
  <p align="center">
    Unified API Proxy for OpenAI, Anthropic, and Compatible LLM Providers
  </p>
</p>

<p align="center">
  <a href="README.md"><strong>English</strong></a> ·
  <a href="README_zh-CN.md">中文</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/fastapi-latest-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/nextjs-15-black.svg" alt="Next.js">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
</p>

---

## Overview

**Squirrel** is a high-performance, production-ready proxy service that unifies access to multiple Large Language Model (LLM) providers. It acts as an intelligent gateway between your applications and LLM services, providing seamless failover, load balancing, comprehensive observability, and a modern management dashboard.

### Why Squirrel?

- **Single Integration Point**: Connect once, access multiple LLM providers through a unified API
- **Zero Code Changes**: Drop-in replacement compatible with OpenAI and Anthropic SDKs
- **Cost Optimization**: Route requests intelligently across providers based on rules, priority, or cost
- **Production Ready**: Built-in retry logic, failover mechanisms, and detailed request logging
- **Full Visibility**: Track every request with token usage, latency metrics, and cost analytics

---

## Key Features

### Unified API Interface

- **OpenAI Compatible**: Full support for `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, `/v1/audio/*`, `/v1/images/*`
- **Anthropic Compatible**: Native support for `/v1/messages` endpoint
- **Protocol Conversion**: Automatically convert between OpenAI and Anthropic formats using [litellm](https://github.com/BerriAI/litellm)
- **Streaming Support**: Full Server-Sent Events (SSE) support for real-time responses

### Intelligent Routing

- **Rule-Based Routing**: Route requests based on model name, headers, message content, or token count
- **Load Balancing Strategies**:
  - **Round-Robin**: Distribute requests evenly across providers
  - **Priority-Based**: Use preferred providers first, fallback to others
  - **Weight-Based**: Distribute by custom weight ratios
  - **Cost-Based**: Automatically select the lowest-priced model based on API pricing
- **Model Mapping**: Map virtual model names to multiple backend providers

### High Availability

- **Automatic Retries**: Configurable retry attempts for server errors (HTTP 500+)
- **Provider Failover**: Seamlessly switch to backup providers on failure
- **Timeout Management**: Configurable request timeouts with long streaming support (default: 30 minutes)

### Comprehensive Observability

- **Full Request/Response Capture**: Complete logging of request and response bodies (including streaming) to help debug issues and optimize AI system performance
- **Token Tracking**: Automatic token counting using [tiktoken](https://github.com/openai/tiktoken)
- **Latency Metrics**: First-byte delay and total response time
- **Cost Analytics**: Aggregated statistics by time, model, provider, and API key
- **Data Sanitization**: Automatic redaction of sensitive information in logs

### Modern Dashboard

Built with **Next.js 15** + **TypeScript** + **shadcn/ui**:

- Provider management with connection testing
- Model mapping configuration with rule editor
- API key generation and lifecycle management
- Advanced log viewer with multi-dimensional filtering
- Cost statistics and usage analytics

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Applications                       │
│              (OpenAI SDK, Anthropic SDK, HTTP Clients)           │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Squirrel Gateway                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Proxy API Layer                         │  │
│  │         /v1/chat/completions, /v1/messages, etc.          │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Service Layer                           │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │  │
│  │  │ Rule Engine │ │  Strategy   │ │  Protocol Converter │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘  │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │  │
│  │  │Token Counter│ │ Log Service │ │   Retry Handler     │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   Data Access Layer                        │  │
│  │               SQLite / PostgreSQL Database                 │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Upstream LLM Providers                       │
│    ┌──────────┐   ┌───────────┐   ┌────────────────────────┐    │
│    │  OpenAI  │   │ Anthropic │   │ OpenAI-Compatible APIs │    │
│    └──────────┘   └───────────┘   └────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

For detailed architecture documentation, see [docs/architecture.md](docs/architecture.md).

---

## Quick Start

### Docker Compose (Recommended)

The fastest way to get started with PostgreSQL:

```bash
# Clone the repository
git clone https://github.com/mylxsw/llm-gateway.git
cd llm-gateway

# Configure environment
cp .env.example .env
# Edit .env if needed (optional: set ADMIN_USERNAME and ADMIN_PASSWORD)

# Start services
./start-docker.sh

# Stop services
./stop-docker.sh
```

Access the dashboard at **http://localhost:8000**

### Docker (Single Container)

Run with SQLite for simple deployments:

```bash
docker build -t llm-gateway .
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/data \
  --name llm-gateway \
  llm-gateway
```

### Manual Installation

#### Prerequisites

- Python 3.12+
- Node.js 18+
- pnpm (for frontend)

#### Backend Setup

```bash
cd backend

# Install dependencies (choose one)
uv sync          # Recommended: using uv
pip install -r requirements.txt  # Or using pip

# Initialize database
alembic upgrade head

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### Frontend Setup

```bash
cd frontend

# Install dependencies
pnpm install

# Development
pnpm dev

# Production build
pnpm build && pnpm start
```

---

## Usage

### Basic Configuration

1. **Add a Provider**: Navigate to Providers page and add your LLM provider (e.g., OpenAI)
   - Set the base URL (e.g., `https://api.openai.com/v1`)
   - Add your API key
   - Select the protocol (OpenAI or Anthropic)

2. **Create Model Mapping**: Go to Models page and create a mapping
   - Define a model name (e.g., `gpt-4`)
   - Associate it with one or more providers
   - Set routing priority/weight

3. **Generate API Key**: Create a gateway API key in API Keys page

4. **Connect Your Application**:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="lgw-your-gateway-api-key"
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### API Endpoints

#### Proxy Endpoints (OpenAI Compatible)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/models` | List available models |
| POST | `/v1/chat/completions` | Chat completions |
| POST | `/v1/completions` | Text completions |
| POST | `/v1/embeddings` | Generate embeddings |
| POST | `/v1/audio/speech` | Text-to-speech |
| POST | `/v1/audio/transcriptions` | Speech-to-text |
| POST | `/v1/images/generations` | Image generation |

#### Proxy Endpoints (Anthropic Compatible)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/messages` | Messages API |

#### Admin Endpoints

| Resource | Endpoints |
|----------|-----------|
| Providers | `GET/POST /api/admin/providers`, `GET/PUT/DELETE /api/admin/providers/{id}` |
| Models | `GET/POST /api/admin/models`, `GET/PUT/DELETE /api/admin/models/{model}` |
| API Keys | `GET/POST /api/admin/api-keys`, `GET/PUT/DELETE /api/admin/api-keys/{id}` |
| Logs | `GET /api/admin/logs`, `GET /api/admin/logs/stats` |

See [docs/api.md](docs/api.md) for complete API documentation.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | LLM Gateway | Application name |
| `DEBUG` | false | Enable debug mode |
| `DATABASE_TYPE` | sqlite | Database type: `sqlite` or `postgresql` |
| `DATABASE_URL` | sqlite+aiosqlite:///./llm_gateway.db | Database connection string |
| `RETRY_MAX_ATTEMPTS` | 3 | Max retry attempts for 500+ errors |
| `RETRY_DELAY_MS` | 1000 | Delay between retries (milliseconds) |
| `HTTP_TIMEOUT` | 1800 | Upstream request timeout (seconds) |
| `API_KEY_PREFIX` | lgw- | Prefix for generated API keys |
| `API_KEY_LENGTH` | 32 | Length of generated API keys |
| `ADMIN_USERNAME` | - | Admin login username (optional) |
| `ADMIN_PASSWORD` | - | Admin login password (optional) |
| `ADMIN_TOKEN_TTL_SECONDS` | 86400 | Admin session TTL (24 hours) |
| `LOG_RETENTION_DAYS` | 7 | Log retention period |
| `LOG_CLEANUP_HOUR` | 4 | Log cleanup time (UTC hour) |

### Database Configuration

**SQLite** (default, simple deployments):
```env
DATABASE_TYPE=sqlite
DATABASE_URL=sqlite+aiosqlite:///./llm_gateway.db
```

**PostgreSQL** (recommended for production):
```env
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/llm_gateway
```

---

## Supported Providers

Squirrel can proxy requests to any OpenAI or Anthropic compatible API:

| Provider | Protocol | Notes |
|----------|----------|-------|
| OpenAI | OpenAI | Full support including GPT-4, GPT-3.5, embeddings, audio, images |
| Anthropic | Anthropic | Claude models via Messages API |
| Azure OpenAI | OpenAI | Use Azure endpoint URL |
| Local Models | OpenAI | Ollama, vLLM, LocalAI, etc. |
| Other Providers | OpenAI/Anthropic | Any compatible API endpoint |

---

## Development

### Project Structure

```
llm-gateway/
├── backend/
│   ├── app/
│   │   ├── api/           # API routes (proxy, admin)
│   │   ├── services/      # Business logic
│   │   ├── providers/     # Protocol adapters
│   │   ├── repositories/  # Data access layer
│   │   ├── db/            # Database models
│   │   ├── domain/        # DTOs and domain models
│   │   ├── rules/         # Rule evaluation engine
│   │   └── common/        # Utilities
│   ├── migrations/        # Alembic migrations
│   └── tests/             # Test suite
├── frontend/
│   └── src/
│       ├── app/           # Next.js App Router pages
│       ├── components/    # React components
│       └── lib/           # Utilities and API client
├── docker-compose.yml
└── Dockerfile
```

### Running Tests

```bash
cd backend
pytest
```

### Database Migrations

```bash
cd backend

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

---

## Documentation

- [Architecture Design](docs/architecture.md)
- [API Reference](docs/api.md)
- [Module Details](docs/modules.md)
- [Requirements](docs/req.md)

---

## License

[MIT](LICENSE)

---

<p align="center">
  Made with care for the LLM community
</p>
