# Потоки данных

Здесь показано не расположение файлов, а порядок действий во времени. Сплошная стрелка — вызов или запись; ответная пунктирная стрелка — результат; блок `alt` — ветвление.

## Crawl одной страницы

```mermaid
sequenceDiagram
    autonumber
    participant Runner as crawler/__main__.py
    participant Adapter as SourceAdapter
    participant HTTP as ResilientHttpClient
    participant Service as CrawlerService
    participant DB as PostgreSQL
    participant FS as Attachment volume
    participant JS as NATS JetStream

    Runner->>Service: get_cursor(source)
    Service->>DB: SELECT/INSERT sources
    DB-->>Service: cursor
    Runner->>Adapter: fetch_page(cursor, limit)
    Adapter->>HTTP: GET/POST official API
    HTTP-->>Adapter: validated JSON
    Adapter-->>Runner: SourcePage(records, next_cursor)
    loop каждая валидная record
        Runner->>Service: persist_record(record)
        Service->>DB: UPSERT tender + attachments
        DB-->>Service: COMMIT + content_hash
        par ограниченная загрузка вложений
            Service->>HTTP: stream(source_url)
            HTTP-->>FS: .part → fsync → atomic replace
            Service->>DB: attachment=ready
        end
        alt данные или файл изменились
            Service->>JS: tender.changed.v1
        end
    end
    Service->>DB: update_cursor(next_cursor)
```

Ключевой порядок: **commit данных предшествует publish**, а cursor фиксируется после обработанной порции. Код orchestration — [`run_source()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/service.py#L256-L297).

### Что считается успехом страницы

- ответ API получен и разобран;
- каждая принятая нормализованная запись зафиксирована;
- сбой отдельного вложения записан в `attachments.error_message`, но не отменяет остальные записи;
- ошибка `persist_record()` прерывает порцию, поэтому cursor не перескакивает потерянную запись;
- publish может временно не выполниться: row остаётся `pending` для следующего `republish_pending()`.

## Индексация события

```mermaid
sequenceDiagram
    autonumber
    participant JS as NATS JetStream
    participant Worker as indexer/__main__.py
    participant Service as IndexerService
    participant DB as PostgreSQL
    participant FS as Attachment volume
    participant AI as AIProvider

    JS->>Worker: message (at least once)
    Worker->>Worker: validate TenderChangedV1
    Worker->>Service: process(event)
    Service->>DB: load tender + attachments
    alt event hash != current hash
        Service-->>Worker: stale
        Worker->>JS: ACK
    else уже indexed_hash == hash
        Service-->>Worker: unchanged
        Worker->>JS: ACK
    else новая версия
        Service->>DB: index_status=processing
        Service->>FS: read supported attachments
        Service->>Service: extract → chunk
        loop batch по EMBEDDING_BATCH_SIZE
            Service->>AI: embed(texts[])
            AI-->>Service: vectors[]
        end
        Service->>DB: lock + recheck hash
        Service->>DB: DELETE old + INSERT new + ready, COMMIT
        Service-->>Worker: ready
        Worker->>JS: ACK
    end
```

Повторная проверка hash выполняется после дорогого вызова AI. Поэтому закупка, изменившаяся во время embeddings, не получает индекс от старой версии.

## Search

```mermaid
sequenceDiagram
    autonumber
    participant Client as Browser / API client
    participant API as FastAPI
    participant Auth as Auth + limiter
    participant AI as AIProvider
    participant DB as pgvector

    Client->>API: POST /api/v1/search + X-API-Key
    API->>Auth: SHA-256 lookup
    Auth->>DB: SELECT api_key
    Auth->>DB: FOR UPDATE rate counter
    API->>AI: embed([query])
    AI-->>API: VECTOR(1024)
    API->>DB: cosine exact scan + threshold
    DB-->>API: top-k chunks
    API-->>Client: items + X-RateLimit-*
```

Search не вызывает generation model. Он выполняет один embedding запроса и SQL из [`SearchService.search()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/search.py#L23-L81).

## Ask / grounded RAG

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API
    participant Search as SearchService
    participant AI as AIProvider

    Client->>API: POST /api/v1/ask
    API->>Search: ask(query, limit≤5)
    Search->>Search: search + MIN_RELEVANCE_SCORE
    alt нет релевантных chunks
        Search-->>API: «Недостаточно данных»
        Note over Search,AI: generation НЕ вызывается
    else найден контекст
        Search->>Search: build_rag_prompt()
        Search->>AI: generate(system, prompt)
        AI-->>Search: grounded answer
        Search-->>API: answer + те же sources
    end
    API-->>Client: JSON
```

## Повторы и финальные действия

| Сбой | Следующее действие | Почему нет потери/дубликата |
|---|---|---|
| HTTP timeout/429/5xx | retry с backoff/`Retry-After` | число HTTP-попыток ограничено |
| redirect | перейти без расхода retry | схема и host проверяются заново |
| publish после DB commit | следующий crawl переопубликует `pending` | `content_hash` привязывает event к версии |
| indexer: PostgreSQL/Ollama/OSError | NAK 10 s | JetStream доставит снова, максимум 5 раз |
| event невалиден | TERM | повтор не исправит payload |
| постоянная ошибка кода/extraction | TERM и `failed` | poison message не блокирует очередь |
| worker умер до ACK | redelivery после `ack_wait=300s` | обработка идемпотентна |

`ACK` подтверждает успешную или уже неактуальную обработку. `NAK` просит повторить позже. `TERM` прекращает доставки конкретного сообщения.
