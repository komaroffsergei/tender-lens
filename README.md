# TenderLens

Асинхронный мониторинг открытых закупок с фоновой индексацией через NATS JetStream, хранением embeddings в PostgreSQL/pgvector и локальным grounded RAG через Ollama.

![Архитектура TenderLens](docs/diagrams/architecture.png)

## Что реализовано

Основное тестовое задание проекта — **№7, асинхронный парсер/скрапер закупок**. Решение дополнено практическими частями заданий №3, №8 и №9:

- два адаптера источников: TED и UK Contracts Finder;
- асинхронный `httpx`-клиент с лимитом конкурентности, задержкой, jitter, retry, `Retry-After` и запретом redirect на неизвестный host;
- нормализация обоих источников в единый Pydantic-контракт `TenderRecordV1`;
- инкрементальный `UPSERT` закупок в PostgreSQL и детерминированный `content_hash`;
- потоковое скачивание вложений с лимитом размера, безопасным именем и SHA-256;
- одно долговечное событие `tender.changed.v1` в NATS JetStream;
- извлечение текста из PDF/XML/HTML/JSON/TXT, чанкинг и batch embeddings;
- точный cosine search через `pgvector`;
- grounded `/ask`, который генерирует ответ только по найденным фрагментам;
- API-key аутентификация и общий PostgreSQL fixed-window limiter для `/search` и `/ask`;
- статический адаптивный UI без npm, CDN и frontend-фреймворков;
- Docker Compose, Alembic, GitHub Actions, unit/API/integration/E2E-тесты;
- MIT License.

Проект намеренно не изображает распределённую империю из десятка пустых сервисов. Один Python package запускается в трёх ролях: `crawler`, `indexer`, `api`.

## Архитектура в одной схеме

```text
TED / Contracts Finder
          │
          ▼
      crawler
  httpx + adapters
  PostgreSQL + files
          │
          ▼
 NATS JetStream
 tender.changed.v1
          │
          ▼
       indexer
 extract → chunk → embed
          │
          ▼
 PostgreSQL + pgvector
          ▲
          │
 Browser → FastAPI → search / grounded RAG → Ollama
```

Подробности: [`docs/architecture.md`](docs/architecture.md), [`docs/algorithm.md`](docs/algorithm.md).

## Состав контейнеров

| Контейнер | Назначение |
|---|---|
| `postgres` | метаданные, API-ключи, chunks и `VECTOR(1024)` |
| `nats` | долговечная очередь фоновой индексации |
| `migrate` | одноразовый `alembic upgrade head` |
| `crawler` | TED/Contracts Finder, вложения, NATS publish |
| `indexer` | durable consumer, extraction, embeddings, index update |
| `api` | REST API, UI, auth, limiter, search и RAG |
| `ollama` | опциональный профиль `ai` для реальных моделей |
| `model-init` | опциональная загрузка моделей Ollama |

`crawler`, `indexer`, `api` и `migrate` используют **один Docker image**.

## Быстрый запуск: детерминированный fake AI

Требуются Docker Engine, Docker Compose v2 и `curl`.

```bash
cp .env.example .env
docker compose up --build -d
```

По умолчанию `AI_MODE=fake`: embeddings и ответы детерминированы, поэтому систему можно проверить без загрузки моделей.

Создание API-ключа:

```bash
docker compose run --rm api \
  python -m tender_lens.cli create-api-key --name demo --limit 5
```

Открыть:

- UI: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`
- readiness: `http://localhost:8000/health/ready`
- NATS monitoring: `http://localhost:8222`

## Полный fixture-demo

Команда поднимает PostgreSQL/NATS/API/indexer, загружает две fixture-закупки, индексирует их, выполняет Search, Ask и проверяет, что шестой общий запрос получает `429`:

```bash
make demo-fake
```

Сценарий не обращается к TED, Contracts Finder или Ollama.

## Реальный локальный AI через Ollama

В `.env` установить:

```dotenv
AI_MODE=live
```

Затем:

```bash
docker compose --profile ai up --build -d
```

Профиль `ai` запускает Ollama и одноразовый `model-init`, который загружает:

```text
qwen3-embedding:0.6b
qwen3:1.7b
```

Размер embedding зафиксирован контрактом и миграцией: `1024`.

## Одноразовый crawl

TED:

```bash
docker compose run --rm crawler \
  python -m tender_lens.crawler --once --source ted --max-items 5
```

Contracts Finder:

```bash
docker compose run --rm crawler \
  python -m tender_lens.crawler --once --source contracts_finder --max-items 5
```

Оба источника:

