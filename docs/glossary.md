---
search:
  boost: 1.5
---

# Глоссарий

Определения даны не абстрактно, а в контексте TenderLens. Английские имена сохранены, потому что именно их нужно искать в коде, логах и документации библиотек.

## A–C

**ACK (acknowledgement)**
: Подтверждение JetStream, что сообщение обработано и больше не нужно доставлять consumer. Indexer вызывает ACK только после успешного DB commit либо для безопасно пропускаемого `stale/unchanged` события.

**ACK wait**
: Время, которое JetStream ждёт ACK до повторной доставки. В проекте — 300 секунд, чтобы CPU Ollama успел обработать документ.

**AI provider**
: Узкий интерфейс `embed/generate/health`. Реализации: детерминированный `FakeAIProvider` и HTTP-клиент `OllamaAIProvider`.

**Alembic**
: Инструмент versioned database migrations для SQLAlchemy. `upgrade head` приводит чистую или старую БД к последней revision; `downgrade base` используется в CI для проверки обратимости. [Официальная документация](https://alembic.sqlalchemy.org/).

**Allowlist**
: Закрытый список разрешённых host. URL с любым другим host блокируется до HTTP-запроса; разные источники имеют разные наборы официальных attachment hosts.

**Async / asynchronous**
: Модель, где coroutine отдаёт event loop управление во время ожидания сети/БД. Это позволяет одному OS-потоку обслуживать несколько I/O operations без thread на запрос.

**At least once**
: Семантика доставки «одно или больше раз». Сообщение не теряется из-за падения до ACK, но consumer обязан терпеть duplicates.

**Atomic operation**
: Операция видна либо целиком, либо не видна. Примеры: DB transaction и `os.replace` готового attachment вместо частично записанного файла.

**Backoff**
: Увеличивающаяся задержка между HTTP retries. TenderLens использует exponential component плюс jitter, если сервер не дал `Retry-After`.

**Batch**
: Группа элементов в одном вызове. Indexer отправляет несколько chunks в один Ollama `/api/embed`, снижая HTTP/model overhead.

**BoundedSemaphore**
: Счётчик `asyncio`, который не позволяет одновременно выполнять больше N сетевых операций и обнаруживает лишний `release`. Это фактический предел concurrency crawler.

**Chunk**
: Небольшой фрагмент текста с section, position и embedding. Это единица cosine search и source в RAG-ответе.

**CI (Continuous Integration)**
: GitHub Actions, автоматически проверяющий format, lint, typing, tests, migrations, image smoke и документацию на push/PR.

**Content hash**
: SHA-256 canonical значимых полей закупки. Изменение hash означает новую версию для индексации; одинаковый hash делает повторный crawl идемпотентным.

**Contract / контракт**
: Явная форма и правила данных. Pydantic model проверяет Python/HTTP/NATS payload, JSON Schema — сериализованный event, DDL — постоянные rows.

**Correlation ID**
: Идентификатор для связи событий наблюдаемости: `request_id`, `event_id`, `tender_id`, `source`.

**Cosine distance / similarity**
: Мера угла между vectors. pgvector operator `<=>` возвращает distance; TenderLens показывает similarity `1 - distance`.

**Crawler / scraper**
: Роль, которая регулярно получает закупки и файлы. Здесь crawler использует официальные JSON API и не извлекает карточки из browser DOM.

**Cursor**
: Непрозрачная позиция pagination источника. Хранится в `sources`, изолирована по source и продвигается только после обработанной порции.

## D–H

**Dead-letter / poison message**
: Событие, которое стабильно не обрабатывается. В MVP отдельной DLQ нет; permanent error получает TERM, а `max_deliver` ограничивает временные повторы. Production должен сохранять такие события для review.

**Dependency injection**
: Передача dependency снаружи вместо создания внутри функции. FastAPI `Depends` предоставляет auth/session, а `create_app` принимает fake session/search в tests.

**DSN / database URL**
: Строка с driver, credentials, host и database, например `postgresql+asyncpg://…`. Считается секретной configuration и не должна попадать в публичный log.

**Durable consumer**
: Именованный JetStream consumer, состояние которого переживает перезапуск indexer. Имя — `INDEXER`.

**Embedding**
: Числовой vector текста. В live-режиме его строит `qwen3-embedding:0.6b`; schema требует ровно 1024 компоненты.

**Environment variable**
: Настройка процесса вне кода. Compose передаёт `.env`; Pydantic Settings преобразует строки в типы и валидирует диапазоны.

**Event loop**
: Планировщик asyncio coroutines. Пока одна coroutine ждёт network I/O, loop выполняет другую готовую coroutine.

**Event / событие**
: Неизменяемый факт «версия закупки изменилась». `TenderChangedV1` содержит идентификаторы и hash, но не полный документ.

**Exact scan**
: Сравнение query vector со всеми candidate vectors без approximate index. Даёт простой предсказуемый результат, но хуже масштабируется.

**FastAPI**
: ASGI framework API, routing, validation и OpenAPI. [Документация](https://fastapi.tiangolo.com/).

**Fixture**
: Зафиксированный локальный пример внешних данных. Он делает mapping/E2E повторяемыми и независимыми от live network.

**Fixed-window rate limit**
: Все запросы одного API key считаются внутри дискретной UTC-минуты. Просто и атомарно, но позволяет burst на границе двух окон.

**Foreign key (FK)**
: Ограничение ссылки между таблицами. Например, attachment обязан принадлежать существующему tender.

**Grounded RAG**
: Generation с обязательной опорой на retrieval context. Ответ возвращается вместе с fragments, использованными как основание.

**Hashing trick**
: Детерминированное распределение tokens по vector dimensions через hash. Используется FakeAI, но не заменяет обученную semantic model.

**Health / liveness / readiness**
: Liveness отвечает «процесс жив». Readiness отвечает «можно обслуживать запрос», проверяя PostgreSQL и AI.

**HNSW / IVFFlat**
: Approximate vector indexes pgvector. Они ускоряют большой индекс ценой настройки, памяти и возможной потери recall; в MVP не созданы.

**HTTP 429 / Retry-After**
: 429 означает превышение rate. `Retry-After` сообщает, сколько секунд ждать; успешные ответы этот header не содержат.

## I–N

**Idempotency / идемпотентность**
: Повтор операции не меняет конечный результат после первого успеха. Обеспечивается unique keys, content/indexed hash, deterministic chunk key и event deduplication.

**Indexer**
: Фоновая роль, которая извлекает текст, режет его, строит embeddings и заменяет chunks.

**Invariant / инвариант**
: Условие, которое система сохраняет при всех разрешённых переходах: например, ready index относится к `indexed_hash`.

**Isolation (источников)**
: Сбой TED не останавливает Contracts Finder; одинаковый `external_id` в разных source не конфликтует; cursor хранится раздельно.

**JetStream**
: Persistence и consumer layer поверх NATS. Добавляет streams, durable consumers, ACK/redelivery и file storage. [Документация](https://docs.nats.io/nats-concepts/jetstream).

**Jitter**
: Случайная добавка к задержке. Разносит запросы во времени и снижает синхронные всплески нескольких crawler instances.

**JSON Schema**
: Машиночитаемая схема JSON. Checked-in файлы генерируются из Pydantic и проверяются на drift.

**LLM (Large Language Model)**
: Генеративная языковая модель. В TenderLens `qwen3:1.7b` формулирует ответ после retrieval; она не выполняет сбор или поиск.

**Migration**
: Версионированное изменение database schema. Migration является source of truth для физической БД.

**MkDocs / Material for MkDocs**
: Static-site generator и его тема, из которых собирается этот инженерный портал. Markdown остаётся читаемым прямо в GitHub, а build добавляет навигацию, оглавление и локальный полнотекстовый поиск. [MkDocs](https://www.mkdocs.org/) · [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).

**Mermaid**
: Текстовый язык диаграмм. Блоки `mermaid` в статьях рендерятся Material for MkDocs в браузере, поэтому схема меняется вместе с кодом без ручного редактирования PNG. Runtime Mermaid 11 загружается с CDN: для первого визуального render нужен интернет, но текст статьи и исходник схемы остаются доступны. [Документация](https://mermaid.js.org/intro/).

**Model (двусмысленный термин)**
: В `models.py` — ORM class/table; в AI-настройках — embedding/generation neural model; в Pydantic — validation schema. Контекст обязателен.

**Monorepo**
: Crawler, indexer, API, migrations, UI и docs находятся в одном Git repository и versioned вместе.

**NAK (negative acknowledgement)**
: Просьба JetStream повторить доставку. Используется только для временных ошибок и может содержать delay.

**NATS**
: Лёгкая messaging system; JetStream делает сообщения durable. Subject TenderLens — `tender.changed.v1`.

**Normalization**
: Преобразование разных внешних форматов в одинаковый `TenderRecordV1`: trim строк, UTC datetime, Decimal, currency uppercase.

## O–R

**OCR**
: Распознавание текста на изображении. В MVP отсутствует, поэтому scanned PDF без text layer сохраняется, но почти не даёт searchable text.

**OCDS**
: Open Contracting Data Standard. Contracts Finder Search возвращает OCDS releases, из которых adapter читает tender/buyer/value/period/documents. [Стандарт](https://standard.open-contracting.org/latest/en/).

**Ollama**
: Локальный HTTP runtime моделей. Compose profile `ai` запускает server и одноразово загружает две модели. [API](https://docs.ollama.com/api/introduction).

**OS thread**
: Поток операционной системы. Crawler не создаёт thread на request; concurrency достигается asyncio coroutines.

**pgvector**
: PostgreSQL extension с типом `VECTOR` и операторами distance. [Проект](https://github.com/pgvector/pgvector).

**Politeness delay**
: Пауза перед запросом к открытому источнику. Это базовая вежливая политика нагрузки, а не обход защиты.

**PostgreSQL row lock / `FOR UPDATE`**
: Блокировка строки до окончания транзакции. Используется для rate counter и финальной проверки версии indexer.

**Prompt**
: System/user text, отправляемый generation model. Documents включаются как недоверенный контекст, не как команды.

**Prompt injection**
: Инструкции внутри внешнего документа, пытающиеся изменить поведение модели. TenderLens ограничивает контекст и явно маркирует его untrusted, но полностью исключить риск одной формулировкой нельзя.

**Pydantic**
: Runtime data validation и serialization. [Документация](https://docs.pydantic.dev/latest/).

**RAG (Retrieval-Augmented Generation)**
: Сначала retrieval находит evidence, затем LLM формулирует ответ с этим evidence. Вызов без retrieval был бы обычным generation, а не RAG.

**Rate limit**
: Ограничение числа Search+Ask одного key — по умолчанию пять за UTC-минуту.

**Redirect**
: HTTP 3xx с новым URL. Обрабатывается вручную, потому что автоматический переход мог бы обойти allowlist.

**Relevance threshold**
: Минимальный cosine similarity (`MIN_RELEVANCE_SCORE`). Результаты ниже него исключаются до RAG.

**Retry**
: Повтор той же операции после временного сбоя. Не путать с redirect: переход к новому URL не расходует retry attempt.

## S–Z

**Schema drift**
: Расхождение Pydantic-generated JSON Schema и checked-in schema file. `export_schemas.py --check` делает drift ошибкой CI.

**Semantic search**
: Поиск по близости embeddings, а не буквальному совпадению подстрок. Качество определяется моделью, chunking и corpus.

**SHA-256**
: Криптографическая hash function с 256-bit результатом. Применяется для API key lookup, content version, chunk key и integrity вложения — с разными входами.

**Source adapter**
: Компонент, который знает внешний API, но возвращает внутренний `SourcePage`.

**Source of truth**
: Авторитетное представление. PostgreSQL — runtime state; Alembic migration — schema history; Pydantic — boundary contract; source code — поведение.

**SSRF**
: Server-Side Request Forgery: заставить backend запросить внутренний/произвольный адрес. Закрытый allowlist и запрет local/private literal IP снижают риск.

**Stale event**
: Событие со старым `content_hash`, когда tender уже обновился. Indexer подтверждает его без изменения current index state.

**Stream (два значения)**
: В NATS — persisted sequence сообщений; в HTTP/file download — постепенное чтение bytes без загрузки всего файла в память.

**TERM**
: JetStream acknowledgement, прекращающий повторную доставку конкретного сообщения. Используется для невалидных или постоянных ошибок.

**TED**
: Tenders Electronic Daily — официальный портал EU procurement. Crawler использует Search API v3, а не HTML detail page. [Search API](https://docs.ted.europa.eu/api/latest/search.html).

**Transaction**
: Группа SQL operations с общей судьбой commit/rollback. Финальная замена chunks выполняется одной транзакцией.

**Typed error**
: Исключение определённого класса с понятной категорией. Позволяет API выбрать status, а indexer — retry policy.

**UPSERT**
: Insert новой строки или update существующей идентичности. В сервисном коде реализован как SELECT + insert/update под constraints; результат идемпотентен.

**UTC**
: Единая временная зона хранения и limiter window. Это исключает неоднозначность локального времени и DST.

**UUID**
: 128-bit идентификатор rows/events. Не является секретом и не заменяет API key.

**Vector**
: Упорядоченный список чисел. TenderLens требует длину 1024 и хранит его в pgvector.

**WAF**
: Web Application Firewall. Browser detail TED может показывать challenge/пустую страницу, хотя официальный Search API и прямые документы доступны; crawler не пытается обходить WAF.

**Worker**
: Долгоживущий фоновый процесс, потребляющий задания. В проекте worker — роль indexer.
