# 10. План реализации по минимальным проверяемым этапам

## Общий gate каждого этапа

Каждый этап состоит минимум из двух коммитов:

1. `feat|chore(stage-XX): ...` — минимальная реализация;
2. `test(stage-XX): ... and sync documentation` — тесты, исправления и документация.

После каждого commit:

1. `git push`;
2. найти GitHub Actions run;
3. дождаться результата;
4. при ошибке сделать отдельный `fix(stage-XX): ...` commit;
5. переходить дальше только при green CI.

В конце каждого этапа обновляются:

- `docs/progress.md`;
- `docs/code-map.md`;
- `docs/traceability.md`;
- релевантные README/docs;
- test IDs и фактические команды.

## Stage 00 — SDD bootstrap и GitHub

### Реализация

- прочитать весь pack;
- проверить/создать Git repository;
- добавить MIT LICENSE, `.gitignore`, initial README;
- положить specs, schemas, diagrams, prototype и AGENTS;
- создать initial `main` commit;
- создать/проверить публичный GitHub repository;
- push `main`;
- создать `feature/tender-lens`.

### Тесты/gate

- BOOT-001..003;
- JSON Schema validation;
- отсутствие secrets;
- links/files check.

### Коммиты

```text
chore(init): add SDD specifications and project guardrails
```

Stage 00 является исключением из правила двух commit: он формирует исходную точку. Следующий stage сразу добавляет CI.

## Stage 01 — Python package и baseline CI

### Реализация

- `pyproject.toml`, lock-file;
- package skeleton и entry points;
- black/flake8/mypy/pytest config;
- простая GitHub Actions job quality;
- Makefile: `format`, `lint`, `typecheck`, `test-unit`, `ci`.

### Тесты

PKG-001..002, CONF-001..003, LOG-001, CI-001..004.

### Gate

- clean install;
- imports;
- quality CI green.

## Stage 02 — Docker Compose infrastructure

### Реализация

- один multi-role Dockerfile;
- Compose: postgres(pgvector), nats(`-js`), ollama, api, crawler, indexer;
- volumes и healthchecks;
- `.env.example`;
- `docker-compose.test.yml`.

### Тесты

DOCKER-001..004, INFRA-001..003.

### Gate

- image build;
- compose config;
- infra health;
- три role commands запускаются.

## Stage 03 — PostgreSQL migration

### Реализация

- Alembic;
- extension vector;
- пять таблиц, constraints/indexes;
- async DB session.

### Тесты

DB-001..008.

### Gate

- upgrade/downgrade/upgrade на чистой БД;
- schema соответствует `04-data-model.md`.

## Stage 04 — Pydantic contracts и persistence

### Реализация

- TenderRecordV1, AttachmentRecordV1, event/API schemas;
- canonical hash;
- source create/get;
- tender upsert;
- attachment metadata upsert;
- API-key persistence and CLI generation.

### Тесты

HASH-001..004, UPSERT-001..003, APIKEY-DB-001..002, CONTRACT-001..005, SCHEMA-001.

### Gate

- new/unchanged/changed behavior доказано;
- checked-in schemas не расходятся.

## Stage 05 — TED adapter как чистый источник

### Реализация

- SourceAdapter Protocol;
- shared HTTP retry/rate policy;
- TedAdapter request/response mapping;
- pagination limits;
- fixtures.

Не сохранять в БД и не скачивать файлы на этом этапе.

### Тесты

TED-001..007, HTTP-001..005, CONC-001, ADAPTER contract subset.

### Gate

- только fixture tests обязательны;
- один optional live smoke фиксируется отдельно.

## Stage 06 — crawler orchestration и attachments

### Реализация

- adapter → upsert;
- cursor transaction boundary;
- async attachment downloader;
- shared volume;
- `crawler --once` и loop;
- один source failure не останавливает остальные.

Пока без NATS: new/changed остаются `pending`.

### Тесты

CURSOR-001..002, CRAWL-001..004, FILE-001..009, HTTP-006..008.

### Gate

- fixture source полностью сохраняется;
- повторный crawl идемпотентен.

## Stage 07 — NATS JetStream event delivery

### Реализация

- stream/consumer setup;
- checked event schema;
- publish after commit;
- pending republisher;
- minimal indexer consumer skeleton с fake handler;
- explicit ACK.

### Тесты

NATS-001..011.

### Gate

- redelivery и pending recovery доказаны на реальном NATS.

## Stage 08 — extraction, chunking, fake indexer

### Реализация

- metadata/PDF/XML/HTML/JSON/TXT extraction;
- safe parsers;
- deterministic chunking;
- deterministic fake embedding provider;
- atomic chunk replacement;
- indexed_hash idempotency.

### Тесты

EXTRACT-001..008, CHUNK-001..006, INDEX-001..005.

### Gate

- NATS event приводит к ready tender и chunks без Ollama.

## Stage 09 — Ollama embeddings и exact vector search

### Реализация

- `/api/embed` batch client;
- vector dimension validation;
- live/fake provider selection;
- exact cosine repository/service;
- optional live smoke.

### Тесты

OLLAMA-EMB-001..005, SEARCH-001..006, LIVE-EMB-001 manual.

### Gate

- deterministic corpus выдаёт ожидаемый top-k;
- CI не требует Ollama model.

## Stage 10 — Contracts Finder adapter

### Реализация

- OCDS mapping;
- cursor pagination;
- 403 cooldown;
- source configuration;
- common adapter contract tests.

### Тесты

CF-001..008, ADAPTER-001..003.

### Gate

- оба источника работают через одну orchestration path.

## Stage 11 — FastAPI base и API-key authentication

### Реализация

- application factory;
- unified errors/request ID;
- health endpoints;
- tender details endpoint;
- X-API-Key dependency;
- static files mounting placeholder.

### Тесты

API-HEALTH-001..004, AUTH-001..006, API-TENDER-001..002, API-ERR-001.

### Gate

- auth и sanitized response доказаны;
- rate limit пока не подключён.

## Stage 12 — PostgreSQL limiter и Search API

### Реализация

- injectable clock;
- row-lock fixed-window limiter;
- headers;
- SearchRequest/SearchResponse;
- `/search` использует embedding + exact repository.

### Тесты

RATE-001..008, API-SEARCH-001..004.

### Gate

- 10 concurrent requests дают ровно 5 successful;
- 6-й последовательный даёт 429.

## Stage 13 — RAG `/ask`

### Реализация

- grounded prompt;
- generation client;
- no-context short circuit;
- source construction in code;
- dependency error mapping.

### Тесты

RAG-001..010, LIVE-RAG-001 manual.

### Gate

- fake model не может добавить source вне retrieval;
- no data не вызывает model.

## Stage 14 — Static UI

### Реализация

- финальные HTML/CSS/JS;
- sessionStorage key;
- Search/Ask modes;
- all states;
- responsive layout matching reference.

### Тесты

UI-001..011.

### Gate

- screenshot desktop/mobile;
- no npm/CDN/hardcoded key/unsafe rendering.

## Stage 15 — E2E, документация, PR и release

### Реализация

- full fake-AI e2e;
- integration job in GitHub Actions;
- Docker job;
- README/operations/algorithm/code-map/traceability/interview cheat sheet;
- manual demo where available;
- PR, merge, tag.

### Тесты

E2E-001..007, MIG-001..002, CI-001..008, DOC-001..003, GIT-001..003, RELEASE-001.

### Gate

- `make ci` local green;
- feature CI green;
- PR CI green;
- merge/main CI green or exact blocker documented.
