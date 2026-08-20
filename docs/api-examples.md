# API TenderLens

Base URL: `http://localhost:8000`.

## Ошибки

```json
{
  "error": {
    "code": "api_key_required",
    "message": "Требуется заголовок X-API-Key.",
    "request_id": "uuid",
    "details": null
  }
}
```

Каждый ответ содержит `X-Request-ID`. Технический stack trace клиенту не возвращается.

## Health

```http
GET /health/live
GET /health/ready
```

`live` проверяет процесс. `ready` проверяет PostgreSQL и активный AI provider.

## Карточка закупки

```http
GET /api/v1/tenders/{uuid}
X-API-Key: tl_...
```

Ответ не содержит `raw_payload`, `content_hash`, `indexed_hash`, `local_path` и key hashes.

## Search

```http
POST /api/v1/search
Content-Type: application/json
X-API-Key: tl_...

{
  "query": "server storage warranty",
  "limit": 5
}
```

Пример:

```json
{
  "query": "server storage warranty",
  "items": [
    {
      "tender_id": "00000000-0000-0000-0000-000000000001",
      "title": "Supply of server and storage equipment",
      "source": "ted",
      "source_url": "https://example.test/tender/1",
      "snippet": "Technical requirements: rack servers...",
      "score": 0.84,
      "attachment": {
        "id": "00000000-0000-0000-0000-000000000002",
        "filename": "specification.pdf"
      }
    }
  ]
}
```

## Ask

```http
POST /api/v1/ask
Content-Type: application/json
X-API-Key: tl_...

{
  "query": "Какие сроки гарантии указаны?",
  "limit": 5
}
```

```json
{
  "answer": "В найденных документах указана гарантия 36 месяцев.",
  "sources": [
    {
      "tender_id": "00000000-0000-0000-0000-000000000001",
      "title": "Supply of server and storage equipment",
      "source": "ted",
      "source_url": "https://example.test/tender/1",
      "snippet": "Warranty period: 36 months...",
      "score": 0.91,
      "attachment": null
    }
  ]
}
```

При пустом индексе:

```json
{
  "answer": "Данных недостаточно для ответа по загруженной базе закупок.",
  "sources": []
}
```

## Rate limit

Первые пять запросов `/search` и `/ask` одного ключа в текущей UTC-минуте проходят. Следующий:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 17
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1787210400
```

Счётчик общий: три Search + два Ask исчерпывают лимит пять.
