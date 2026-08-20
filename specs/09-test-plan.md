# 09. Полный тестовый план

## 1. Правила

- Каждый `MUST` requirement имеет хотя бы один test ID.
- Один параметризованный тест может закрывать несколько ID, но mapping фиксируется в `docs/traceability.md`.
- Live tests имеют marker `live` и не входят в обычный CI.
- Unit tests не используют сеть/БД/NATS.
- Integration tests используют настоящий PostgreSQL/pgvector и NATS.
- E2E использует локальный mock source и fake AI.
- Исправленный дефект всегда получает новый regression test ID вида `REG-XXX`.

## 2. Stage 00–02: структура, качество, инфраструктура

| ID | Уровень | Проверка | Ожидаемый результат |
|---|---|---|---|
| BOOT-001 | static | Все обязательные spec/schema/diagram files существуют | Проверка проходит |
| BOOT-002 | unit | Все JSON Schema валидны по meta-schema | Нет ошибок |
| BOOT-003 | static | Нет пустых обязательных файлов/TODO в stage deliverables | Нет нарушений |
| PKG-001 | unit | Импорт `tender_lens` | Импорт успешен |
| PKG-002 | unit | Entry points `crawler`, `indexer`, `api`, `cli` импортируются без side effects | Успешно |
| CONF-001 | unit | Значения defaults валидны | Settings создаются |
| CONF-002 | unit | Некорректный max concurrency/size/limit отклоняется | Validation error |
| CONF-003 | unit | Secret fields не попадают в repr/log | Значения замаскированы |
| LOG-001 | unit | JSON log содержит timestamp, level, message, request_id | Поля присутствуют |
| DOCKER-001 | static | `docker compose config` | Exit 0 |
| DOCKER-002 | build | Один application image собирается | Exit 0 |
| DOCKER-003 | smoke | Три роли выполняют `--help`/smoke command из одного image | Exit 0 |
| DOCKER-004 | static | Container user не root | Проверка проходит |
| INFRA-001 | integration | PostgreSQL healthcheck | Healthy |
| INFRA-002 | integration | NATS JetStream доступен | Stream API отвечает |
| INFRA-003 | integration | Ollama health endpoint доступен в live compose | Healthy или явно skipped в fake CI |

## 3. Stage 03–04: база и контракты

| ID | Уровень | Проверка | Ожидаемый результат |
|---|---|---|---|
| DB-001 | integration | `alembic upgrade head` на чистой БД | Все таблицы созданы |
| DB-002 | integration | `alembic downgrade base` и повторный upgrade | Успешно |
| DB-003 | integration | Расширение `vector` включено | Extension существует |
| DB-004 | integration | Созданы ровно пять application tables | Ровно ожидаемый набор |
| DB-005 | integration | Unique `(source_id, external_id)` | Duplicate отклонён |
| DB-006 | integration | CHECK статусов и nonnegative amount/size | Invalid row отклонён |
| DB-007 | integration | Cascade tender delete | Attachments/chunks удалены |
| DB-008 | integration | Transaction rollback | Частичные данные отсутствуют |
| HASH-001 | unit | Сортировка ключей raw JSON не влияет на hash | Hash одинаков |
| HASH-002 | unit | Порядок attachments не влияет на hash | Hash одинаков |
| HASH-003 | unit | Изменение title/amount/deadline меняет hash | Hash различается |
| HASH-004 | unit | Processing timestamps не влияют на hash | Hash одинаков |
| UPSERT-001 | integration | Новый tender | created=true, pending |
| UPSERT-002 | integration | Неизменённый tender | created=false, changed=false |
| UPSERT-003 | integration | Изменённый tender | changed=true, pending, indexed_hash не подменён |
| APIKEY-DB-001 | integration | Создание ключа | В БД только hash |
| APIKEY-DB-002 | integration | Duplicate hash | Отклонён |
| CONTRACT-001 | unit | Valid TenderRecordV1 | Принимается |
| CONTRACT-002 | unit | Empty title/external_id | Отклоняется |
| CONTRACT-003 | unit | Negative amount | Отклоняется |
| CONTRACT-004 | unit | Naive datetime | Нормализован/отклонён согласно реализации |
| CONTRACT-005 | unit | Extra internal field | Отклоняется |
| SCHEMA-001 | unit | Pydantic schema совместима с checked-in JSON Schema | Нет drift |

## 4. Stage 05–06: TED и crawler

