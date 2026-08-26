# Indexer

Indexer переводит сохранённую закупку и её документы в поисковые chunks. Он принимает at-least-once события, поэтому каждый шаг спроектирован как повторяемый и version-safe.

<dl class="module-contract">
  <dt>Вход</dt><dd>tender.changed.v1, PostgreSQL rows, attachment files</dd>
  <dt>Выход</dt><dd>chunks + VECTOR(1024), indexed_hash, index_status</dd>
  <dt>AI</dt><dd>FakeAIProvider в CI или Ollama embeddings в live</dd>
  <dt>Точка запуска</dt><dd><code>python -m tender_lens.indexer</code></dd>
</dl>

## Карта файлов

| Файл | Назначение |
|---|---|
| [`extract.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/indexer/extract.py) | метаданные + безопасное извлечение PDF/XML/HTML/JSON/TXT |
| [`chunk.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/indexer/chunk.py) | paragraph-first разбиение с overlap |
| [`service.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/indexer/service.py) | stale checks, batches и атомарная замена |
| [`__main__.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/indexer/__main__.py) | durable consumer, ACK/NAK/TERM policy |

## Извлечение

Каждый parser возвращает список [`TextUnit`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/indexer/extract.py#L20-L24): `attachment_id`, человекочитаемая `section`, `text`.

Метаданные индексируются тремя units: название отдельно, описание отдельно и агрегированная карточка. Это не даёт длинному description полностью размыть embedding title. Для PDF unit соответствует странице; для остальных поддержанных форматов — документу.

Unknown binary возвращает пустой список, а ошибка отдельного supported attachment становится warning. Поэтому доступные metadata всё равно индексируются.

## Chunking

[`chunk_units()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/indexer/chunk.py#L42-L81) сначала уважает абзацы, затем режет слишком длинный абзац по ближайшему пробелу. Максимум — 1500 символов, overlap — 150. Position монотонно растёт через все units одной закупки.

```text
TextUnit A: [chunk 0] [overlap → chunk 1]
TextUnit B: [chunk 2] [overlap → chunk 3]
```

Overlap сохраняет контекст возле границы, но увеличивает объём индекса; параметры выбраны как MVP-компромисс.

## Version-safe process

[`process()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/indexer/service.py#L70-L151) имеет три быстрых результата:

- `missing` — tender удалён/не существует;
- `stale` — event hash не равен текущему;
- `unchanged` — этот hash уже готов.

Для новой версии сервис ставит `processing`, извлекает и chunk-ит вне длинной DB-транзакции, вызывает embeddings batch-ами, затем снова блокирует tender и сверяет hash. Только после этого одна транзакция удаляет старые chunks, вставляет новые и ставит `ready`.

Если embedding или insert падает, старая версия chunks не была удалена. [`_mark_failed()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/indexer/service.py#L62-L68) меняет status только если tender всё ещё имеет hash падающего event.

## AI batches

`EMBEDDING_BATCH_SIZE` ограничивает число текстов в одном `/api/embed`. Это критично для CPU Ollama: один большой вызов избегает overhead отдельного HTTP request на chunk, а небольшие batches ограничивают память и latency.

Проверяются:

- число vectors равно числу drafts;
- каждый vector имеет 1024 компоненты;
- результаты собираются в исходном порядке;
- `zip(..., strict=True)` не скрывает рассинхронизацию.

## Политика сообщения

| Событие/ошибка | Действие |
|---|---|
| невалидный JSON/Pydantic | `TERM` |
| `missing/stale/unchanged/ready` | `ACK` |
| Ollama/PostgreSQL/OSError | `NAK(delay=10)` |
| неожиданная постоянная ошибка | `TERM` |

JetStream всё равно ограничивает доставку `max_deliver=5`, а `ack_wait=300s` должен быть больше нормальной индексации одного tender.
