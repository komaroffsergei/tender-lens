# TenderLens: публичный учебный корпус

Подготовлено 07.09.2026. Четыре собственных синтетических HTML-документа: серверы, резервное копирование, Angular-портал, мониторинг сети. Реальных заказчиков и закупок нет. Внешний crawler и Ollama не запускаются.

Реально работают нормализация TenderRecordV1, NATS JetStream, извлечение HTML, chunking, SQLAlchemy, PostgreSQL VECTOR(1024), cosine search, контроль отсутствия контекста и атомарный rate limiter. FakeAIProvider использует hashing trick; генерация — шаблон из найденных фрагментов. Cosine и вероятности не выдаются за качество модели.

Seed проходит `_upsert_demo_record` → TenderChangedV1 → NATS → IndexerService. Кнопка повторяет реальные события; unchanged content_hash позволяет worker идемпотентно пропустить повтор. Документы общие и read-only. Пользовательские запросы не сохраняются; счётчик лимита принадлежит подписанной часовой HttpOnly/Secure cookie. Просроченные demo ApiKey удаляются каждые пять минут. Сброс очищает интерфейс, сохраняя лимит сессии.

Публичная конфигурация запрещает live AI. До 30 запросов в минуту на сессию, до 1000 живых demo-ключей. JetStream ограничен 1000 событиями, 8 MiB и одним часом хранения. API и worker имеют собственные лимиты и ротацию логов. Worker readiness означает установленное соединение с очередью при старте; отдельный механизм определения зависшего вычисления не реализован.

| Функция | API/экран | Код | Данные |
|---|---|---|---|
| Начальная индексация | CLI portfolio | cli._upsert_demo_record, NatsBroker, IndexerService | sources, tenders, attachments, chunks |
| Поиск/ответ | api/v1/search, ask | SearchService, FakeAIProvider | chunks VECTOR(1024) |
| Источники | локальные HTML | web/demo | собственный корпус |
| Повтор события | api/demo/replay | NatsBroker / hash guard | общий read-only корпус |
| Сессия и лимит | cookie / middleware | portfolio, auth, rate_limit | api_keys (только хеш и счётчики) |

Перед изменением проследить DTO → событие → индексатор → SQL → SearchResponse. После изменения обновить code-map, схемы и проверить повтор события, ссылки на источники, отсутствие контекста и независимые лимиты двух сессий. Документация исходной live-архитектуры сохраняется отдельно от демо-архитектуры.
