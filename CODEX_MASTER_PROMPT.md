# Мастер-промпт Codex: самостоятельная реализация TenderLens

## Роль

Ты — ведущий разработчик и исполнитель Spec-Driven Development. Твоя задача — самостоятельно создать, протестировать, задокументировать и опубликовать в GitHub законченное тестовое приложение TenderLens.

Работай от начала до конца без ожидания дополнительных указаний. Не задавай вопросы, если ответ однозначно следует из спецификаций или можно выбрать более простой вариант без изменения требований. Задавай вопрос только при настоящем блокере, который нельзя безопасно разрешить: отсутствие GitHub-авторизации, невозможность запустить Docker, конфликт с существующей историей репозитория либо недоступность обязательного секрета. Даже в этом случае сначала выполни всё, что не зависит от блокера, затем создай `BLOCKERS.md`.

Никаких обещаний «сделаю позже», псевдоуспешных отчётов и декоративных файлов. Каждый завершённый этап должен иметь работающий код, тесты, документацию, коммиты, push и зелёный CI.

## 1. Прочитай проект до действий

Перед изменениями:

1. прочитай `AGENTS.md` полностью;
2. прочитай все файлы `specs/*.md` по порядку;
3. прочитай JSON Schema из `schemas/`;
4. изучи Mermaid-схемы, PNG-макеты и `prototype/`;
5. выполни `git status`, `git log --oneline -20`, `git remote -v`;
6. проверь `gh auth status`, `docker version`, `docker compose version`;
7. составь внутренний план строго по `specs/10-implementation-plan.md`;
8. не начинай следующий этап до прохождения ворот текущего.

## 2. Цель продукта

Создай минимальную систему мониторинга и интеллектуального поиска по закупкам:

1. `crawler` асинхронно получает новые и изменённые закупки из двух открытых источников через адаптеры:
   - TED Search API;
   - UK Contracts Finder OCDS Search API.
2. Оба адаптера возвращают одну Pydantic-модель `TenderRecordV1`.
3. `crawler` сохраняет нормализованные метаданные и сведения о вложениях в PostgreSQL, скачивает доступные вложения в общий volume и при новом/изменённом тендере публикует одно событие `tender.changed.v1` в NATS JetStream.
4. `indexer` получает событие, читает сохранённый тендер, извлекает текст из метаданных и поддерживаемых вложений, режет его на чанки, получает embeddings через Ollama и сохраняет чанки в PostgreSQL/pgvector.
5. `api` предоставляет поиск по cosine similarity и RAG-ответ по найденным фрагментам, проверяет `X-API-Key` и ограничивает пользователя пятью запросами в минуту через атомарный fixed-window limiter в PostgreSQL.
6. FastAPI раздаёт простой статический HTML/CSS/JavaScript-интерфейс без frontend-фреймворка.
7. Всё запускается через Docker Compose и проверяется GitHub Actions.

## 3. Соответствие тестовому заданию

Основным считается задание №7: асинхронный сбор закупок, базовые задержки, загрузка вложений и сохранение метаданных в PostgreSQL.

Расширения:

- RAG и pgvector демонстрируют логику задания №3;
- API key, лимит 5 запросов/минуту и HTTP 429 демонстрируют логику задания №8;
- Docker Compose и GitHub Actions демонстрируют контейнеризацию и CI из задания №9.

В README прямо укажи, что выбранным заданием является №7, а остальные возможности — расширения одной законченной реализации. Не заявляй буквальное выполнение четырёх независимых заданий.

## 4. Жёсткие границы

Реализуй только согласованный объём.

### Обязательно

- один monorepo;
- один Python package;
- один Dockerfile для `crawler`, `indexer`, `api`;
- FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, asyncpg;
- httpx;
- nats-py и JetStream;
- PostgreSQL с pgvector;
- pypdf;
- Ollama через HTTP;
- pytest, pytest-asyncio, respx;
- black, flake8, mypy;
- статический UI;
- MIT LICENSE;
- русская документация и содержательные комментарии;
- английские идентификаторы;
- CI на push и pull request.

### Запрещено в MVP

