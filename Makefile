PYTHON ?= python
COMPOSE ?= docker compose

.PHONY: install format lint typecheck test-unit test-integration test-e2e test ci migrate compose-up compose-down demo-fake live-smoke

install:
	$(PYTHON) -m pip install -r requirements-dev.lock

format:
	$(PYTHON) -m black src tests migrations

lint:
	$(PYTHON) -m black --check src tests migrations
	$(PYTHON) -m flake8 src tests

typecheck:
	$(PYTHON) -m mypy src

test-unit:
	PYTHONPATH=src $(PYTHON) -m pytest -q tests/unit tests/api

test-integration:
	RUN_INTEGRATION=1 PYTHONPATH=src $(PYTHON) -m pytest -q -m integration tests/integration

test-e2e:
	RUN_INTEGRATION=1 PYTHONPATH=src $(PYTHON) -m pytest -q -m e2e tests/e2e

test: test-unit test-integration test-e2e

ci: lint typecheck test-unit

migrate:
	$(PYTHON) -m alembic upgrade head

compose-up:
	$(COMPOSE) up --build -d

compose-down:
	$(COMPOSE) down

demo-fake:
	bash scripts/demo_fake.sh

live-smoke:
	bash scripts/live_smoke.sh
