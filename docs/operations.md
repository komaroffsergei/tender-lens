# Эксплуатация TenderLens

## Конфигурация

Все поддержанные переменные перечислены в `.env.example` и типизированы в `src/tender_lens/config.py`.

Критические:

```dotenv
DATABASE_URL=postgresql+asyncpg://...
NATS_URL=nats://nats:4222
AI_MODE=fake|live
OLLAMA_URL=http://ollama:11434
EMBEDDING_MODEL=qwen3-embedding:0.6b
EMBEDDING_DIMENSIONS=1024
GENERATION_MODEL=qwen3:1.7b
ATTACHMENTS_DIR=/data/attachments
MAX_ATTACHMENT_BYTES=20971520
```

`EMBEDDING_DIMENSIONS` не является произвольной runtime-настройкой: миграция хранит `VECTOR(1024)`, поэтому Pydantic принимает только `1024`.

## Первый запуск

```bash
cp .env.example .env
docker compose up --build -d
```

`migrate` завершается до запуска прикладных ролей.

Проверка:

```bash
curl -fsS http://localhost:8000/health/live
curl -fsS http://localhost:8000/health/ready
```

## Управление ключами

```bash
docker compose run --rm api python -m tender_lens.cli create-api-key --name demo --limit 5
docker compose run --rm api python -m tender_lens.cli list-api-keys
docker compose run --rm api python -m tender_lens.cli disable-api-key demo
```

Открытый ключ нельзя восстановить из БД. При утрате создаётся новый.

## Диагностика ingestion

```bash
docker compose logs -f crawler
docker compose logs -f indexer
docker compose logs -f nats
```

Pending:

```sql
SELECT id, title, content_hash, indexed_hash, index_status, last_error
FROM tenders
WHERE index_status IN ('pending', 'failed')
ORDER BY updated_at;
```

`pending` будет переопубликован следующим crawler cycle. `failed` означает, что индексатор записал typed error; JetStream message остаётся без ACK и повторяется.

## Проверка NATS

Monitoring endpoint:

```text
http://localhost:8222
```

Ожидаются stream `TENDERS`, subject `tender.changed.v1`, durable consumer `INDEXER`.

## Смена embedding model

Нельзя смешивать в одной колонке векторы разных пространств. При смене модели:

1. сохранить backup;
2. убедиться, что новая модель отдаёт 1024 dimensions;
3. изменить `EMBEDDING_MODEL`;
4. поставить существующие tenders в `pending`, обнулить `indexed_hash`;
5. позволить crawler переопубликовать события;
6. проверить Search benchmark.

## Backup

Для демонстрационной среды:

```bash
docker compose exec -T postgres \
  pg_dump -U tender_lens -d tender_lens -Fc > tender-lens.dump
```

Вложения находятся в volume `attachments_data`, NATS state в `nats_data`.

## Остановка

```bash
docker compose down
```

Удаление всех данных выполняется только намеренно:

```bash
docker compose down -v
```

## Live source policy

- максимум 5 записей в smoke-run;
- не запускать live источники в CI;
- соблюдать delay и concurrency limits;
- не обходить CAPTCHA/authorization;
- не коммитить скачанные файлы;
- при изменении внешнего contract сначала обновить fixture и adapter tests.
