# 11. Definition of Done

## 1. Функциональность

- [ ] TED adapter получает и нормализует закупки.
- [ ] Contracts Finder adapter получает и нормализует закупки.
- [ ] Оба проходят общий contract-test.
- [ ] Crawler ограничивает concurrency и соблюдает retry/delay.
- [ ] Metadata сохраняются в PostgreSQL.
- [ ] Вложения скачиваются потоково и безопасно.
- [ ] Повторный crawl не создаёт дубли.
- [ ] Изменение significant field меняет content hash.
- [ ] `tender.changed.v1` публикуется только для new/changed.
- [ ] JetStream redelivery работает.
- [ ] Indexer идемпотентен.
- [ ] Текст извлекается из обязательных форматов.
- [ ] Chunks соответствуют размеру/overlap.
- [ ] Embeddings сохраняются как VECTOR(1024).
- [ ] Exact cosine search возвращает top-k.
- [ ] `/ask` grounded и возвращает sources.
- [ ] При отсутствии контекста LLM не вызывается.
- [ ] API key хранится только как hash.
- [ ] 5 запросов проходят, 6-й возвращает 429.
- [ ] Static UI выполняет Search и Ask.

## 2. Тестирование

- [ ] Все обязательные test IDs реализованы или mapped к параметризованным тестам.
- [ ] Unit tests не используют внешнюю сеть.
- [ ] Integration tests используют настоящий PostgreSQL/pgvector и NATS.
- [ ] E2E проходит с fixture source и fake AI.
- [ ] Live tests отделены marker-ом и не входят в CI.
- [ ] Каждый найденный дефект имеет regression test.
- [ ] `black --check .` green.
- [ ] `flake8 src tests` green.
- [ ] `mypy src` green.
- [ ] `pytest` green.
- [ ] Migration from clean DB green.
- [ ] Docker build green.
- [ ] Compose config green.

## 3. Документация

- [ ] README объясняет, что основное задание — №7.
- [ ] Quick start проверен на чистом Compose.
- [ ] Architecture и sequence diagrams актуальны.
- [ ] Algorithm описывает crawl/index/search/rate-limit.
- [ ] API examples соответствуют OpenAPI.
- [ ] `docs/code-map.md` соответствует фактическому tree.
- [ ] `docs/traceability.md` связывает MUST → code → tests.
- [ ] `docs/progress.md` содержит реальные commit/CI data.
- [ ] Trade-offs честно описывают shared DB, fixed window, exact search и volume.
- [ ] Комментарии/docstrings на русском и объясняют неочевидное.
- [ ] Нет устаревших команд или ссылок.

## 4. Git/GitHub

- [ ] Initial specs commit находится в `main`.
- [ ] Работа выполнена в `feature/tender-lens`.
- [ ] На каждый stage есть implementation и test/docs commits, кроме stage 00.
- [ ] После каждого push проверен GitHub Actions run.
- [ ] Нет force push и переписанной публичной истории.
- [ ] Pull Request содержит summary, tests, demo, limitations.
- [ ] Merge выполнен merge commit-ом либо blocker честно указан.
- [ ] `main` CI green.
- [ ] Annotated tag `v0.1.0` создан после merge.
- [ ] Репозиторий публичный.
- [ ] MIT LICENSE присутствует.

## 5. Безопасность и чистота

- [ ] Нет secrets/API keys в Git history и logs.
- [ ] Нет live attachments и больших models в repository.
- [ ] `.env` игнорируется.
- [ ] Path traversal тесты проходят.
- [ ] XML external entities выключены.
- [ ] UI не использует unsafe `innerHTML` с внешними данными.
- [ ] Prompt injection рассматривается как data.
- [ ] Ошибки не раскрывают stack/DSN/path.
- [ ] Нет TODO/pass/dead code в завершённых stages.

## 6. Финальное доказательство

Готовность определяется не текстом отчёта, а ссылками и командами:

- repository URL;
- PR URL;
- head/merge SHA;
- CI run URLs и conclusions;
- test summary;
- команды запуска;
- screenshot UI;
- demo output Search/Ask/429.
