# Search, RAG и API

API — тонкая HTTP-оболочка над authentication, rate limiting и `SearchService`. Search возвращает проверяемые fragments; Ask добавляет generation только поверх релевантного результата.

<dl class="module-contract">
  <dt>Вход</dt><dd>HTTP JSON + X-API-Key</dd>
  <dt>Выход</dt><dd>SearchResponse, AskResponse, TenderDetails или ErrorResponse</dd>
  <dt>Состояние</dt><dd>PostgreSQL + AIProvider; request_id живёт в одном HTTP request</dd>
  <dt>Точка запуска</dt><dd><code>uvicorn tender_lens.api.main:app</code></dd>
</dl>

## Карта файлов

| Файл | Назначение |
|---|---|
| [`api/main.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/api/main.py) | app factory, lifespan, middleware, exception handlers, static mount |
| [`api/routes.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/api/routes.py) | health, detail, search, ask endpoints |
| [`api/auth.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/api/auth.py) | API-key generation/hash/lookup |
| [`api/rate_limit.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/api/rate_limit.py) | atomic fixed UTC-minute counter |
| [`search.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/search.py) | pgvector retrieval и grounded ask |
| [`ai.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/ai.py) | provider protocol, fake/Ollama, prompt |

## App factory и lifespan

[`create_app()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/api/main.py#L52-L135) принимает optional dependencies, поэтому HTTP tests подставляют in-memory service без PostgreSQL. В production lifespan создаёт engine/session factory и AI provider, сохраняет их в `application.state`, а при shutdown закрывает собственные ресурсы.

Middleware принимает клиентский `X-Request-ID` или генерирует UUID и возвращает его в каждом ответе. Exception handlers преобразуют Pydantic validation и внутренние exceptions в одинаковую envelope.

## Authentication

Dependency [`authenticate_api_key()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/api/auth.py#L35-L59):

1. требует header;
2. считает SHA-256;
3. ищет `ApiKey.key_hash`;
4. проверяет `enabled`;
5. делает constant-time `compare_digest`;
6. detach-ит model от session и возвращает identity следующей dependency.

Health endpoints открыты; tender/search/ask защищены.

## Rate limiter

[`consume_rate_limit()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/api/rate_limit.py#L42-L81) блокирует строку ключа `FOR UPDATE`. При новой UTC-минуте count обнуляется. Успех увеличивает count и возвращает только `X-RateLimit-Limit`, `Remaining`, `Reset`. Превышение rollback-ит и добавляет `Retry-After` только к 429.

Search и Ask делят один counter, потому что обе операции потребляют AI/DB ресурсы.

## Exact cosine retrieval

Query превращается в embedding, далее PostgreSQL вычисляет:

```sql
1 - (chunks.embedding <=> CAST(:embedding AS vector))
```

`<=>` — cosine distance, поэтому `1 - distance` — cosine similarity. SQL ограничивает значение диапазоном `[-1, 1]`, фильтрует `MIN_RELEVANCE_SCORE`, сортирует по близости и UUID, затем применяет limit.

MVP использует exact scan: просто и детерминированно для небольшого индекса. При большом числе chunks потребуются HNSW/IVFFlat и измеренный recall/latency trade-off.

## Fake и live provider

[`AIProvider`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/ai.py#L17-L23) задаёт `embed`, `generate`, `health`.

- `FakeAIProvider` — hashing trick: token получает детерминированный индекс и знак по SHA-256, vector нормализуется. Это не нейросеть и не production semantic model; он делает CI быстрым и повторяемым.
- `OllamaAIProvider` вызывает `/api/embed`, `/api/generate`, `/api/tags`, строго проверяет количество и размерность vectors и переводит HTTP/JSON ошибки в typed dependency error.

## Grounded Ask

[`ask()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/search.py#L83-L93) сначала вызывает тот же Search. Пустой результат возвращает «Недостаточно данных в базе знаний» без LLM. Иначе [`build_rag_prompt()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/ai.py#L134-L157) передаёт вопрос, названия, source URLs и fragments.

«Grounded» означает, что ответ должен опираться на переданный контекст. Sources в ответе позволяют человеку проверить основание, но модель всё равно может ошибиться — поэтому интерфейс не скрывает fragments.

## Endpoints

| Method/path | Auth/rate | Назначение |
|---|---|---|
| `GET /health/live` | нет | процесс отвечает |
| `GET /health/ready` | нет | PostgreSQL и AI доступны |
| `GET /api/v1/tenders/{id}` | auth | карточка и attachments |
| `POST /api/v1/search` | auth + rate | top 1..10 chunks |
| `POST /api/v1/ask` | auth + rate | answer по top 1..5 chunks |

Полные payloads — в [HTTP API](../api-examples.md).
