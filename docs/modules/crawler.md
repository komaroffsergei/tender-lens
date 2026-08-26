# Crawler

Crawler — основное тестовое задание. Он асинхронно опрашивает два официальных API, нормализует записи, безопасно скачивает файлы, сохраняет metadata и публикует событие индексации.

<dl class="module-contract">
  <dt>Вход</dt><dd>TED Search API v3, Contracts Finder OCDS Search или fixture JSON</dd>
  <dt>Выход</dt><dd>sources/tenders/attachments, файлы volume, tender.changed.v1</dd>
  <dt>Параллельность</dt><dd>asyncio tasks + отдельные BoundedSemaphore для API и attachments</dd>
  <dt>Точка запуска</dt><dd><code>python -m tender_lens.crawler</code></dd>
</dl>

## Карта файлов

| Файл | Зачем существует | Ключевой символ |
|---|---|---|
| [`base.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/base.py) | единый adapter protocol и HTTP safety/retry policy | [`ResilientHttpClient`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/base.py#L37-L252) |
| [`ted.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/ted.py) | TED fields, pagination token и mapping | [`TedAdapter`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/ted.py#L64-L171) |
| [`contracts_finder.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/contracts_finder.py) | OCDS release, cursor и documents | [`ContractsFinderAdapter`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/contracts_finder.py#L55-L139) |
| [`fixture.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/fixture.py) | offline source для E2E/демо | [`FixtureAdapter`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/fixture.py#L13-L33) |
| [`service.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/service.py) | транзакционный orchestration | [`CrawlerService`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/service.py#L49-L297) |
| [`__main__.py`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/__main__.py) | wiring, source isolation и interval loop | [`run()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/__main__.py#L75-L146) |

## 1. Adapter boundary

[`SourceAdapter`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/base.py#L27-L34) требует только `source_code` и `fetch_page(cursor, limit)`. Результат [`SourcePage`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/base.py#L19-L24) содержит нормализованные records и следующий opaque cursor.

TED использует POST search с `paginationMode=ITERATION`, а Contracts Finder — GET с `cursor` query parameter. Разница не просачивается в `CrawlerService`.

## 2. HTTP policy

`ResilientHttpClient` выполняет один алгоритм для JSON и stream:

1. проверяет scheme/host/IP;
2. добавляет politeness delay + jitter;
3. занимает semaphore только на время активного HTTP I/O;
4. не следует redirect автоматически;
5. разрешает максимум пять redirect независимо от retry attempts;
6. повторяет timeout/network/429/5xx, а Contracts Finder ещё 403 с cooldown;
7. уважает числовой или HTTP-date `Retry-After`;
8. переводит исчерпание попыток в `SourceRequestError`.

Отдельный instance для source pages и attachments не позволяет крупным файлам занять все слоты JSON polling.

## 3. Mapping

`TedAdapter.map_notice()` использует tolerant helpers `_first`, `_string`, `_datetime`, `_decimal`, потому что Search API может возвращать локализованные/списочные формы. Он создаёт PDF/XML attachments только из официальных `links`.

`ContractsFinderAdapter.map_release()` читает OCDS `tender`, `buyer`, `value`, `tenderPeriod`, `documents`. Missing optional field становится `None`; отсутствие id/title отклоняет только конкретную release и пишет warning.

## 4. Persistence

[`persist_record()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/service.py#L77-L162):

- вычисляет canonical `content_hash`;
- находит tender по `(source_id, external_id)`;
- обновляет поля всегда, но ставит `pending` только при новом hash;
- сопоставляет attachments по `source_url`;
- отсутствующие в новой версии помечает `skipped`;
- commit-ит tender и attachment metadata одной транзакцией;
- возвращает UUID и флаг `changed`, не ORM-object привязанный к закрытой session.

## 5. Attachment pipeline

[`download_record_attachments()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/service.py#L213-L219) запускает независимые coroutines через `asyncio.gather`; реальный верхний предел задаёт semaphore HTTP client. [`_download_one()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/service.py#L164-L211) пропускает уже готовый файл, записывает успех или короткую ошибку, и при новом файле переводит готовый tender обратно в `pending`.

## 6. Cursor и recovery

Cursor хранится отдельно для `ted` и `contracts_finder`. Повтор одного ненулевого cursor внутри запуска считается ошибкой источника и предотвращает бесконечный цикл. [`republish_pending()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/crawler/service.py#L234-L247) восстанавливает разрыв «DB commit прошёл, NATS publish не прошёл».

## 7. Source isolation

Entry point создаёт клиентов и сервис внутри цикла по источникам. Исключение TED логируется и не запрещает попытку Contracts Finder; `CancelledError` не поглощается, чтобы контейнер завершался корректно.

## Что не является «обходом роботов»

Проект использует открытые API, User-Agent, задержки, jitter и ограничение concurrency. Он не ломает CAPTCHA, авторизацию, WAF или robots policy. Это сознательная этическая и эксплуатационная граница.
