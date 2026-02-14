
default:
	echo "Please specify a target: start-backend or start-frontend or test"

test:
	cd llm_api_converter && uv sync --extra dev && uv run pytest
	$(MAKE) test-backend

test-backend:
	./backend/run-tests.sh

start-backend:
	cd backend && uv sync && uv run python -m app.main

start-frontend:
	cd frontend && npm install && npm run dev

.PHONY: start-backend start-frontend test test-backend
