# TenderLens

[![CI](https://github.com/komaroffsergei/tender-lens/actions/workflows/ci.yml/badge.svg)](https://github.com/komaroffsergei/tender-lens/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Асинхронный сервис мониторинга открытых закупок на Python. Основное тестовое задание — **№7: асинхронный парсер/скрапер сайтов**. Сервис получает закупки из TED и UK Contracts Finder, скачивает вложения и сохраняет нормализованные метаданные в PostgreSQL.

RAG-поиск, API rate limiter и контейнеризация — дополнительные возможности, демонстрирующие части заданий №3, №8 и №9. Проект не заявляет выполнение остальных заданий вакансии.

![Архитектура TenderLens](docs/diagrams/architecture.png)

## Соответствие заданию №7

- два открытых источника: TED Search API и Contracts Finder OCDS Search API;
- `asyncio` и `httpx` с ограниченной конкурентностью;
- базовая задержка с jitter, timeout, retry и поддержка `Retry-After`;
- ручная проверка каждого redirect и закрытый allowlist официальных host;
- потоковая загрузка вложений с ограничением размера;
- безопасные имена файлов, атомарная запись и SHA-256;
- PostgreSQL, идемпотентный UPSERT и cursor источника;
- ошибка одной записи, вложения или источника не останавливает остальные;
- fixture-тесты не зависят от доступности внешних сайтов.

Параллельность реализована асинхронными задачами внутри одного процесса. Это позволяет одновременно обрабатывать сетевые операции без создания OS-потока на каждый запрос.

## Архитектура

Один Python-пакет и Docker image запускаются в трёх ролях:

```text
TED / Contracts Finder
          │
          ▼
       crawler ──► PostgreSQL + attachment volume
          │
          ▼
 NATS JetStream: tender.changed.v1
          │
          ▼
       indexer ──► PostgreSQL / pgvector
                          ▲
                          │
 Browser ──► FastAPI ──► Search / grounded RAG
```

Состав Compose:

| Сервис | Назначение |
|---|---|
| `postgres` | Метаданные, API-ключи и `VECTOR(1024)` |
| `nats` | Durable очередь фоновой индексации |
| `migrate` | Применение Alembic migration |
| `crawler` | Источники, вложения, UPSERT и публикация события |
| `indexer` | Извлечение текста, embeddings и pgvector |
| `api` | FastAPI, UI, auth, limiter, Search и Ask |
| `ollama` | Опциональный локальный AI-профиль |

Подробности: [архитектура](docs/architecture.md) и [алгоритмы](docs/algorithm.md).

## Быстрый запуск

Требуются Docker Engine и Docker Compose.

```bash
cp .env.example .env
docker compose up --build -d
```

Для PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

По умолчанию используется `AI_MODE=fake`: модель не скачивается, embeddings и ответы детерминированы.

Создать API-ключ:

```bash
docker compose run --rm api \
  python -m tender_lens.cli create-api-key --name demo --limit 5
```

Открыть:

- UI: <http://localhost:8000>
- OpenAPI: <http://localhost:8000/docs>
- readiness: <http://localhost:8000/health/ready>
- NATS monitoring: <http://localhost:8222>

Остановить сервисы:

```bash
docker compose down
```

## Демонстрация crawler

Одноразово получить до пяти записей TED:

```bash
docker compose run --rm crawler \
  python -m tender_lens.crawler --once --source ted --max-items 5
```

Contracts Finder:

```bash
docker compose run --rm crawler \
  python -m tender_lens.crawler --once --source contracts_finder --max-items 5
```

Детерминированный fixture-demo полного конвейера:

```bash
make demo-fake
```

Сценарий загружает две локальные fixture-закупки, индексирует их, выполняет Search и Ask и проверяет ответ 429 на шестой запрос.

Crawler не обходит CAPTCHA, авторизацию или технические ограничения. Он использует только открытые API и вежливую сетевую политику.

## API

Все прикладные endpoints требуют `X-API-Key`.

```bash
curl http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tl_..." \
  -d '{"query":"server storage warranty","limit":5}'
```

```bash
curl http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: tl_..." \
  -d '{"query":"Какие серверы и гарантии требуются?","limit":5}'
```

- `/search` принимает `limit` от 1 до 10.
- `/ask` использует не более пяти источников.
- Результаты с cosine similarity ниже `MIN_RELEVANCE_SCORE` не возвращаются.
- При отсутствии релевантного контекста LLM не вызывается.
- Один API-ключ может выполнить пять общих запросов Search/Ask за UTC-минуту.
- `Retry-After` возвращается только с HTTP 429.

Примеры контрактов: [docs/api-examples.md](docs/api-examples.md).

## Реальный Ollama

В `.env`:

```dotenv
AI_MODE=live
```

Запуск:

```bash
docker compose --profile ai up --build -d
```

Профиль загружает `qwen3-embedding:0.6b` и `qwen3:1.7b`. Размерность embedding зафиксирована миграцией как 1024.

## Проверки

Локальные проверки Python:

```bash
python -m pip install -r requirements-dev.lock
python -m black --check src tests migrations
python -m flake8 src tests
python -m mypy src
python -m pytest -q tests/unit tests/api
```

Интеграционные и E2E-тесты:

```bash
docker compose -f docker-compose.test.yml up -d
DATABASE_URL=postgresql+asyncpg://tender_lens:tender_lens@localhost:55432/tender_lens_test \
  python -m alembic upgrade head
RUN_INTEGRATION=1 \
TEST_DATABASE_URL=postgresql+asyncpg://tender_lens:tender_lens@localhost:55432/tender_lens_test \
TEST_NATS_URL=nats://localhost:54222 \
  python -m pytest -q
```

GitHub Actions проверяет Black, Flake8, MyPy, unit/API, PostgreSQL/pgvector, настоящий NATS, полный fixture E2E, downgrade/upgrade migration, Docker build, Compose config и запуск всех трёх ролей. Live API и Ollama не входят в обязательный CI.

## Ограничения

- PDF без текстового слоя требует OCR, которого в MVP нет.
- DOCX/XLSX и архивы скачиваются, но не индексируются.
- Векторный поиск использует exact scan без HNSW/IVFFlat и рассчитан на демонстрационный объём.
- Fixed-window limiter допускает burst на границе двух минут.
- Live-smoke внешних API выполняется отдельно и может зависеть от доступности источника.

## Документация

- [Логика и алгоритмы](docs/algorithm.md)
- [Архитектура](docs/architecture.md)
- [Тестирование](docs/testing.md)
- [Эксплуатация](docs/operations.md)
- [Traceability задания](docs/traceability.md)
- [Карта кода](docs/code-map.md)
- [Компромиссы](docs/tradeoffs.md)
- [Безопасность](SECURITY.md)

## License

Проект распространяется по лицензии [MIT](LICENSE).
