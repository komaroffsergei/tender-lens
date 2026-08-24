# Карта кода

## Общие модули

| Путь | Ответственность |
|---|---|
| `config.py` | типизированные env-настройки |
| `schemas.py` | контракты источников, событий и API |
| `models.py`, `db.py` | SQLAlchemy и async session |
| `storage.py` | безопасная потоковая запись вложений |
| `nats.py` | stream, publish и durable consumer |
| `ai.py`, `search.py` | fake/Ollama, pgvector retrieval и RAG |

## Crawler

| Путь | Ответственность |
|---|---|
| `crawler/base.py` | SourceAdapter и безопасная HTTP-политика |
| `crawler/ted.py` | нормализация TED Search API |
| `crawler/contracts_finder.py` | нормализация Contracts Finder OCDS |
| `crawler/fixture.py` | offline adapter для тестов |
| `crawler/service.py` | cursor, UPSERT, вложения и publish/republish |
| `crawler/__main__.py` | CLI, source isolation и периодический цикл |

## Indexer и API

| Путь | Ответственность |
|---|---|
| `indexer/extract.py` | PDF/XML/HTML/JSON/TXT extraction |
| `indexer/chunk.py` | детерминированный chunking |
| `indexer/service.py` | атомарная и stale-safe индексация |
| `api/auth.py` | hash-only API-key authentication |
| `api/rate_limit.py` | PostgreSQL fixed-window limiter |
| `api/routes.py`, `api/main.py` | HTTP-контракты, lifecycle и ошибки |
| `web/` | статический адаптивный UI |

## Проверки

| Путь | Уровень |
|---|---|
| `tests/unit/` | pure logic и HTTP mocks |
| `tests/api/` | FastAPI in-process |
| `tests/integration/` | PostgreSQL/pgvector и NATS |
| `tests/e2e/` | полный fixture pipeline |
