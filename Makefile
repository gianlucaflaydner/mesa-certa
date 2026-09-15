.PHONY: install lint format typecheck test cov ingest search seed chat eval run-api run-web web-install web-check

UV ?= uv

install:
	$(UV) sync --all-groups

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format:
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

typecheck:
	$(UV) run mypy src tests scripts

test:
	$(UV) run pytest -m "not e2e"

cov:
	$(UV) run pytest -m "not e2e" --cov --cov-report=term-missing

# Stubs: implementados nas fases indicadas.
ingest:
	$(UV) run python scripts/ingest.py

search:
	$(UV) run python scripts/search.py "$(Q)"

seed:
	$(UV) run python scripts/reset_db.py

# Ex.: make chat ARGS="--agora 2026-09-15T14:00:00-03:00 --debug"
chat:
	$(UV) run python scripts/chat.py $(ARGS)

eval:
	@echo "eval: entra na F6"

# API em http://localhost:8000. Para a demo, fixe o relógio do seed: FIXED_NOW no .env.
run-api:
	$(UV) run uvicorn mesa_certa.api.main:app --reload --port 8000

# Front-end Next.js em http://localhost:3000 (pasta web/).
web-install:
	cd web && npm install

run-web:
	cd web && npm run dev

web-check:
	cd web && npm run lint && npm run typecheck && npm test && npm run build
