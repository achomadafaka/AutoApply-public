PYTHON ?= python3

.PHONY: install api-install api-init-db api-dev api-test browser-install ui-install ui-dev ui-check check dev demo

install: api-install ui-install
api-install:
	$(PYTHON) -m venv backend/.venv
	backend/.venv/bin/python -m pip install -r backend/requirements.txt

browser-install:
	backend/.venv/bin/python -m pip install -r backend/requirements-automation.txt
	backend/.venv/bin/python -m playwright install chromium

api-init-db:
	cd backend && .venv/bin/python scripts/init_db.py

demo:
	cd backend && .venv/bin/python scripts/init_db.py --seed seed/001_seed.sql

api-dev:
	cd backend && PYTHONPATH=src .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

api-test:
	cd backend && .venv/bin/python -m ruff check src tests && .venv/bin/python -m pytest -q

ui-install:
	cd frontend && npm ci

ui-dev:
	cd frontend && npm run dev -- --host 127.0.0.1 --strictPort

ui-check:
	cd frontend && npm run lint && npm run check && npm run build

check: api-test ui-check

dev:
	./dev-review.sh
