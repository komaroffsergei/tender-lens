# Traceability: требования → код → тесты

| Requirement | Реализация | Основные тесты |
|---|---|---|
| FR-CRAWL-001/002 | `crawler/base.py`, `ted.py`, `contracts_finder.py` | `test_adapters.py` contract/mapping |
| FR-CRAWL-003/004 | `ResilientHttpClient` | `test_http_and_storage.py` concurrency/retry/redirect |
| FR-CRAWL-005 | `CrawlerService.run_source` | integration/e2e repeat and cursor behavior |
| FR-CRAWL-006 | `persist_record`, `tender_content_hash` | hashing unit + DB upsert integration |
| FR-FILE-001 | `storage.py`, `_download_one` | safe filename/size/stream unit, E2E |
| FR-FILE-002 | `indexer/extract.py` | extraction unit tests |
| FR-DATA-001/002/003 | migration + `models.py` | migration/table/unique integration, API sanitation |
| FR-HASH-001 | `hashing.py` | `test_schemas_and_hashing.py` |
| FR-NATS-001/002/003 | `nats.py`, `TenderChangedV1` | event unit + NATS integration |
| FR-NATS-004 | `republish_pending` | DB pipeline/E2E behavior |
| FR-INDEX-001/002 | `extract.py`, `chunk.py` | extraction/chunk unit |
| FR-INDEX-003 | `OllamaAIProvider.embed` | AI provider unit |
| FR-INDEX-004/005 | `IndexerService.process` | idempotent/stale integration |
| FR-SEARCH-001/002/003 | `SearchService.search`, `SearchRequest` | search unit/integration/API |
| FR-RAG-001/002/003/004 | `build_rag_prompt`, `SearchService.ask` | AI/RAG unit + API/E2E |
| FR-AUTH-001/002 | `api/auth.py`, `cli.py` | auth unit/API, DB integration |
| FR-RATE-001/002/003 | `api/rate_limit.py` | state unit, concurrent integration, API 429 |
| FR-API-001/002 | `api/main.py`, `routes.py` | API test suite |
| FR-UI-001/002/003/004 | `web/` | API asset tests + static project contract |
| NFR-MAINT-001 | one package/image, three roles | code-map + Docker/CI validation |
| NFR-DOC-001/002 | Russian docs/docstrings + this map | static delivery test |
| NFR-TEST-001 | fixtures/fake AI | workflow review + tests |
| NFR-CI-001 | `.github/workflows/ci.yml` | GitHub Actions jobs |
| NFR-SEC-001 | `.gitignore`, masking, hash-only key | unit/API/static tests |
| NFR-OPS-001 | Compose, `.env.example`, README | container CI + manual demo |

Полный исходный перечень test IDs сохранён в `specs/09-test-plan.md`. Несколько IDs покрываются параметризованными тестами, а не отдельным методом на каждую строку. Так тесты проверяют поведение, а не размножаются ради красивого количества, это всё-таки код, не перепись населения.
