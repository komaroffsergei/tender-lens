# 13. Планируемая карта кода

Codex использует этот документ как исходное намерение, но после каждого этапа поддерживает фактическую карту в `docs/code-map.md`.

## 1. Root

| Путь | Назначение |
|---|---|
| `AGENTS.md` | Постоянные правила агента |
| `CODEX_MASTER_PROMPT.md` | Полный сценарий самостоятельной реализации |
| `README.md` | Вход для проверяющего |
| `pyproject.toml` | Package, dependencies, tooling |
| `Dockerfile` | Один image для трёх ролей |
| `docker-compose.yml` | Live local stack |
| `docker-compose.test.yml` | Isolated integration/e2e stack |
| `Makefile` | Канонические команды |
| `migrations/` | Alembic schema history |

## 2. Общие модули

| Модуль | Ответственность |
|---|---|
| `config.py` | Typed settings, без side effects |
| `logging.py` | JSON logging, request/event IDs, masking |
| `db.py` | Engine/session lifecycle |
| `models.py` | SQLAlchemy models |
| `schemas.py` | Shared Pydantic contracts |
| `storage.py` | Safe attachment paths and stream download |
| `nats.py` | Connection, stream/consumer setup, publish/consume primitives |
| `ai.py` | Minimal embed/generate clients and fake provider |
| `files.py` | Content type detection and bounded reads |
| `cli.py` | API key and maintenance commands |

## 3. Crawler

| Модуль | Ответственность |
|---|---|
| `crawler/base.py` | SourceAdapter Protocol, common transport policy |
| `crawler/ted.py` | TED request + mapping only |
| `crawler/contracts_finder.py` | OCDS request + mapping only |
| `crawler/service.py` | Orchestration, persistence, cursor, attachments, publish |
| `crawler/__main__.py` | CLI/loop entry point |

## 4. Indexer

| Модуль | Ответственность |
|---|---|
| `indexer/extract.py` | Safe text extraction |
| `indexer/chunk.py` | Deterministic chunking |
| `indexer/service.py` | Event validation, idempotency, embeddings, transaction, ACK |
| `indexer/__main__.py` | Consumer lifecycle |

## 5. API

| Модуль | Ответственность |
|---|---|
| `api/auth.py` | API key lookup/validation |
| `api/rate_limit.py` | Fixed-window transaction and headers |
| `api/routes.py` | Thin HTTP routes |
| `api/main.py` | App factory, middleware, errors, static UI |

Если routes становятся больше примерно 300 строк, разрешено разделить на `health.py`, `tenders.py`, `search.py`, но не создавать десятки файлов заранее.

## 6. Web

| Файл | Назначение |
|---|---|
| `web/index.html` | Semantic structure |
| `web/styles.css` | Responsive visual system |
| `web/app.js` | Fetch, session key, safe state rendering |

## 7. Тесты

```text
tests/unit/         pure functions, models, adapters, mocks
tests/integration/  PostgreSQL/pgvector/NATS
tests/e2e/          full fixture pipeline
tests/fixtures/     compact stable source and document examples
```

Test filenames группируются по поведению, а не зеркалируют каждый production-файл механически.

## 8. Владение записью

| Данные | Пишет | Читает |
|---|---|---|
| sources/tenders/attachments | crawler, CLI только для source init | crawler, indexer, api |
| chunks/indexed status | indexer | api, indexer |
| api_keys/counters | CLI/API | API |
| attachment volume | crawler | indexer |
| NATS stream | crawler publishes | indexer consumes |

## 9. Запрещённые псевдослои

Не создавать без доказанной потребности:

```text
domain/
application/
infrastructure/
repositories/
use_cases/
factories/
managers/
helpers/
utils/  # как склад несвязанных функций
```
