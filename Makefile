.PHONY: install infra backend frontend test eval up down
install:
	cd backend && python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm install
infra:      ## solo Postgres+pgvector e Redis
	docker compose up -d db redis
backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
frontend:
	cd frontend && npm run dev
test:
	cd backend && .venv/bin/pytest -v | tee ../docs/TEST_RESULTS.txt
eval:
	cd backend && .venv/bin/python eval/run_eval.py --write
up:         ## tutto in Docker
	docker compose up --build
down:
	docker compose down