| ID | Уровень | Проверка | Ожидаемый результат |
|---|---|---|---|
| TED-001 | unit | Обычный fixture | Валидный TenderRecordV1 |
| TED-002 | unit | Optional fields отсутствуют | Модель валидна, None |
| TED-003 | unit | Пустой result set | Пустой iterator |
| TED-004 | unit | Несколько notices | Все записи возвращены |
| TED-005 | unit | Invalid notice без ID/title | Запись пропущена/ошибка изолирована и залогирована |
| TED-006 | unit | Pagination/iteration token | Следующая страница запрошена один раз |
| TED-007 | unit | Config max pages/items | Лимит соблюдён |
| HTTP-001 | unit | 200 | Ответ возвращён |
| HTTP-002 | unit | 429 + Retry-After seconds | Ожидание рассчитано по header |
| HTTP-003 | unit | 503 без header | Exponential backoff + jitter |
| HTTP-004 | unit | Connect/read timeout | Retry до max attempts |
| HTTP-005 | unit | Исчерпание retry | Явная typed error |
| HTTP-006 | unit | 404 attachment | Attachment failed, tender processing продолжается |
| HTTP-007 | unit | Redirect на разрешённый host | Разрешён |
| HTTP-008 | unit | Redirect на неразрешённый host | Заблокирован |
| CONC-001 | unit | 20 mock requests при limit 3 | Max observed concurrency <= 3 |
| CURSOR-001 | integration | Успешная порция | Cursor обновлён после commit |
| CURSOR-002 | integration | Ошибка до конца порции | Cursor не продвинут |
| CRAWL-001 | integration | Первый crawl | Tender/attachments созданы |
| CRAWL-002 | integration | Повторный crawl | Дублей нет |
| CRAWL-003 | integration | Изменённый fixture | content_hash изменён, pending |
| CRAWL-004 | integration | Первый source падает | Второй source запускается |
| FILE-001 | unit | Safe filename | Получен basename без traversal |
| FILE-002 | unit | `../../x.pdf` | Нормализован безопасно |
| FILE-003 | unit | Null byte/absolute path | Отклонён/очищен |
| FILE-004 | unit | Stream до лимита | Файл и SHA-256 корректны |
| FILE-005 | unit | Content-Length больше лимита | Отказ до download |
| FILE-006 | unit | Поток превысил лимит | Temp file удалён |
| FILE-007 | unit | Соединение оборвано | Temp file удалён, status failed |
| FILE-008 | integration | Повторная ссылка | Duplicate attachment не создан |
| FILE-009 | integration | Одинаковый SHA у двух URL | Файлы допустимы, metadata корректна; поведение задокументировано |

## 5. Stage 07: NATS

| ID | Уровень | Проверка | Ожидаемый результат |
|---|---|---|---|
| NATS-001 | integration | Создание stream впервые | Stream создан |
| NATS-002 | integration | Повторная инициализация | Ошибки нет, config совместим |
| NATS-003 | integration | Создание durable consumer | Consumer создан |
| NATS-004 | unit | Event schema valid | Принимается |
| NATS-005 | unit | Invalid UUID/hash/version/extra field | Отклоняется |
| NATS-006 | integration | New tender after DB commit | Одно событие опубликовано |
| NATS-007 | integration | Unchanged tender | Событие не опубликовано |
| NATS-008 | integration | Publish failure | Tender остаётся pending |
| NATS-009 | integration | Следующий цикл pending scan | Событие опубликовано повторно |
| NATS-010 | integration | Consumer без ACK | Сообщение доставляется повторно |
| NATS-011 | integration | ACK после success | Повторной доставки нет |

## 6. Stage 08–09: extraction, chunking, embeddings, search

