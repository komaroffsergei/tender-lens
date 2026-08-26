PYTHON ?= python
COMPOSE ?= docker compose

.PHONY: install install-docs format lint typecheck test-unit test-integration test-e2e test docs docs-check ci migrate compose-up compose-down demo-fake live-smoke

install:
	$(PYTHON) -m pip install -r requirements-dev.lock

install-docs:
	$(PYTHON) -m pip install -r requirements-docs.lock

format:
	$(PYTHON) -m black src tests migrations scripts

lint:
	$(PYTHON) -m black --check src tests migrations scripts
	$(PYTHON) -m flake8 src tests scripts

typecheck:
	$(PYTHON) -m mypy src

test-unit:
	PYTHONPATH=src $(PYTHON) -m pytest -q tests/unit tests/api

test-integration:
	RUN_INTEGRATION=1 PYTHONPATH=src $(PYTHON) -m pytest -q -m integration tests/integration

test-e2e:
	RUN_INTEGRATION=1 PYTHONPATH=src $(PYTHON) -m pytest -q -m e2e tests/e2e

test: test-unit test-integration test-e2e

docs:
	$(PYTHON) scripts/generate_code_reference.py
	$(PYTHON) -m mkdocs serve --dev-addr 127.0.0.1:8001

docs-check:
	$(PYTHON) scripts/generate_code_reference.py --check
	$(PYTHON) -m mkdocs build --strict
	$(PYTHON) scripts/check_docs.py

ci: lint typecheck test-unit docs-check

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