- Redis;
- RabbitMQ/Kafka;
- отдельный `catalog-service`;
- отдельный сервис только для записи в БД;
- отдельные физические базы на роль;
- MinIO/S3;
- Angular/React/Vue/RxJS;
- Playwright/Selenium;
- LangChain/LlamaIndex;
- Elasticsearch/Qdrant/Chroma;
- hybrid search, FTS, RRF, reranker;
- HNSW/IVFFlat до появления измеренной необходимости;
- OCR;
- DOCX/XLSX/ZIP/RAR;
- NATS request/reply для API;
- сложная ролевая модель пользователей;
- CRUD источников через API;
- WebSocket/SSE;
- Prometheus/Grafana/OpenTelemetry;
- Kubernetes.

Если считаешь запрещённый элемент необходимым, сначала докажи невозможность выполнить конкретное требование текущим стеком и зафиксируй решение в ADR. Предпочитай не добавлять.

## 5. Архитектура

Прикладные роли:

```text
crawler  -> PostgreSQL + attachment volume
crawler  -> NATS JetStream: tender.changed.v1
indexer  <- NATS JetStream
indexer  -> PostgreSQL/pgvector + Ollama
api      -> PostgreSQL/pgvector + Ollama
browser  -> HTTP -> api
```

NATS применяется только для отделения быстрого получения данных от медленной фоновой индексации. API выполняет прямой SQL-поиск в pgvector и прямой HTTP-вызов Ollama. Не протаскивай пользовательский запрос через NATS.

Используй один PostgreSQL-контейнер и одну схему приложения. Общая база — сознательный MVP-компромисс, описанный в `specs/15-tradeoffs.md`.

## 6. Структура репозитория

Соблюдай следующую форму без дополнительных слоёв ради самих слоёв:

```text
.
├── AGENTS.md
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock или иной один lock-файл
├── Dockerfile
├── docker-compose.yml
├── docker-compose.test.yml
├── Makefile
├── .env.example
├── alembic.ini
├── migrations/
├── src/tender_lens/
│   ├── config.py
│   ├── logging.py
│   ├── db.py
│   ├── models.py
│   ├── schemas.py
│   ├── storage.py
│   ├── nats.py
│   ├── ai.py
│   ├── files.py
│   ├── cli.py
│   ├── crawler/
│   │   ├── base.py
│   │   ├── ted.py
│   │   ├── contracts_finder.py
│   │   ├── service.py
│   │   └── __main__.py
│   ├── indexer/
│   │   ├── extract.py
│   │   ├── chunk.py
│   │   ├── service.py
│   │   └── __main__.py
│   ├── api/
│   │   ├── auth.py
│   │   ├── rate_limit.py
│   │   ├── routes.py
│   │   └── main.py
│   └── web/
│       ├── index.html
│       ├── app.js
│       └── styles.css
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── specs/
├── docs/
│   ├── architecture.md
│   ├── algorithm.md
│   ├── code-map.md
│   ├── traceability.md
│   ├── progress.md
│   ├── decisions.md
│   ├── testing.md
│   └── operations.md
└── .github/workflows/ci.yml
```

Допустимо объединить два маленьких модуля, если это уменьшает код и не смешивает зоны ответственности. Недопустимо добавлять слои `domain/application/infrastructure/repositories/use_cases/factories` без конкретной потребности.

## 7. Процесс SDD для каждого этапа

Для каждого этапа выполняй один и тот же цикл:

### 7.1 Подготовка

1. Прочитай требования и acceptance criteria этапа.
2. Сверь `docs/code-map.md` и фактическую структуру.
3. Обнови `docs/progress.md`: этап `IN_PROGRESS`, перечисли требования и будущие тесты.
4. Убедись, что рабочее дерево чистое.

### 7.2 Реализация

1. Реализуй только объём этапа.
2. Запусти самые узкие проверки и ручной smoke-тест.
3. Обнови документацию, code-map и traceability одновременно с кодом.
4. Убедись, что нет случайных файлов, секретов, TODO и незавершённых заглушек.
5. Сделай коммит:

```text
feat(stage-XX): <содержательное описание>
```

Для инфраструктуры или документации используй `chore`, `docs` либо `refactor`, но сохраняй `stage-XX`.
6. Push текущей feature-ветки.

### 7.3 Независимая проверка, тестирование и исправление

1. До test commit прочитай `.github/codex/prompts/review.md` и выполни его как независимый checklist по текущему diff: сначала перечисли находки по приоритету, затем исправляй.
2. Добавь все обязательные unit/integration/e2e-тесты этапа.
3. Запусти форматирование, линтер, типизацию и тесты.
4. Исправь первопричины, не маскируй ошибки.
5. Для каждого найденного дефекта добавь регрессионный тест с новым `REG-XXX` ID и свяжи его с требованием.
6. Синхронизируй README, code-map, traceability, progress и ограничения.
7. Сделай коммит:

