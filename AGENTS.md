# Repository Guidelines

## Project Structure & Module Organization
This repo has two main apps: `backend/` (FastAPI) and `frontend/` (Next.js). Backend code lives in `backend/app/` with feature areas like `api/`, `services/`, `repositories/`, `rules/`, and `providers/`. Tests are in `backend/tests/` (unit and integration). Frontend source is in `frontend/src/` with routes under `src/app/`, reusable UI in `src/components/`, and API clients in `src/lib/api/`. Static assets live in `frontend/public/`. Architecture notes are in `docs/`.

## Build, Test, and Development Commands
Run commands from each app directory:

```bash
cd backend
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run python -m app.main
pytest
```

- `uv run python -m app.main`: start the API service (uses the configured FastAPI entrypoint).
- `pytest`: run backend unit/integration tests.

```bash
cd frontend
npm run dev
npm run build
npm run lint
```

- `npm run dev`: start the frontend dev server.
- `npm run build`: production build.
- `npm run lint`: ESLint checks.

## Local Setup & CI Expectations
Backend uses `uv` with a Python 3.12 virtualenv; install dependencies from `backend/requirements.txt`. Frontend uses npm (or pnpm/yarn if you prefer) with `frontend/package.json`.

CI is not defined in this repo, so treat local checks as the gate: run `pytest` for backend changes and `npm run lint` (plus `npm run build` when touching Next.js config) before opening a PR.

## Coding Style & Naming Conventions
Backend: 4-space indentation, `snake_case` for functions/variables, `PascalCase` for classes. Keep modules small and follow existing layering (`api/` -> `services/` -> `repositories/`). Frontend: TypeScript/React with `PascalCase` components (e.g., `LogList.tsx`), `camelCase` for hooks and utilities (e.g., `useProviders`). ESLint is the primary frontend style gate; no auto-formatter is configured.

## Testing Guidelines
Backend tests use `pytest` with files named `test_*.py` under `backend/tests/`. Add unit tests alongside the relevant module area (e.g., `backend/tests/unit/test_services/`). No frontend test framework is currently configured; keep UI changes manual-testable and note coverage gaps in PRs.

## Commit & Pull Request Guidelines
Recent commits use short, descriptive messages (often in Chinese) and sometimes include a tracker suffix like `(vibe-kanban <id>)`. Follow that style: keep messages brief and focused. PRs should include: a summary, test commands run, and screenshots for UI changes. Link related issues or kanban cards when available.

## Configuration & Security
Backend settings come from environment variables (see `backend/app/config.py`). Common ones include `DATABASE_TYPE` and `DATABASE_URL`; use a local `.env` and avoid committing secrets or API keys.
