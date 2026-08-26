# Тестирование

Тестовая пирамида отделяет чистую логику от infrastructure contracts. Полный searchable список функций и source links находится в [каталоге тестов](reference/test-catalog.md).

## Уровни

### Unit и API

Не используют внешнюю сеть, PostgreSQL, NATS или Ollama. Проверяются:

- контракты Pydantic и отсутствие JSON Schema drift;
- TED и Contracts Finder на сохранённых fixtures;
- bounded concurrency, retry, redirect и SSRF policy;
- потоковая загрузка и ограничения файлов;
- extraction, chunking и fake/live AI HTTP-контракт;
- FastAPI auth, validation, rate-limit headers и безопасные ошибки;
- статические HTML/CSS/JS assets.

```bash
python -m pytest -q tests/unit tests/api
```

### Integration

Используются настоящие PostgreSQL/pgvector и NATS JetStream:

- схема и extension `vector`;
- UPSERT, source isolation, cursor и pending republish;
- идемпотентная индексация и защита от stale event;
- relevance threshold и отсутствие generation без контекста;
- атомарный rate limiter;
- durable consumer с `ack_wait=300` и `max_deliver=5`.

### E2E

Детерминированный сценарий выполняет цепочку:

```text
fixture source → crawler → attachment → PostgreSQL → NATS
→ indexer → pgvector → protected Search/Ask → 429
```

Один из E2E-тестов использует настоящий NATS, а не in-memory broker.

## Локальный инфраструктурный прогон

```bash
docker compose -f docker-compose.test.yml up -d
export DATABASE_URL=postgresql+asyncpg://tender_lens:tender_lens@localhost:55432/tender_lens_test
python -m alembic upgrade head
RUN_INTEGRATION=1 \
TEST_DATABASE_URL="$DATABASE_URL" \
TEST_NATS_URL=nats://localhost:54222 \
python -m pytest -q
docker compose -f docker-compose.test.yml down
```

## GitHub Actions

| Job | Проверки |
|---|---|
| `quality` | Black, Flake8, MyPy, unit/API |
| `integration` | clean migration, PostgreSQL, NATS, integration/E2E, downgrade/upgrade |
| `container` | Compose config, Docker build, non-root и smoke трёх ролей |
| `Documentation / build` | generated reference drift, strict MkDocs, source links и search index |
| `Documentation / deploy` | публикация Pages artifact только из `main` |

Live TED/Contracts Finder и real Ollama намеренно не входят в обязательный CI.

## Документация

```bash
python -m pip install -r requirements-docs.lock
python scripts/generate_code_reference.py --check
python -m mkdocs build --strict
python scripts/check_docs.py
```

Проверка гарантирует, что карта отражает текущий AST/tracked tree, ссылки `GitHub #Lx-Ly` не выходят за файл, а full-text index содержит ключевые понятия и symbols.
