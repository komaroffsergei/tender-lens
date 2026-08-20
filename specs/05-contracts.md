# 05. Контракты

## 1. Версионирование

- Внутренние контракты имеют суффикс `V1`.
- NATS event содержит `schema_version`.
- В рамках MVP допускаются только обратно совместимые добавления optional-полей.
- Переименование, смена типа или удаление поля требует `V2` и ADR.
- Pydantic models используют `extra="forbid"` для внутренних контрактов.
- Raw payload внешнего источника не валидируется внутренней схемой целиком.

JSON Schema находятся в `schemas/` и должны проверяться в CI.

## 2. `AttachmentRecordV1`

```python
class AttachmentRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str | None = None
    title: str | None = None
    filename: str
    source_url: AnyHttpUrl
    content_type: str | None = None
```

Правила:

- `filename` — только предпочтительное имя; downloader всё равно нормализует его;
- URL должен быть HTTP(S);
- пустые строки нормализуются в `None`, кроме обязательного filename.

## 3. `TenderRecordV1`

```python
class TenderRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["ted", "contracts_finder"]
    external_id: str
    title: str
    description: str | None = None
    buyer_name: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    published_at: datetime | None = None
    deadline: datetime | None = None
    source_url: AnyHttpUrl
    attachments: list[AttachmentRecordV1] = []
    raw_payload: dict[str, Any]
```

Нормализация:

- timestamps переводятся в UTC;
- currency — uppercase ISO-подобный трёхбуквенный код, если источник его дал;
- отрицательная amount отклоняется;
- title и external_id не могут быть пустыми;
- attachments сортируются по source_url перед вычислением hash;
- `content_hash` вычисляет crawler и не является полем адаптера.

## 4. NATS event `TenderChangedV1`

Subject:

```text
tender.changed.v1
```

Payload:

```json
{
  "schema_version": 1,
  "event_id": "uuid",
  "occurred_at": "2026-08-20T10:00:00Z",
  "tender_id": "uuid",
  "content_hash": "64 lowercase hex chars"
}
```

Событие не содержит:

- raw payload;
- full tender;
- binary attachment;
- embedding;
- секреты.

## 5. Search contract

Request:

```json
{
  "query": "серверное оборудование для дата-центра",
  "limit": 5
}
```

Response result:

```json
{
  "tender_id": "uuid",
  "title": "Supply of server equipment",
  "source": "ted",
  "source_url": "https://...",
  "snippet": "The contracting authority requires...",
  "score": 0.8734,
  "attachment": {
    "id": "uuid",
    "filename": "specification.pdf"
  }
}
```

`score = 1 - cosine_distance`, ограничивается диапазоном `[-1, 1]` только для сериализации; сортировка по убыванию.

## 6. Ask contract

Request совпадает с SearchRequest, но `limit` контекста по умолчанию и максимум равен 5.

Response:

```json
{
  "answer": "Краткий ответ, основанный только на найденных фрагментах.",
  "sources": [
    {
      "tender_id": "uuid",
      "title": "...",
      "source_url": "https://...",
      "snippet": "...",
      "score": 0.8734
    }
  ]
}
```

## 7. Error contract

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Превышен лимит запросов.",
    "request_id": "uuid",
    "details": null
  }
}
```

Коды:

- `validation_error` — 422;
- `api_key_required` — 401;
- `api_key_invalid` — 401;
- `api_key_disabled` — 403;
- `not_found` — 404;
- `rate_limit_exceeded` — 429;
- `dependency_unavailable` — 503;
- `internal_error` — 500 без технических деталей наружу.

## 8. Совместимость адаптеров

Оба адаптера обязаны проходить общий набор assertions:

- source указан корректно;
- external_id и title непустые;
- source_url абсолютный;
- amount неотрицательная;
- timestamps timezone-aware;
- attachment URLs абсолютные;
- raw_payload сериализуем в JSON;
- модель не содержит полей, специфичных только для одного источника.
