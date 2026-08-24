# Соответствие тестовому заданию

Основное выбранное задание — №7 «Асинхронный Парсер/Скрапер сайтов».

| Требование задания | Реализация | Проверка |
|---|---|---|
| Асинхронный Python-скрипт | `asyncio`, `httpx.AsyncClient`, роли `tender_lens.crawler` | `test_http_concurrency_is_bounded`, role smoke в CI |
| Сбор новых закупок | `TedAdapter`, `ContractsFinderAdapter`, cursor в таблице `sources` | adapter fixtures, cursor integration tests |
| Параллельная обработка | `BoundedSemaphore`, отдельные лимиты запросов и вложений | восемь одновременных запросов в unit-тесте |
| Базовые задержки | polite delay, jitter, bounded retry, `Retry-After`, cooldown 403 | HTTP policy unit-тесты |
| Скачивание вложений | streaming в `.part`, лимит размера, SHA-256, atomic replace | unit-тесты файлов и fixture E2E |
| Сохранение метаданных в PostgreSQL | SQLAlchemy async, Alembic, idempotent UPSERT | PostgreSQL integration suite |
| Работа источников независимо | ошибка записи изолируется; ошибка одного source не завершает общий цикл | malformed-record tests и orchestration path |
| Безопасность URL и файлов | закрытый allowlist, проверка каждого redirect, блок local/private target, safe filename | SSRF/redirect/path traversal regression tests |
| Markdown с логикой решения | `README.md`, `docs/algorithm.md`, `docs/architecture.md` | delivery contract test |
| LICENSE | MIT `LICENSE` | delivery contract test |
| Ветка и merge в main | feature/fix-ветки, содержательные коммиты, merge commit | публичная история GitHub |

## Дополнительные возможности

| Расширение | Реализация | Проверка |
|---|---|---|
| №3: RAG | pgvector, relevance threshold, grounded `/ask` | low-relevance short circuit и E2E |
| №8: Rate limiter | API key в PostgreSQL, общий лимит 5/мин | concurrent integration и шестой запрос 429 |
| №9: Docker/CI | один image, Compose, GitHub Actions | container role smoke и зелёный workflow |

Обычный CI использует fixtures и fake AI. Live API и Ollama проверяются отдельно и не влияют на детерминированность основной сборки.
