
default:
	echo "Please specify a target: start-backend or start-frontend or test"

test:
	cd llm_api_converter && uv sync --extra dev && uv run pytest
	cd backend && uv sync && uv run pytest

start-backend:
	cd backend && uv sync && uv run python -m app.main

start-frontend:
	cd frontend && npm install && npm run dev

.PHONY: start-backend start-frontend test