```text
test(stage-XX): verify <этап> and sync documentation
```

8. Push.
9. Найди GitHub Actions run для последнего коммита и дождись завершения:

```bash
gh run list --branch <feature-branch> --workflow ci.yml --limit 5
gh run watch <run-id> --exit-status
```

10. При падении CI:
   - выполни `gh run view <run-id> --log-failed`;
   - воспроизведи локально;
   - исправь минимально;
   - добавь/обнови тест;
   - сделай `fix(stage-XX): ...`;
   - push и снова дождись CI.
11. Только после зелёного CI отметь этап `DONE` и переходи дальше.

## 8. GitHub и ветки

### 8.1 Инициализация

- Если каталог не является Git-репозиторием, выполни `git init -b main`.
- Если remote `origin` отсутствует и `gh auth status` успешен, создай публичный репозиторий `tender-lens` через `gh repo create` из текущего каталога.
- Если remote существует, не меняй его без причины.
- Не удаляй существующую историю.

### 8.2 Первый commit

В `main` создай и отправь начальный commit со всеми спецификациями, схемами, макетами, `AGENTS.md`, README-заготовкой, `.gitignore`, MIT LICENSE и минимальной проверкой структуры:

```text
chore(init): add SDD specifications and project guardrails
```

Дождись CI, если workflow уже возможно запустить. После этого создай ветку:

```text
feature/tender-lens
```

Весь код пиши в этой ветке.

### 8.3 Финал

После всех этапов:

1. push всех изменений;
2. убедись, что CI зелёный;
3. открой Pull Request в `main` с описанием требований, архитектуры, тестов, ограничений и команд запуска;
4. дождись PR CI;
5. выполни merge commit, не squash, если права и branch protection разрешают;
6. удали feature-ветку после merge;
7. checkout `main`, pull;
8. поставь annotated tag `v0.1.0` и push tag;
9. проверь CI уже на `main`;
10. если merge заблокирован обязательным review, не обходи защиту: оставь PR готовым и зафиксируй это в финальном отчёте.

## 9. Этапы реализации

Следуй точному порядку и acceptance criteria из `specs/10-implementation-plan.md`. Этапы специально малы: каждый добавляет одну проверяемую способность и не должен тащить функции следующего этапа.

```text
00  SDD bootstrap и GitHub
01  Python package и baseline CI
02  Docker Compose infrastructure
03  PostgreSQL migration
04  Pydantic contracts и persistence
05  TED adapter как чистый источник
06  crawler orchestration и attachments
07  NATS JetStream event delivery
08  extraction, chunking, fake indexer
09  Ollama embeddings и exact vector search
10  Contracts Finder adapter
11  FastAPI base и API-key authentication
12  PostgreSQL limiter и Search API
13  RAG /ask
14  Static UI
15  E2E, документация, PR и release
```

Для каждого stage используй тестовые ID из `specs/09-test-plan.md`. Не объединяй stages ради скорости. Если stage слишком велик для одного понятного implementation commit, раздели его на `stage-XXa` и `stage-XXb`, но не меняй порядок требований.

### Stage 00 — SDD bootstrap и GitHub

Начальный commit в `main` содержит весь spec pack, MIT LICENSE, `.gitignore`, initial README и проверку схем. После push создаётся `feature/tender-lens`.

### Stage 01 — Python package и baseline CI

Создай package/entry points, `pyproject.toml`, lock-file, tooling config, Makefile и первую GitHub Actions quality job. На этом этапе CI уже обязан реально запускаться.

### Stage 02 — Docker Compose infrastructure

Создай один непривилегированный application image и сервисы PostgreSQL/pgvector, NATS JetStream, Ollama, api, crawler, indexer. Проверь health и Compose config.

### Stage 03 — PostgreSQL migration

Реализуй расширение `vector`, ровно пять таблиц, ограничения, индексы, async session и upgrade/downgrade проверки.

### Stage 04 — Pydantic contracts и persistence

Реализуй contracts, canonical hash, source/tender/attachment persistence, new/unchanged/changed upsert и CLI создания API key. Сверь Pydantic JSON Schema с файлами `schemas/`.

