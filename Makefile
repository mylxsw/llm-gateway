
default:
	echo "Please specify a target: start-backend or start-frontend"

start-backend:
	cd backend && uv sync && uv run python -m app.main

start-frontend:
	cd frontend && npm install && npm run dev

.PHONY: start-backend start-frontend