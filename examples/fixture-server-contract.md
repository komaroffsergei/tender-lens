# Контракт локального fixture server для e2e

Fixture server может быть маленьким FastAPI-приложением внутри tests или pytest HTTP server fixture. Он не является production-сервисом и не входит в основной Compose.

## Endpoints

```text
POST /ted/v3/notices/search
GET  /contracts-finder/Published/Notices/OCDS/Search
GET  /files/sample_tender.pdf
GET  /files/sample_notice.xml
GET  /fail/429
GET  /fail/503
GET  /fail/slow
GET  /fail/truncated-file
```

## Управляемые сценарии

Query/header теста может выбирать:

- первая/следующая/пустая page;
- изменённая версия tender;
- 429 с `Retry-After`;
- 503;
- задержка больше timeout;
- файл больше limit;
- обрыв stream.

Fixture server обязан вести счётчик текущих и максимальных одновременных запросов для `CONC-001`.
