# Code map

## Корень

| Путь | Назначение |
|---|---|
| `pyproject.toml` | package metadata, зависимости, black/pytest/mypy config |
| `requirements*.lock` | фиксированные runtime/dev зависимости |
| `Dockerfile` | единый non-root application image |
| `docker-compose.yml` | runtime stack |
| `docker-compose.test.yml` | локальная PostgreSQL/NATS test infra |
| `alembic.ini`, `migrations/` | схема PostgreSQL/pgvector |
| `.github/workflows/ci.yml` | quality, integration и container jobs |
| `scripts/` | fixture demo, live smoke, JSON Schema export |
| `schemas/` | проверяемые wire contracts |
| `examples/fixtures/` | детерминированные TED/CF/PDF/XML/HTML/TXT fixtures |

## Python package

| Путь | Ответственность |
|---|---|
| `config.py` | Pydantic Settings |
| `errors.py` | typed errors |
| `logging.py` | JSON logs и masking |
| `schemas.py` | Pydantic source/NATS/API contracts |
| `hashing.py` | deterministic tender/chunk hashes |
| `models.py` | ровно пять SQLAlchemy models |
| `db.py` | async engine/session factory |
| `storage.py` | safe streaming attachments |
| `nats.py` | JetStream broker и in-memory test broker |
| `ai.py` | fake/live embeddings и generation |
| `search.py` | exact pgvector retrieval и RAG orchestration |
| `cli.py` | API keys и demo seed |

## Crawler

| Путь | Ответственность |
|---|---|
| `crawler/base.py` | SourceAdapter, SourcePage, resilient HTTP policy |
| `crawler/ted.py` | TED Search API normalization |
| `crawler/contracts_finder.py` | OCDS normalization |
| `crawler/fixture.py` | offline E2E adapter |
| `crawler/service.py` | cursor, upsert, downloads, publish/republish |
| `crawler/__main__.py` | process loop и source isolation |

## Indexer

| Путь | Ответственность |
|---|---|
| `indexer/extract.py` | metadata/PDF/XML/HTML/JSON/TXT extraction |
| `indexer/chunk.py` | deterministic paragraph chunking |
| `indexer/service.py` | idempotent atomic index replacement |
| `indexer/__main__.py` | durable consumer/ACK/NAK loop |

## API/UI

| Путь | Ответственность |
|---|---|
| `api/auth.py` | API-key generation/hash/auth |
| `api/rate_limit.py` | atomic fixed-window limiter |
| `api/routes.py` | health, tender, search, ask |
| `api/main.py` | lifespan, errors, middleware, static mount |
| `web/index.html` | semantic form/result structure |
| `web/styles.css` | desktop/mobile adaptive presentation |
| `web/app.js` | sessionStorage, fetch, safe DOM rendering |

## Тесты

| Путь | Уровень |
|---|---|
| `tests/unit/` | pure logic, HTTP mocks, static contracts |
| `tests/api/` | FastAPI in-process |
| `tests/integration/` | PostgreSQL/pgvector и NATS |
| `tests/e2e/` | fixture ingestion → index → search/ask |
