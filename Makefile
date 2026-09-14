.PHONY: install lint format typecheck test cov ingest seed eval run-api run-ui

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
	$(UV) run mypy src tests

test:
	$(UV) run pytest -m "not e2e"

cov:
	$(UV) run pytest -m "not e2e" --cov --cov-report=term-missing

# Stubs: implementados nas fases indicadas.
ingest:
	@echo "ingest: entra na F2"

seed:
	@echo "seed: entra na F1"

eval:
	@echo "eval: entra na F6"

run-api:
	@echo "run-api: entra na F5"

run-ui:
	@echo "run-ui: entra na F5"
