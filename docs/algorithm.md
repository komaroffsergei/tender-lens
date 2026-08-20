# Алгоритмы TenderLens

## 1. Получение данных

### Единый адаптер

```python
class SourceAdapter(Protocol):
    source_code: str

    async def fetch_page(self, cursor: str | None, limit: int) -> SourcePage:
        ...
```

TED и Contracts Finder имеют разные внешние JSON-структуры, но возвращают одну Pydantic-модель `TenderRecordV1`.

### HTTP-политика

Для каждого запроса:

1. проверить `http/https` и allowlist host;
2. дождаться базовой задержки + jitter;
3. занять `BoundedSemaphore`;
4. выполнить запрос с timeout;
5. вручную проверить redirect target;
6. на `429/5xx`, timeout или network error выполнить ограниченный retry;
7. учитывать `Retry-After`;
8. после исчерпания попыток вернуть typed error.

Contracts Finder может использовать отдельный cooldown на `403`; для остальных источников `403` не ретраится.

### Обработка страницы

1. получить cursor из `sources`;
2. запросить одну страницу;
3. пропустить и залогировать отдельные malformed records;
4. для каждой записи выполнить `persist_record`;
5. скачать новые/ошибочные вложения;
6. опубликовать event при изменении метаданных или готовности нового файла;
7. только после всей порции обновить cursor.

## 2. Детерминированный hash и UPSERT

В hash входят нормализованные значимые поля и отсортированный список вложений. Не входят timestamps обработки и состояние индекса.

```text
canonical normalized payload
        ↓ JSON sort_keys
      SHA-256
```

Результат:

- новая запись: `index_status=pending`;
- тот же hash: повторная индексация не требуется;
- новый hash: поля обновляются, `index_status=pending`, старый `indexed_hash` сохраняется до успешного reindex.

## 3. Скачивание вложения

1. очистить имя и построить путь внутри root;
2. открыть HTTP stream;
3. проверить `Content-Length`, если он есть;
4. писать в `.part` небольшими chunks;
5. одновременно считать SHA-256 и фактический размер;
6. при превышении лимита удалить временный файл;
7. после полного успеха выполнить atomic `replace`;
8. сохранить path, hash, size и content type.

Ошибка одного вложения не прекращает обработку остальных закупок.

## 4. Событие NATS

```json
{
  "schema_version": 1,
  "event_id": "uuid",
  "occurred_at": "2026-08-20T10:00:00Z",
  "tender_id": "uuid",
  "content_hash": "64 hex"
}
```

Crawler публикует событие после DB commit. JetStream использует `Nats-Msg-Id=event_id` и durable consumer.

## 5. Извлечение текста

Indexer формирует `TextUnit` из:

- метаданных закупки с понятными label;
- PDF с текстовым слоем;
- XML;
- HTML без `script/style`;
- JSON;
- TXT.

Unsupported binary сохраняется как вложение, но возвращает пустой список текста и не ломает весь tender.

## 6. Чанкинг

1. сохранить границу `TextUnit` и section;
2. разделить текст по пустым строкам;
3. собирать chunk до `1500` символов;
4. переносить хвост не более `150` символов в следующий chunk;
5. не сохранять пустые chunks;
6. вычислить детерминированный content hash и chunk key.

## 7. Embeddings и атомарная индексация

1. проверить, что event не stale и ещё не обработан;
2. собрать все drafts;
3. вызвать `AIProvider.embed()` одним batch;
4. проверить count и размерность каждого вектора (`1024`);
5. повторно заблокировать tender и сверить hash;
6. в одной транзакции удалить старые chunks, добавить новые и поставить `ready`;
7. после commit ACK event.

При ошибке embeddings/insert старые chunks остаются доступными.

## 8. Exact semantic search

1. проверить query и limit;
2. получить один query embedding той же моделью;
3. выполнить SQL:

```sql
ORDER BY chunks.embedding <=> CAST(:embedding AS vector)
LIMIT :limit
```

4. преобразовать distance в cosine similarity `1 - distance`;
5. вернуть sanitized metadata и snippet, не раскрывая raw payload, hashes и local paths.

## 9. Grounded RAG

1. выполнить тот же retrieval;
2. если список пуст, не вызывать generation и вернуть детерминированный ответ о недостатке данных;
3. передать максимум top-k fragments;
4. system prompt объявляет документы недоверенными данными;
5. модель должна отвечать только по контексту;
6. API возвращает текст и ровно те sources, которые пришли из retrieval.

## 10. API-key и rate limit

### Аутентификация

```text
X-API-Key → SHA-256 → lookup api_keys.key_hash → enabled check
```

Открытый key не сохраняется.

### Fixed UTC-minute

Для `/search` и `/ask` используется общий счётчик одного ключа:

1. `SELECT ... FOR UPDATE` по UUID ключа;
2. определить начало текущей UTC-минуты;
3. при новом окне сбросить count;
4. если count достиг limit, rollback и `429`;
5. иначе увеличить count и commit.

Row lock обеспечивает атомарность между конкурентными API-processes, работающими с одной БД.
