# Эксплуатация

## Конфигурация

Все переменные перечислены в `.env.example` и валидируются в `Settings`.

Ключевые настройки:

```dotenv
DATABASE_URL=postgresql+asyncpg://tender_lens:tender_lens@postgres:5432/tender_lens
NATS_URL=nats://nats:4222
AI_MODE=fake
EMBEDDING_DIMENSIONS=1024
MIN_RELEVANCE_SCORE=0.20
ATTACHMENTS_DIR=/data/attachments
MAX_ATTACHMENT_BYTES=20971520
CRAWL_MAX_CONCURRENCY=3
ATTACHMENT_MAX_CONCURRENCY=2
NATS_ACK_WAIT_SECONDS=300
NATS_MAX_DELIVER=5
```

`EMBEDDING_DIMENSIONS` читается из строкового env, но допускает только 1024, потому что migration создаёт `VECTOR(1024)`.

## Первый запуск

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
```

`migrate` должен завершиться с кодом 0, а `api` — перейти в healthy.

## API-ключ

```bash
docker compose run --rm api \
  python -m tender_lens.cli create-api-key --name demo --limit 5
```

Открытый ключ выводится один раз. В PostgreSQL хранится только SHA-256.

## Диагностика

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
docker compose logs --tail=200 crawler indexer api
```

Readiness проверяет PostgreSQL и выбранный AI provider. NATS доступен через monitoring endpoint на порту 8222.

## Live crawl

```bash
docker compose run --rm crawler \
  python -m tender_lens.crawler --once --source all --max-items 5
```

Live-smoke не является частью CI. При изменении внешнего API сначала обновляются сохранённые fixtures и contract tests.

## Резервное копирование

Минимально необходимо сохранять:

- PostgreSQL;
- volume `attachments_data`;
- `.env` без публикации в Git.

JetStream хранит события для восстановления фоновой обработки, но не заменяет резервную копию PostgreSQL.