```bash
docker compose run --rm crawler \
  python -m tender_lens.crawler --once --source all --max-items 5
```

Crawler не обходит CAPTCHA, авторизацию или технические запреты. Реализованы только базовые задержки, ограничение конкурентности и корректная обработка временных ошибок.

## API

Все пользовательские endpoints требуют `X-API-Key`.

### Поиск

```bash
curl -sS http://localhost:8000/api/v1/search \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: tl_...' \
  -d '{"query":"server storage warranty","limit":5}'
```

### Grounded RAG

```bash
curl -sS http://localhost:8000/api/v1/ask \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: tl_...' \
  -d '{"query":"Какие серверы и гарантии требуются?","limit":5}'
```

### Карточка закупки

```bash
curl -sS http://localhost:8000/api/v1/tenders/<UUID> \
  -H 'X-API-Key: tl_...'
```

Rate-limit headers:

```text
X-RateLimit-Limit
X-RateLimit-Remaining
X-RateLimit-Reset
Retry-After
```

Подробнее: [`docs/api-examples.md`](docs/api-examples.md).

## CLI

```bash
python -m tender_lens.cli create-api-key --name demo --limit 5
python -m tender_lens.cli list-api-keys
python -m tender_lens.cli disable-api-key demo
python -m tender_lens.cli seed-demo --fixture-dir examples/fixtures
```

Открытое значение API-ключа показывается один раз. В базе хранится только SHA-256.

## Локальная разработка

Python 3.12+:

```bash
python -m pip install -r requirements-dev.lock
cp .env.example .env
```

Проверки без инфраструктуры:

```bash
make lint
make typecheck
make test-unit
```

Интеграционные тесты требуют PostgreSQL с `pgvector` и NATS. Канонический вариант:

```bash
docker compose -f docker-compose.test.yml up -d
DATABASE_URL=postgresql+asyncpg://tender_lens:tender_lens@localhost:55432/tender_lens_test \
  python -m alembic upgrade head
RUN_INTEGRATION=1 \
TEST_DATABASE_URL=postgresql+asyncpg://tender_lens:tender_lens@localhost:55432/tender_lens_test \
TEST_NATS_URL=nats://localhost:54222 \
  python -m pytest -q tests/integration tests/e2e
```

## CI/CD

`.github/workflows/ci.yml` запускается на push и pull request:

1. `black --check`;
2. `flake8`;
3. unit/API tests;
4. PostgreSQL/pgvector migration;
5. NATS integration tests;
6. fixture E2E;
7. Docker build;
8. `docker compose config`.

`mypy` оставлен отдельной локальной проверкой (`make typecheck`), но не блокирует обязательный CI: формальное требование тестового задания относится к `black` и `flake8`.

CI не обращается к live-источникам и не загружает Ollama-модели. Люди иногда называют сетевую случайность тестированием, но здесь решено не участвовать в этом обряде.

## Ограничения MVP

- PDF индексируется только при наличии текстового слоя; OCR отсутствует.
- DOC/DOCX/XLS/XLSX/архивы сохраняются, но не индексируются.
- Поиск только semantic, без PostgreSQL FTS/RRF/reranker.
- Exact vector scan без HNSW/IVFFlat подходит для небольшого демонстрационного корпуса.
- Fixed UTC-minute limiter допускает burst на границе двух минут.
- Общие PostgreSQL и Docker volume сознательно упрощают развёртывание на одном host.
- Изменение содержимого файла по прежнему URL обнаруживается только при изменении метаданных закупки или повторной неуспешной загрузке.

Обоснование: [`docs/tradeoffs.md`](docs/tradeoffs.md).

## Документация

- [Архитектура](docs/architecture.md)
- [Алгоритмы](docs/algorithm.md)
- [API и примеры](docs/api-examples.md)
- [Тестирование](docs/testing.md)
- [Эксплуатация](docs/operations.md)
- [Code map](docs/code-map.md)
- [Traceability](docs/traceability.md)
- [Компромиссы](docs/tradeoffs.md)
- [Решения](docs/decisions.md)
- [Отчёт о поставке](docs/final-report.md)
- [Шпаргалка к собеседованию](docs/INTERVIEW_CHEATSHEET.md)

## Git-процесс

В архиве сохранена история Git:

- спецификации и исходные материалы инициализированы в `main`;
- реализация выполнена в `feature/tender-lens`;
- изменения разбиты на содержательные commits;
- финальная версия сливается merge commit-ом и помечается `v0.1.0`.

Для переноса истории отдельно поставляется Git bundle.

## License

MIT, см. [`LICENSE`](LICENSE).
