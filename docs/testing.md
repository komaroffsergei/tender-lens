# Тестирование TenderLens

## Уровни

### Unit

Не используют внешнюю сеть, PostgreSQL, NATS или Ollama. `httpx.MockTransport`, fake sessions и `FakeAIProvider` проверяют:

- Pydantic contracts и JSON Schema drift;
- hashing;
- два source adapters;
- malformed record isolation;
- concurrency, retry, cooldown и redirect policy;
- безопасную загрузку файлов;
- extraction и chunking;
- Ollama HTTP contract;
- prompt-injection boundary;
- API-key и rate limiter state machine;
- static UI security checks.

```bash
make test-unit
```

### API

FastAPI запускается in-process с fake session/search/AI. Проверяются:

- health;
- auth 401/403;
- sanitized tender details;
- validation errors;
- Search/Ask contracts;
- shared rate limit и 429 headers;
- stable 500/503;
- static UI/assets.

### Integration

Требуются настоящий PostgreSQL/pgvector и NATS JetStream:

- migration и vector extension;
- upsert/unique constraints;
- exact vector query;
- idempotent/stale indexing;
- concurrent row-lock limiter;
- JetStream create/publish/consume/ACK.

### E2E

Fixture source → PostgreSQL → attachment volume → event → indexer → pgvector → Search/Ask.

Live source и real Ollama имеют отдельную ручную политику и не входят в CI.

## Команды

```bash
make format
make lint
make typecheck
make test-unit
make test-integration
make test-e2e
```

Полный инфраструктурный запуск:

```bash
docker compose -f docker-compose.test.yml up -d
export DATABASE_URL=postgresql+asyncpg://tender_lens:tender_lens@localhost:55432/tender_lens_test
python -m alembic upgrade head
RUN_INTEGRATION=1 \
TEST_DATABASE_URL="$DATABASE_URL" \
TEST_NATS_URL=nats://localhost:54222 \
python -m pytest -q tests/integration tests/e2e
```

## CI jobs

| Job | Проверки |
|---|---|
| `quality` | black, flake8, unit/API |
| `integration` | clean migration, PostgreSQL/pgvector, NATS, integration/E2E |
| `container` | Compose validation и Docker build |

## Что считается успешным

- тест не отключён ради зелёного результата;
- дефект сопровождается regression test;
- unit tests не зависят от live network;
- migration применяется на чистую БД;
- E2E использует fixture и fake AI;
- CI не выполняет model pull;
- документация и code-map обновлены вместе с поведением.

## Локальная верификация поставки

Фактические результаты текущей поставки находятся в `docs/reports/`. Ограничения среды фиксируются явно: отсутствие Docker daemon или GitHub remote не подменяется бодрой выдумкой о зелёном облачном CI, как это иногда принято у менее стеснительных автоматов.
