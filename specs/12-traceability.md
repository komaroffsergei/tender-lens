# 12. Начальная матрица прослеживаемости

Это ожидаемая карта до реализации. Codex обязан перенести её в `docs/traceability.md`, заменить ожидаемые пути фактическими и поддерживать после каждого этапа.

| Requirement | Ожидаемая реализация | Test IDs |
|---|---|---|
| FR-CRAWL-001 | `crawler/base.py`, adapters | ADAPTER-001..002, CONTRACT-* |
| FR-CRAWL-002 | `crawler/ted.py`, `crawler/contracts_finder.py` | TED-*, CF-* |
| FR-CRAWL-003 | shared HTTP/concurrency helper | CONC-001 |
| FR-CRAWL-004 | retry policy | HTTP-002..005, CF-008 |
| FR-CRAWL-005 | crawler service + sources cursor | CURSOR-001..002 |
| FR-CRAWL-006 | persistence/upsert | UPSERT-*, CRAWL-* |
| FR-FILE-001 | storage/downloader | FILE-001..009 |
| FR-FILE-002 | indexer extractors | EXTRACT-002..008 |
| FR-DATA-001 | Alembic migration | DB-001..004 |
| FR-DATA-002 | unique constraint | DB-005 |
| FR-DATA-003 | tender persistence/API sanitization | API-SEARCH-004, API-TENDER-001 |
| FR-HASH-001 | canonical hash | HASH-001..004 |
| FR-NATS-001 | crawler publisher | NATS-006..009 |
| FR-NATS-002 | NATS setup/indexer consumer | NATS-001..003, NATS-010..011 |
| FR-NATS-003 | `TenderChangedV1` | NATS-004..005 |
| FR-NATS-004 | pending republisher | NATS-008..009 |
| FR-INDEX-001 | extract module | EXTRACT-* |
| FR-INDEX-002 | chunk module | CHUNK-* |
| FR-INDEX-003 | AI embed client | OLLAMA-EMB-* |
| FR-INDEX-004 | indexer idempotency | INDEX-002, INDEX-005 |
| FR-INDEX-005 | transaction replacement | INDEX-003..004 |
| FR-SEARCH-001 | search repository/service | SEARCH-001..003 |
| FR-SEARCH-002 | API schemas/routes | API-SEARCH-001,004 |
| FR-SEARCH-003 | Pydantic validation | SEARCH-004..005 |
| FR-RAG-001 | prompt + ask service | RAG-001..003 |
| FR-RAG-002 | no-context branch | RAG-004 |
| FR-RAG-003 | source builder | RAG-005 |
| FR-RAG-004 | dependency errors | RAG-006..009 |
| FR-AUTH-001 | api auth dependency | AUTH-001..004,006 |
| FR-AUTH-002 | CLI | AUTH-005 |
| FR-RATE-001 | limiter service | RATE-001..003,008 |
| FR-RATE-002 | row lock transaction | RATE-004 |
| FR-RATE-003 | headers/error | RATE-002,005..006 |
| FR-API-001 | API routes/error handlers | API-* |
| FR-API-002 | health routes | API-HEALTH-* |
| FR-UI-001 | web static files | UI-001..003 |
| FR-UI-002 | JS session key | UI-004,010 |
| FR-UI-003 | UI state rendering | UI-006..008 |
| FR-UI-004 | safe DOM rendering | UI-009 |
| NFR-MAINT-001 | repository structure | BOOT-*, DOC-002 |
| NFR-DOC-001 | source/docs review | DOC-* |
| NFR-DOC-002 | stage gate | DOC-002..003, GIT-* |
| NFR-TEST-001 | CI workflow/fakes | CI-004..005,008 |
| NFR-CI-001 | GitHub Actions | CI-001..007 |
| NFR-SEC-001 | config/log/storage | CONF-003, AUTH-006, FILE-* |
| NFR-OPS-001 | Compose/README | DOCKER-*, DOC-001 |

## Статусы в итоговом документе

```text
PLANNED → IMPLEMENTED → VERIFIED
BLOCKED
DEFERRED (только для SHOULD/MAY)
```

Для каждого `MUST` итоговый статус только `VERIFIED` либо `BLOCKED` с доказательством. `IMPLEMENTED` без теста не считается завершением.
