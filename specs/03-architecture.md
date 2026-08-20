# 03. Архитектура

## 1. Архитектурный стиль

TenderLens — **минимально распределённое событийное приложение**, а не набор строгих автономных микросервисов.

Используются:

- один monorepo;
- один Python package;
- один application image;
- три независимо запускаемые роли: `crawler`, `indexer`, `api`;
- общая PostgreSQL/pgvector база;
- один NATS JetStream канал между crawler и indexer;
- общий volume для вложений;
- один Ollama instance.

Такое разделение сохраняет реальную асинхронную границу вокруг медленной индексации, но не создаёт отдельные CRUD/API/БД там, где они не дают пользы.

## 2. Контекстная схема

См.:

- `docs/diagrams/architecture.mmd`;
- `docs/diagrams/architecture.png`;
- `docs/diagrams/crawl-sequence.mmd`;
- `docs/diagrams/ask-sequence.mmd`.

```text
Browser -> FastAPI API -> PostgreSQL/pgvector -> Ollama

TED / Contracts Finder -> crawler -> PostgreSQL + attachment volume
crawler -> NATS JetStream:tender.changed.v1 -> indexer
indexer -> attachment volume + PostgreSQL -> Ollama -> pgvector
```

## 3. Компоненты

### 3.1 `crawler`

Ответственность:

- запуск адаптеров;
- HTTP-политика внешних источников;
- нормализация в `TenderRecordV1`;
- детерминированный `content_hash`;
- upsert метаданных;
- загрузка вложений;
- публикация `tender.changed.v1`;
- повторная публикация `pending` при предыдущей ошибке;
- обновление cursor.

Crawler не создаёт embeddings и не отвечает на пользовательские запросы.

### 3.2 `indexer`

Ответственность:

- durable pull consumption;
- извлечение текста;
- чанкинг;
- embeddings;
- атомарная замена chunks;
- обновление `indexed_hash/index_status`;
- ACK только после commit.

Indexer не ходит во внешние сайты и не обслуживает HTTP API.

### 3.3 `api`

Ответственность:

- static UI;
- health endpoints;
- API-key auth;
- PostgreSQL rate limiter;
- поиск в pgvector;
- вызов Ollama для RAG;
- единая модель ошибок.

API не использует NATS request/reply. Для чтения он обращается к PostgreSQL напрямую.

## 4. Инфраструктура

### PostgreSQL + pgvector

Хранит метаданные, состояние индекса, chunks, embeddings и API keys. Exact cosine search выполняется оператором cosine distance. Approximate index не создаётся.

### NATS JetStream

Используется только для долговечной очереди фоновой индексации.

```text
Stream: TENDERS
Subjects: tender.changed.v1
Retention: limits
Storage: file
Consumer: INDEXER
Delivery: pull
Ack policy: explicit
```

Обработка предполагает at-least-once delivery. Идемпотентность обеспечивается сравнением `indexed_hash` и `content_hash`.

### Ollama

Обслуживает:

- batch embeddings;
- генерацию RAG-ответа.

В CI заменяется fake provider или HTTP mock.

### Attachment volume

Crawler пишет, indexer читает. API может читать только для выдачи файла, если такой endpoint позднее будет нужен; в MVP отдельного download endpoint нет.

## 5. Поток новой закупки

1. Scheduler-цикл вызывает адаптер.
2. Адаптер возвращает `TenderRecordV1`.
3. Crawler вычисляет hash и выполняет upsert.
4. Доступные вложения скачиваются атомарно через временный файл.
5. Commit фиксирует тендер и attachments.
6. Для new/changed публикуется `tender.changed.v1`.
7. Indexer получает сообщение.
8. Indexer читает тендер и файлы.
9. Текст извлекается и режется на chunks.
10. Fake/live provider создаёт embeddings.
11. В одной транзакции старые chunks заменяются новыми, `indexed_hash` обновляется.
12. После commit сообщение ACK.

## 6. Поток пользовательского запроса

1. UI отправляет `X-API-Key` и JSON request.
2. API проверяет hash ключа.
3. Для `/search` и `/ask` атомарно проверяется общий rate limit.
4. API получает query embedding.
5. PostgreSQL возвращает top-k chunks по cosine similarity.
6. `/search` сразу возвращает результаты.
7. `/ask` при наличии контекста вызывает generation model.
8. Ответ содержит только источники из retrieval.

## 7. Ошибки и восстановление

| Сбой | Поведение |
|---|---|
| TED/CF timeout | ограниченный retry, затем источник помечается ошибкой текущего цикла |
| 429/503 внешнего источника | учитывается `Retry-After`, применяется backoff |
| Один источник упал | второй источник всё равно запускается |
| Attachment download упал | ошибка сохраняется; остальные записи продолжаются |
| NATS publish упал | тендер остаётся `pending`, повторная публикация в следующем цикле |
| Indexer упал до commit | NATS не получает ACK, сообщение доставляется повторно |
| Indexer упал после commit до ACK | повторная доставка распознаётся по `indexed_hash` |
| Ollama embeddings недоступна | index status `failed`/retry по NATS, старый индекс не удаляется |
| Ollama generation недоступна | API возвращает 503 |
| PostgreSQL недоступен | readiness false; защищённые endpoints возвращают 503 |

## 8. Сознательные нарушения строгой микросервисности

- одна база для трёх ролей;
- один package и Docker image;
- общий attachment volume;
- API напрямую читает chunks;
- нет отдельного catalog API.

Это снижает объём кода и когнитивную стоимость. Границы процессов сохранены там, где есть разный жизненный цикл и профиль нагрузки.