| ID | Уровень | Проверка | Ожидаемый результат |
|---|---|---|---|
| EXTRACT-001 | unit | Metadata text | Поля с понятными labels включены |
| EXTRACT-002 | unit | Text PDF fixture | Текст извлечён |
| EXTRACT-003 | unit | PDF без text layer | Пустой result + warning, pipeline жив |
| EXTRACT-004 | unit | Malformed PDF | Typed extraction error изолирован |
| EXTRACT-005 | unit | XML с external entity | Entity не разрешается |
| EXTRACT-006 | unit | HTML | Теги удалены, script/style не включены |
| EXTRACT-007 | unit | JSON/TXT | Текст извлечён |
| EXTRACT-008 | unit | Unsupported binary | Skip без падения |
| CHUNK-001 | unit | Короткий абзац | Один chunk |
| CHUNK-002 | unit | Длинный текст | Каждый chunk <= 1500 |
| CHUNK-003 | unit | Overlap | <=150 и содержание перекрывается |
| CHUNK-004 | unit | Пустые/whitespace абзацы | Не создают chunks |
| CHUNK-005 | unit | Unicode/русский текст | Не повреждён |
| CHUNK-006 | unit | Детерминированность | Повторный запуск даёт те же chunks/keys |
| INDEX-001 | integration | Fake embeddings + valid event | Chunks сохранены, ready |
| INDEX-002 | integration | Same indexed_hash | Нет новых chunks, ACK |
| INDEX-003 | integration | Ошибка во время insert | Старые chunks остаются, no ACK |
| INDEX-004 | integration | Ошибка embeddings | Status failed, no partial chunks |
| INDEX-005 | integration | Event content_hash не совпадает с текущим tender | Stale event ACK/skip, новое состояние не портится |
| OLLAMA-EMB-001 | unit | Batch request contract | Один request с массивом input |
| OLLAMA-EMB-002 | unit | Порядок векторов | Совпадает с input order |
| OLLAMA-EMB-003 | unit | Vector length 1024 | Принимается |
| OLLAMA-EMB-004 | unit | Wrong vector length/count | Typed error, запись запрещена |
| OLLAMA-EMB-005 | unit | Timeout/5xx/malformed JSON | Typed dependency error |
| SEARCH-001 | integration | Deterministic fake corpus | Ожидаемый top-1/top-k |
| SEARCH-002 | integration | Порядок cosine similarity | По убыванию score |
| SEARCH-003 | integration | Empty chunks | Empty list |
| SEARCH-004 | unit | limit 1/5/10 | Соблюдается |
| SEARCH-005 | unit | limit 0/11 | Validation error |
| SEARCH-006 | integration | Deleted tender | Результаты отсутствуют |
| LIVE-EMB-001 | live | Реальный Ollama embed | 1024 values, non-empty |

## 7. Stage 10: Contracts Finder

| ID | Уровень | Проверка | Ожидаемый результат |
|---|---|---|---|
| CF-001 | unit | OCDS fixture | Валидный TenderRecordV1 |
| CF-002 | unit | Planning-only release | Доступные поля нормализованы |
| CF-003 | unit | Tender/award fields | Приоритет полей документирован и соблюдён |
| CF-004 | unit | Missing buyer/value/date | None, модель валидна |
| CF-005 | unit | Document links | Attachments нормализованы |
| CF-006 | unit | Cursor pagination | Следующий cursor использован |
| CF-007 | unit | limit >100 config | Ограничен/validation error |
| CF-008 | unit | 403 rate limit | Источник приостанавливается на заданный срок |
| ADAPTER-001 | contract | Общий contract test TED | Pass |
| ADAPTER-002 | contract | Общий contract test CF | Pass |
| ADAPTER-003 | integration | Одинаковый external_id разных sources | Две независимые записи |

## 8. Stage 11–12: API, auth, limiter, search

| ID | Уровень | Проверка | Ожидаемый результат |
|---|---|---|---|
| API-HEALTH-001 | api | live health | 200 без зависимостей |
| API-HEALTH-002 | api | ready, БД/Ollama доступны | 200 |
| API-HEALTH-003 | api | БД недоступна | 503 |
| API-HEALTH-004 | api | Ollama недоступна | 503 |
| AUTH-001 | api | Нет X-API-Key | 401 stable error |
| AUTH-002 | api | Неизвестный key | 401 |
| AUTH-003 | api | Disabled key | 403 |
| AUTH-004 | api | Valid key | Request продолжен |
| AUTH-005 | unit | CLI key generation | Достаточная entropy, prefix, hash persisted |
| AUTH-006 | unit | Key absent from logs/repr | Не найден |
| RATE-001 | integration | Запросы 1..5 | 200 и корректный remaining |
| RATE-002 | integration | Шестой запрос | 429 + headers |
| RATE-003 | integration | Два ключа | Счётчики независимы |
| RATE-004 | integration | 10 concurrent requests | Ровно 5 пропущено |
| RATE-005 | unit | Новый UTC-minute через fake clock | Counter reset |
| RATE-006 | unit | 429 не увеличивает count | Count остаётся limit |
| RATE-007 | api | GET tender details | Auth нужен, limiter не расходуется |
| RATE-008 | api | Search и Ask | Используют общий counter |
| API-SEARCH-001 | api | Valid request | 200 contract |
| API-SEARCH-002 | api | Query <3, >1000, blank | 422 |
| API-SEARCH-003 | api | Empty index | 200 items=[] |
| API-SEARCH-004 | api | Result fields | Нет raw payload/path/hash |
| API-TENDER-001 | api | Existing tender | 200 sanitized model |
| API-TENDER-002 | api | Unknown UUID | 404 |
| API-ERR-001 | api | Internal exception | 500 generic, request_id |

