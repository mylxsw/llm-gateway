# LLM Gateway Project Overview

## Project Purpose
The LLM Gateway is a robust proxy service designed to route, manage, and monitor requests to Large Language Model (LLM) providers like OpenAI and Anthropic. It provides a unified interface for multiple providers, enabling capabilities such as:
- **Rule-based Routing:** Intelligently routing requests based on models, headers, and token usage.
- **Failover & Retries:** Ensuring high availability through automatic retries and switching to backup providers.
- **Observability:** Comprehensive logging of requests, including token usage and latency, with sensitive data redaction.
- **Management:** A centralized dashboard for configuring providers, models, API keys, and viewing logs.

## Architecture

The project follows a standard full-stack architecture:

### Backend (`backend/`)
- **Framework:** Python + FastAPI
- **Database:** SQLite (default) or PostgreSQL, accessed via SQLAlchemy (async).
- **Core Components:**
    - **Proxy Service:** Handles request forwarding, implementing the OpenAI/Anthropic protocol.
    - **Rule Engine:** Evaluates context (request body, headers) to determine the target provider and model.
    - **Strategy Engine:** Manages load balancing (currently Round Robin).
    - **Token Counter:** Estimates token usage for logging and rules.
- **Key Directories:**
    - `app/api`: API route definitions.
    - `app/services`: Business logic (proxying, rules, logging).
    - `app/repositories`: Database access layer.
    - `app/providers`: Adapters for upstream LLM providers.
    - `app/rules`: Rule evaluation logic.

### Frontend (`frontend/`)
- **Framework:** Next.js (App Router) + TypeScript
- **Styling:** Tailwind CSS + shadcn/ui
- **State Management:** React Query
- **Key Features:**
    - **Dashboard:** Overview of system status.
    - **Configuration:** Management interfaces for Providers, Models, and API Keys.
    - **Logs:** Detailed request log viewer with filtering capabilities.

## Getting Started

### Backend Setup
1.  Navigate to the `backend` directory:
    ```bash
    cd backend
    ```
2.  Install dependencies (assuming `uv` or `pip`):
    ```bash
    # using uv
    uv sync
    # OR using pip
    pip install -r requirements.txt
    ```
3.  Run database migrations:
    ```bash
    alembic upgrade head
    ```
4.  Start the development server:
    ```bash
    uvicorn app.main:app --reload
    ```
5.  Run tests:
    ```bash
    pytest
    ```

### Frontend Setup
1.  Navigate to the `frontend` directory:
    ```bash
    cd frontend
    ```
2.  Install dependencies:
    ```bash
    pnpm install
    ```
3.  Start the development server:
    ```bash
    pnpm dev
    ```

## Development Conventions

- **Code Style:**
    - **Python:** Follows PEP 8. Use type hints for all function signatures.
    - **TypeScript:** Strict type checking enabled. Follow standard React hooks patterns.
- **Architecture:**
    - **Layered Approach:** Strict separation between API (Routes), Service (Business Logic), and Repository (Data Access) layers.
    - **Dependency Injection:** Services and Repositories should be injected where possible to facilitate testing.
- **Testing:**
    - All new features and bug fixes must be accompanied by unit tests.
    - Backend tests are located in `backend/tests`.
- **Database:**
    - Use SQLAlchemy ORM for database interactions.
    - All schema changes must be managed via Alembic migrations.

## Key Configuration Files
- `backend/pyproject.toml`: Backend dependencies and project metadata.
- `backend/app/config.py`: Application configuration settings (env vars).
- `frontend/package.json`: Frontend dependencies and scripts.
- `docs/architecture.md`: Detailed architectural design.
- `req.md`: Detailed functional and non-functional requirements.
