# 14. Эксплуатация и команды

## 1. Переменные среды

Минимальный набор:

```dotenv
APP_ENV=local
LOG_LEVEL=INFO
DATABASE_URL=postgresql+asyncpg://tender_lens:tender_lens@postgres:5432/tender_lens
NATS_URL=nats://nats:4222
OLLAMA_URL=http://ollama:11434
EMBEDDING_MODEL=qwen3-embedding:0.6b
EMBEDDING_DIMENSIONS=1024
GENERATION_MODEL=qwen3:1.7b
ATTACHMENTS_DIR=/data/attachments
MAX_ATTACHMENT_BYTES=20971520
CRAWL_INTERVAL_SECONDS=3600
CRAWL_MAX_CONCURRENCY=3
ATTACHMENT_MAX_CONCURRENCY=2
HTTP_MAX_ATTEMPTS=3
HTTP_BASE_DELAY_SECONDS=0.5
HTTP_JITTER_SECONDS=0.5
DEFAULT_RATE_LIMIT_PER_MINUTE=5
AI_MODE=live
```

Тесты используют отдельные значения и `AI_MODE=fake`.

## 2. Канонические Make targets

```text
make install
make format
make lint
make typecheck
make test-unit
make test-integration
make test-e2e
make test
make migrate
make compose-up
make compose-down
make ci
make live-smoke
```

## 3. Первый запуск

```bash
cp .env.example .env
docker compose up --build -d postgres nats ollama
docker compose run --rm api alembic upgrade head
docker compose exec ollama ollama pull qwen3-embedding:0.6b
docker compose exec ollama ollama pull qwen3:1.7b
docker compose run --rm api python -m tender_lens.cli create-api-key --name demo --limit 5
docker compose up -d api indexer crawler
```

Открыть UI на documented port.

## 4. Одноразовый crawl

```bash
docker compose run --rm crawler python -m tender_lens.crawler --once --source ted --max-items 5
```

Для второго источника:

```bash
docker compose run --rm crawler python -m tender_lens.crawler --once --source contracts_finder --max-items 5
```

## 5. Fake demo

Должна существовать команда, которая не зависит от сети и моделей:

```bash
make demo-fake
```

Она:

1. поднимает test infra;
2. применяет миграции;
3. запускает fixture source;
4. выполняет crawler;
5. публикует/обрабатывает NATS event;
6. индексирует fake embeddings;
7. создаёт demo key;
8. выполняет Search, Ask и 429 assertions;
9. печатает URL UI и summary.

## 6. Диагностика

### Tender застрял `pending`

Проверить:

```bash
docker compose logs crawler
docker compose logs nats
docker compose exec postgres psql ... -c "select id,index_status,last_error from tenders where index_status='pending';"
```

Следующий crawler cycle должен republish pending.

### Tender `failed`

Проверить indexer logs по tender/event ID. Старые chunks должны сохраниться при failed reindex.

### API 503

Проверить `/health/ready`, PostgreSQL и Ollama health. Не маскировать dependency failure пустым ответом.

### 429

Использовать `Retry-After`; fixed window сбрасывается на границе следующей UTC-минуты.

## 7. Backup/cleanup для demo

```bash
docker compose down
docker compose down -v  # только если намеренно удалить DB, NATS state и attachments
```

Не выполнять `-v` автоматически в обычном shutdown.

## 8. Live source policy

- live smoke ограничен 5 записями;
- задержки включены;
- не запускать live source в CI;
- не коммитить скачанные live attachments;
- записывать дату/результат live smoke в final report;
- если API изменился, обновить adapter fixture/spec и сделать отдельный commit.