## 9. Stage 13: RAG

| ID | Уровень | Проверка | Ожидаемый результат |
|---|---|---|---|
| RAG-001 | unit | Prompt assembly | Только top results и правила grounding |
| RAG-002 | unit | Document contains instruction | Instruction остаётся quoted context, не system rule |
| RAG-003 | api | Fake answer | 200 + sources |
| RAG-004 | api | No results | Детерминированный insufficient-data, generation не вызван |
| RAG-005 | unit | Source list | Только retrieval IDs |
| RAG-006 | unit | Malformed model response | Dependency error |
| RAG-007 | api | Ollama timeout | 503 stable error |
| RAG-008 | api | Ollama 5xx | 503 |
| RAG-009 | api | Model returns empty text | 503/typed invalid response |
| RAG-010 | api | Rate limit shared with search | Шестой mixed request 429 |
| LIVE-RAG-001 | live | Реальная локальная генерация | Ответ и sources, ручная оценка grounding |

## 10. Stage 14: UI

| ID | Уровень | Проверка | Ожидаемый результат |
|---|---|---|---|
| UI-001 | api | `/` | 200 HTML |
| UI-002 | api | CSS/JS assets | 200, local |
| UI-003 | static | Нет внешних CDN/npm references | Pass |
| UI-004 | static | Нет hardcoded API key | Pass |
| UI-005 | dom/smoke | Required labels/elements | Присутствуют |
| UI-006 | dom/smoke | Loading state | Button disabled, aria-busy |
| UI-007 | dom/smoke | Empty state | Понятный текст |
| UI-008 | dom/smoke | 401/429/503 | Разные сообщения |
| UI-009 | static | External strings use textContent | Нет unsafe innerHTML path |
| UI-010 | dom/smoke | sessionStorage key | Не попадает в URL/DOM |
| UI-011 | screenshot | 1440x1024 и 390x844 | Нет критического overflow |

## 11. Stage 15: E2E и поставка

| ID | Уровень | Проверка | Ожидаемый результат |
|---|---|---|---|
| E2E-001 | e2e | Fixture TED → DB → NATS → indexer → search | Ожидаемый result |
| E2E-002 | e2e | Fixture CF → тот же pipeline | Ожидаемый result |
| E2E-003 | e2e | Повторный crawl | Количество tenders/chunks не растёт |
| E2E-004 | e2e | Изменение tender | Новые chunks заменяют старые |
| E2E-005 | e2e | Ask | Answer grounded, sources valid |
| E2E-006 | e2e | Sixth protected request | 429 |
| E2E-007 | e2e | Indexer offline, затем online | Накопленное сообщение обработано |
| MIG-001 | CI | Migration from clean DB | Pass |
| MIG-002 | CI | Models and migration schema smoke | Нет явного drift |
| CI-001 | CI | black | Pass |
| CI-002 | CI | flake8 | Pass |
| CI-003 | CI | mypy | Pass |
| CI-004 | CI | unit tests | Pass |
| CI-005 | CI | integration/e2e | Pass |
| CI-006 | CI | Docker build | Pass |
| CI-007 | CI | Compose config | Pass |
| CI-008 | CI | Нет live network/model pull | Подтверждено workflow |
| DOC-001 | static | Все команды README воспроизводимы | Проверены |
| DOC-002 | static | Code-map соответствует tree | Проверено скриптом/ручным gate |
| DOC-003 | static | Traceability без orphan MUST | Все MUST mapped |
| GIT-001 | process | Два+ содержательных commits на stage | История подтверждает |
| GIT-002 | process | Push/CI после каждого gate | URLs записаны в progress |
| GIT-003 | process | PR и merge commit | Выполнено либо честно blocked |
| RELEASE-001 | process | Tag v0.1.0 | Создан после merge |

## 12. Ручной demo checklist

- [ ] Запущен Compose.
- [ ] Создан demo key.
- [ ] Выполнен crawler `--once` минимум для одного live source или явно указан fake режим.
- [ ] Есть tender со статусом `ready`.
- [ ] Search возвращает источники.
- [ ] Ask возвращает grounded answer.
- [ ] Шестой запрос возвращает 429.
- [ ] UI открыт и отображает те же данные.
- [ ] GitHub Actions зелёный.
