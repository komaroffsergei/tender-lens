# 06. HTTP API

Базовый prefix: `/api/v1`.

## 1. Общие правила

- JSON UTF-8;
- request ID создаётся для каждого запроса и возвращается как `X-Request-ID`;
- защищённые endpoints требуют `X-API-Key`;
- `/search` и `/ask` используют один общий rate-limit counter;
- timestamps сериализуются в UTC ISO 8601;
- OpenAPI генерируется FastAPI и сверяется smoke-тестом;
- raw payload, filesystem paths и API key hash наружу не выдаются.

## 2. Health

### `GET /health/live`

Публичный. Не обращается к зависимостям.

```json
{"status":"ok","service":"api"}
```

### `GET /health/ready`

Публичный. Проверяет PostgreSQL и Ollama. Для crawler/indexer отдельные CLI health/smoke команды могут проверять NATS.

- 200: зависимости готовы;
- 503: хотя бы одна обязательная зависимость недоступна.

## 3. Получение закупки

### `GET /api/v1/tenders/{tender_id}`

Auth: `X-API-Key`.
Rate limit: нет.

200 response:

```json
{
  "id": "uuid",
  "source": "ted",
  "external_id": "123456-2026",
  "title": "Supply of server equipment",
  "description": "...",
  "buyer_name": "Example authority",
  "amount": "1250000.00",
  "currency": "EUR",
  "published_at": "2026-08-20T09:00:00Z",
  "deadline": "2026-09-15T12:00:00Z",
  "source_url": "https://...",
  "index_status": "ready",
  "attachments": [
    {
      "id": "uuid",
      "title": "Technical specification",
      "filename": "specification.pdf",
      "content_type": "application/pdf",
      "size_bytes": 18320,
      "download_status": "ready"
    }
  ]
}
```

Ошибки: 401, 403, 404, 503.

## 4. Semantic search

### `POST /api/v1/search`

Auth: `X-API-Key`.
Rate limit: да.

Request:

```json
{
  "query": "серверы для центра обработки данных",
  "limit": 5
}
```

Validation:

- query: trim, 3..1000 символов;
- limit: 1..10, default 5.

200 response:

```json
{
  "query": "серверы для центра обработки данных",
  "items": [
    {
      "tender_id": "uuid",
      "title": "Supply of data centre hardware",
      "source": "ted",
      "source_url": "https://...",
      "snippet": "The required equipment includes rack servers...",
      "score": 0.8734,
      "attachment": {
        "id": "uuid",
        "filename": "technical-specification.pdf"
      }
    }
  ]
}
```

Пустой результат — 200 с `items: []`.

## 5. RAG answer

### `POST /api/v1/ask`

Auth: `X-API-Key`.
Rate limit: да, общий с `/search`.

Request:

```json
{"query":"Какие требования предъявлены к серверному оборудованию?"}
```

200 response:

```json
{
  "answer": "В найденных закупках требуется ...",
  "sources": [
    {
      "tender_id": "uuid",
      "title": "Supply of data centre hardware",
      "source_url": "https://...",
      "snippet": "...",
      "score": 0.8734
    }
  ]
}
```

Если контекста нет:

```json
{
  "answer": "Недостаточно данных для ответа.",
  "sources": []
}
```

Ollama timeout/5xx: 503 `dependency_unavailable`.

## 6. Rate-limit headers

На успешных `/search` и `/ask`:

```text
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 4
X-RateLimit-Reset: <unix timestamp следующей UTC-минуты>
```

На 429 дополнительно:

```text
Retry-After: <целое число секунд, минимум 1>
```

## 7. CLI API-key management

Обязательная команда:

```bash
python -m tender_lens.cli create-api-key --name demo --limit 5
```

Она:

1. создаёт 32+ байта криптографической случайности;
2. выводит префикс `tl_` и открытый ключ один раз;
3. сохраняет только SHA-256;
4. не логирует ключ вторично.

Допустимая команда для демонстрации:

```bash
python -m tender_lens.cli disable-api-key --name demo
```

## 8. CORS

Так как UI раздаётся тем же FastAPI origin, CORS middleware не требуется. Не добавлять wildcard CORS.
