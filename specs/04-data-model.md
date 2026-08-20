# 04. Модель данных

## 1. Общие правила

- PostgreSQL с расширением `vector`.
- UUID генерируются приложением.
- Все timestamps — `TIMESTAMPTZ`, UTC.
- Денежные значения — `NUMERIC(20, 2)`.
- Не использовать PostgreSQL ENUM: небольшие строковые статусы защищаются CHECK constraints и Pydantic enums.
- Имена таблиц и колонок — snake_case.
- Миграции Alembic являются единственным способом изменения схемы.

## 2. Таблица `sources`

| Колонка | Тип | Ограничения | Назначение |
|---|---|---|---|
| `id` | UUID | PK | Идентификатор источника |
| `code` | VARCHAR(64) | NOT NULL, UNIQUE | `ted`, `contracts_finder` |
| `cursor` | TEXT | NULL | Последний подтверждённый cursor/token |
| `last_sync_at` | TIMESTAMPTZ | NULL | Последний успешный sync |
| `created_at` | TIMESTAMPTZ | NOT NULL | Создание |
| `updated_at` | TIMESTAMPTZ | NOT NULL | Изменение |

## 3. Таблица `tenders`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `source_id` | UUID | FK `sources.id`, NOT NULL |
| `external_id` | TEXT | NOT NULL |
| `title` | TEXT | NOT NULL |
| `description` | TEXT | NULL |
| `buyer_name` | TEXT | NULL |
| `amount` | NUMERIC(20,2) | NULL, CHECK >= 0 |
| `currency` | VARCHAR(3) | NULL |
| `published_at` | TIMESTAMPTZ | NULL |
| `deadline` | TIMESTAMPTZ | NULL |
| `source_url` | TEXT | NOT NULL |
| `content_hash` | CHAR(64) | NOT NULL |
| `indexed_hash` | CHAR(64) | NULL |
| `index_status` | VARCHAR(16) | NOT NULL, default `pending`, CHECK in `pending,processing,ready,failed` |
| `last_error` | TEXT | NULL |
| `raw_payload` | JSONB | NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

Ограничения и индексы:

```sql
UNIQUE (source_id, external_id)
INDEX (published_at DESC)
INDEX (deadline)
INDEX (index_status)
INDEX (content_hash)
```

## 4. Таблица `attachments`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `tender_id` | UUID | FK `tenders.id` ON DELETE CASCADE, NOT NULL |
| `external_id` | TEXT | NULL |
| `title` | TEXT | NULL |
| `filename` | TEXT | NOT NULL |
| `source_url` | TEXT | NOT NULL |
| `local_path` | TEXT | NULL |
| `content_type` | TEXT | NULL |
| `sha256` | CHAR(64) | NULL |
| `size_bytes` | BIGINT | NULL, CHECK >= 0 |
| `download_status` | VARCHAR(16) | NOT NULL, CHECK in `pending,ready,failed,skipped` |
| `error_message` | TEXT | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |
| `updated_at` | TIMESTAMPTZ | NOT NULL |

Ограничения:

```sql
UNIQUE (tender_id, source_url)
INDEX (tender_id)
INDEX (sha256)
```

## 5. Таблица `chunks`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `tender_id` | UUID | FK `tenders.id` ON DELETE CASCADE, NOT NULL |
| `attachment_id` | UUID | FK `attachments.id` ON DELETE CASCADE, NULL |
| `chunk_key` | CHAR(64) | NOT NULL, UNIQUE |
| `position` | INTEGER | NOT NULL, CHECK >= 0 |
| `section` | TEXT | NULL |
| `content` | TEXT | NOT NULL, CHECK length > 0 |
| `content_hash` | CHAR(64) | NOT NULL |
| `embedding` | VECTOR(1024) | NOT NULL |
| `embedding_model` | VARCHAR(128) | NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |

Индексы:

```sql
INDEX (tender_id)
INDEX (attachment_id)
```

В MVP **не создавать** HNSW/IVFFlat. Exact search выполняется полным сканированием небольшого корпуса.

`chunk_key` вычисляется детерминированно из:

```text
tender_id + attachment_id-or-metadata + position + content_hash + embedding_model
```

## 6. Таблица `api_keys`

| Колонка | Тип | Ограничения |
|---|---|---|
| `id` | UUID | PK |
| `name` | VARCHAR(128) | NOT NULL |
| `key_hash` | CHAR(64) | NOT NULL, UNIQUE |
| `enabled` | BOOLEAN | NOT NULL, default true |
| `limit_per_minute` | INTEGER | NOT NULL, default 5, CHECK 1..1000 |
| `window_started_at` | TIMESTAMPTZ | NULL |
| `request_count` | INTEGER | NOT NULL, default 0, CHECK >= 0 |
| `last_used_at` | TIMESTAMPTZ | NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL |

Открытый API key никогда не сохраняется.

## 7. Канонический `content_hash`

Hash строится из JSON с сортировкой ключей и стабильным порядком вложений. Включаются:

- source;
- external_id;
- title;
- description;
- buyer_name;
- amount как строка в нормализованном формате;
- currency;
- published_at/deadline в UTC ISO 8601;
- source_url;
- список вложений, отсортированный по `source_url`, только с external_id/title/filename/source_url/content_type.

Не включаются:

- raw_payload целиком;
- локальный path;
- время скачивания;
- created_at/updated_at;
- retry counters;
- порядок ключей внешнего JSON.

## 8. Состояния индекса

```text
pending    — требуется публикация/индексация
processing — indexer начал текущую попытку
ready      — indexed_hash == content_hash
failed     — последняя попытка завершилась ошибкой
```

Новая версия не удаляет старые chunks до готовности новых embeddings и открытия транзакции замены.