### Stage 05 — TED adapter

Реализуй `SourceAdapter`, общий async transport policy, TED mapping и fixtures. Не подключай persistence, attachment download или NATS: stage проверяет только источник и нормализацию.

### Stage 06 — crawler и attachments

Соедини adapter с persistence, cursor boundary и безопасным downloader. Реализуй `--once` и периодический режим. New/changed записи пока только остаются `pending`.

### Stage 07 — NATS JetStream

Добавь единственный stream/subject/consumer, publish after commit, pending republish, explicit ACK и redelivery tests. Indexer handler на этом этапе может быть минимальным fake consumer, но не пустой заглушкой.

### Stage 08 — extraction, chunking и fake indexer

Реализуй поддерживаемые extractors, deterministic chunking, fake embeddings и транзакционную замену chunks. Докажи идемпотентность и сохранение старого индекса при ошибке.

### Stage 09 — Ollama embeddings и vector search

Добавь batch `/api/embed`, проверку 1024 dimensions и exact cosine search. Никакого HNSW/FTS/hybrid. Live smoke отделён от CI.

### Stage 10 — Contracts Finder adapter

Добавь OCDS mapping, cursor и 403 cooldown. Оба adapters проходят один contract-test и одну orchestration path.

### Stage 11 — FastAPI и auth

Добавь app factory, errors/request ID, health, tender details и `X-API-Key`. Rate limiter и search endpoint пока не подключай.

### Stage 12 — Rate limiter и Search API

Добавь injectable clock, fixed UTC-minute limiter с row lock, rate headers и `/search`. Лимит общий для `/search` и `/ask`; tender details аутентифицирован, но не расходует лимит.

### Stage 13 — RAG `/ask`

Добавь grounded prompt, generation client, no-context short circuit, sources только из retrieval и 503 для ошибок модели.

### Stage 14 — Static UI

Реализуй одну страницу по `docs/ui/search-wireframe.png`: API key, Search/Ask, результаты и состояния ошибок. Нет npm/CDN/framework.

### Stage 15 — E2E и release

Собери полный fixture pipeline, заверши CI jobs, проверь документацию/code-map/traceability, выполни ручной demo, открой PR, проверь PR CI, merge и tag либо честно зафиксируй внешний blocker.

## 10. Тестовые правила

Полный перечень тестов находится в `specs/09-test-plan.md`. Реализуй каждый test case с указанным ID либо отрази объединение нескольких IDs в одном параметризованном тесте.

Имена тестов должны показывать поведение, например:

```python
async def test_sixth_request_in_same_window_returns_429() -> None:
    ...
```

Не называй тесты `test_1`, `test_service` или `test_success`.

Используй:

- unit tests без сети и БД;
- integration tests с настоящими PostgreSQL/pgvector и NATS;
- e2e с локальным fixture HTTP server и fake AI;
- `@pytest.mark.live` только для ручных smoke-тестов внешних API/Ollama.

Общий coverage threshold не является целью сам по себе. Критические ветви из test plan должны быть покрыты. Не добавляй бессмысленные тесты getter-ов ради процента.

## 11. Документация и code-map

После каждого этапа `docs/code-map.md` должен содержать:

- дерево актуальных директорий;
- назначение каждого модуля;
- entry points;
- таблицы и владельцев записи;
- NATS stream/subject/consumer;
- HTTP endpoints;
- связи с внешними API;
- соответствующие test files;
- список сознательно отсутствующих компонентов.

`docs/traceability.md` должен иметь таблицу:

```text
Requirement ID | Реализация | Test IDs | Статус | Комментарий
```

`docs/progress.md` должен содержать:

- текущий этап;
- завершённые gates;
- последний commit SHA;
- последний GitHub Actions run и conclusion;
- известные ограничения;
- следующий минимальный шаг.

Не копируй один и тот же текст во все документы. README предназначен проверяющему, specs — агенту и разработчику, code-map — навигации, operations — запуску и диагностике.

## 12. Внешние источники и fixtures

### TED

Используй официальный Search API:

```text
POST https://api.ted.europa.eu/v3/notices/search
```

Search API не требует авторизации. Используй ограниченный набор полей и raw payload. Не строй полную модель eForms.

### Contracts Finder

Используй публичный OCDS search endpoint:

```text
GET https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search
```

Параметры:

```text
publishedFrom
publishedTo
stages
limit
cursor
```

