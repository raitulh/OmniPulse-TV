.PHONY: setup backend frontend test test-backend test-frontend docker-up docker-down

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -r backend/requirements-dev.txt
	cd frontend && npm install

backend:
	cd backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	cd backend && python -m pytest

test-frontend:
	cd frontend && npm test

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
