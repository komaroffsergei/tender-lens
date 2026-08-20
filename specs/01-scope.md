# 01. Границы MVP

## 1. Входит в MVP

### 1.1 Сбор данных

- два адаптера: TED и UK Contracts Finder;
- асинхронный HTTP через `httpx.AsyncClient`;
- ограничение конкурентности через `asyncio.Semaphore`;
- таймауты, ограниченные повторы, exponential backoff, jitter;
- уважение `Retry-After`;
- режим `--once` и периодический цикл;
- курсор/состояние источника в таблице `sources`;
- загрузка доступных вложений потоково;
- ограничение размера файла;
- безопасные локальные имена;
- SHA-256 для вложений;
- сохранение исходного payload в JSONB.

### 1.2 Хранение и события

- один PostgreSQL с расширением `pgvector`;
- пять таблиц: `sources`, `tenders`, `attachments`, `chunks`, `api_keys`;
- один NATS JetStream stream;
- один subject `tender.changed.v1`;
- один durable consumer `INDEXER`;
- событие содержит только идентификатор и hash, а не PDF или весь payload;
- at-least-once обработка и идемпотентность по `indexed_hash`.

### 1.3 Индексация и AI

- извлечение текста из метаданных и форматов PDF с текстовым слоем, XML, HTML, JSON, TXT;
- чанкинг по абзацам до 1500 символов с overlap до 150;
- batch embeddings через Ollama;
- модель `qwen3-embedding:0.6b`, размер 1024;
- точный cosine search через `pgvector`;
- RAG-ответ через `qwen3:1.7b`;
- fake AI provider для CI и e2e.

### 1.4 API и интерфейс

- FastAPI;
- `X-API-Key`;
- CLI-команда создания API-ключа;
- fixed UTC-minute rate limiter в PostgreSQL;
- общий лимит для `/search` и `/ask`, по умолчанию 5 запросов в минуту;
- 429 с `Retry-After` и `X-RateLimit-*`;
- статический HTML/CSS/JS без npm и CDN;
- состояния loading, empty, success, validation error, 401, 429, 503.

### 1.5 Качество поставки

- один monorepo;
- один Python package;
- один Dockerfile и три роли;
- Docker Compose;
- Alembic;
- pytest unit/integration/e2e;
- black, flake8, mypy;
- GitHub Actions;
- README, алгоритм, архитектура, code-map, traceability, operations, trade-offs;
- MIT LICENSE;
- отдельная feature-ветка, развёрнутые коммиты, merge в `main`.

## 2. Не входит в MVP

- CAPTCHA solving, обход авторизации, proxy rotation или browser fingerprint evasion;
- Playwright/Selenium;
- OCR и распознавание сканов;
- DOCX, XLSX, архивы;
- предобработка сложных таблиц;
- Elasticsearch, Qdrant, ChromaDB;
- PostgreSQL FTS, hybrid search, RRF, reranker;
- HNSW/IVFFlat;
- Redis/RabbitMQ/Kafka/Celery/Taskiq;
- отдельный catalog-service и database-writer service;
- outbox/inbox и schema registry;
- отдельные базы на каждую роль;
- MinIO/S3;
- Angular/React/Vue/RxJS;
- WebSocket/SSE;
- пользовательская регистрация, роли и административная панель;
- CRUD источников через API;
- облачные LLM;
- Kubernetes, Prometheus, Grafana, OpenTelemetry;
- автоматическое развёртывание в публичный cloud.

## 3. Допустимые упрощения

1. Второй адаптер реализуется после полного вертикального сценария первого.
2. Если у live-источника нет доступного вложения, тесты используют fixture PDF; это не отменяет обязательную реализацию загрузчика.
3. Вложения хранятся в общем Docker volume, поскольку Compose работает на одном хосте.
4. API и indexer читают одну БД напрямую. Раздельное владение данными не моделируется.
5. Rate limiter использует fixed window. Boundary burst документируется как известный компромисс.
6. Поиск точный, без ANN-индекса, пока corpus мал и нет измеренной проблемы производительности.

## 4. Правило против расползания объёма

Функция не реализуется, если она:

- не нужна для acceptance criteria;
- не закрывает найденный дефект;
- не требуется безопасностью;
- не снижает сложность уже существующего решения.

Любое расширение требует ADR и оценки влияния на сроки, тесты и документацию.
