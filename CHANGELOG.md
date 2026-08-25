# Changelog

## Unreleased

- Индексация реальной Ollama выполняется ограниченными batch-запросами с отдельным timeout,
  чтобы большие документы не падали на CPU-only окружении.
- Integration CI запускает NATS на динамическом свободном порту и всегда удаляет свой контейнер.

## 0.2.0

- исправлен запуск из `.env.example` и включён MyPy в CI;
- исправлена изоляция event loop интеграционных тестов;
- усилена redirect/SSRF-политика и allowlist вложений Contracts Finder;
- добавлены cursor, pending republish и real JetStream E2E проверки;
- добавлены отдельные title/description chunks, relevance threshold и short circuit RAG без вызова LLM;
- `Retry-After` ограничен ответами 429, `/ask` — пятью источниками;
- индексатор защищён от stale failure и получил bounded durable delivery;
- добавлены Docker role smoke и reversible migration check;
- публичная документация сфокусирована на тестовом задании №7.

## 0.1.0

- async TED and Contracts Finder adapters;
- safe attachment ingestion;
- PostgreSQL/pgvector schema;
- NATS JetStream indexing queue;
- PDF/XML/HTML/JSON/TXT extraction and chunking;
- fake/Ollama embeddings and generation;
- exact semantic search and grounded RAG;
- API-key auth and PostgreSQL rate limiter;
- static responsive UI;
- Docker Compose, CI, tests and documentation.