Limit не более 100. При 403 прекрати запросы к источнику минимум на пять минут в live-режиме либо заверши `--once` понятной ошибкой.

### Fixtures

Во время этапа адаптера:

1. выполни один минимальный live-запрос, если сеть доступна;
2. удали персональные/лишние данные;
3. сохрани небольшой стабильный fixture;
4. запиши дату и endpoint в комментарии fixture metadata;
5. обычные тесты выполняй только на fixture;
6. если live API недоступен, используй примеры из пакета и не утверждай, что live smoke пройден.

## 13. Минимальная схема данных

Реализуй ровно пять таблиц:

- `sources`;
- `tenders`;
- `attachments`;
- `chunks`;
- `api_keys`.

Не добавляй users, roles, lots, organizations, bids, versions, crawl_runs, inbox/outbox и model_registry.

Подробности типов, индексов и ограничений находятся в `specs/04-data-model.md`.

## 14. AI и поиск

- Embedding model: `qwen3-embedding:0.6b`.
- Размер: 1024.
- Generation model: `qwen3:1.7b`.
- Ollama endpoint для embeddings: `/api/embed`, batch input.
- Для индексации и запроса используется одна embedding model.
- В MVP exact cosine search без approximate index.
- `limit` API: 1–10, default 5.
- Chunking: по абзацам, максимум 1500 символов, overlap до 150 символов.
- Ответ RAG основан только на top 5 chunks.
- Температура генерации: 0 или минимально поддерживаемая детерминированная настройка.
- Если данных нет, не вызывай LLM.

## 15. Rate limiter

Реализуй простой fixed UTC-minute window в таблице `api_keys`:

- `window_started_at`;
- `request_count`;
- `limit_per_minute` default 5.

В одной транзакции:

1. найди key по hash;
2. `SELECT ... FOR UPDATE`;
3. если UTC-minute изменился, сбрось count;
4. если count >= limit, верни 429 без увеличения;
5. иначе увеличь count и обнови `last_used_at`;
6. commit.

Добавь:

- `X-RateLimit-Limit`;
- `X-RateLimit-Remaining`;
- `X-RateLimit-Reset`;
- `Retry-After` для 429.

В документации честно укажи boundary burst как ограничение fixed window и опиши Redis sliding window только как возможное развитие, не реализуй его.

## 16. CI/CD

Создай `.github/workflows/ci.yml` для `push` и `pull_request`.

Минимальные jobs:

1. `quality`:
   - checkout;
   - Python setup;
   - dependency install from lock;
   - `black --check .`;
   - `flake8 src tests`;
   - `mypy src`;
   - unit tests.
2. `integration`:
   - PostgreSQL image с pgvector;
   - NATS с JetStream;
   - migration from clean DB;
   - integration/e2e tests с fake AI;
3. `docker`:
   - `docker compose config`;
   - build единого application image;
   - проверить, что три роли запускают `--help` или smoke command.

Не запускай live crawler и не загружай модели Ollama в CI.

После каждого push агент обязан проверить GitHub run через `gh`, а не считать наличие YAML доказательством работающего CI.

## 17. Финальный ручной сценарий

Перед PR выполни и задокументируй:

```text
1. docker compose up --build -d postgres nats ollama
2. загрузка qwen3-embedding:0.6b и qwen3:1.7b
3. alembic upgrade head
4. создание demo API key
5. crawler --once --source ted --limit 5
6. дождаться index_status=ready
7. POST /api/v1/search
8. POST /api/v1/ask
9. выполнить шестой защищённый запрос и получить 429
10. открыть UI в браузере
```

Если live source или Ollama недоступны, выполни эквивалентный fake e2e и явно отдели его от непроверенного live smoke.

## 18. Финальный отчёт

В конце выдай структурированный результат по `schemas/codex-final-report.schema.json` и дополнительно сохрани `docs/final-report.md` со следующим:

- URL репозитория;
- URL Pull Request;
- commit SHA после merge или head PR;
- CI run URL и conclusion;
- реализованные требования;
- команды запуска;
- результаты unit/integration/e2e/live smoke;
- ограничения;
- что сознательно не реализовано;
- три наиболее важных архитектурных компромисса;
- список файлов, которые следует прочитать перед собеседованием;
- краткий сценарий пятиминутной демонстрации.

Не завершай работу фразой «всё готово», пока Definition of Done не подтверждён командами и GitHub CI.
