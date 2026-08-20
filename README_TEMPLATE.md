# TenderLens

> Асинхронный мониторинг закупок с NATS JetStream, PostgreSQL/pgvector и локальным RAG через Ollama.

## Выбранное тестовое задание

Основное задание — №7: асинхронный сбор закупок, задержки, скачивание вложений и PostgreSQL. RAG, rate limiter, Docker Compose и CI являются расширениями одной реализации.

## Быстрый запуск

Codex обязан заменить этот раздел проверенными командами фактического проекта.

```bash
cp .env.example .env
docker compose up --build
```

## Архитектура

Вставить `docs/diagrams/architecture.png` и кратко объяснить три роли.

## Возможности

- TED и Contracts Finder adapters;
- asynchronous crawl and attachments;
- NATS JetStream indexing queue;
- local embeddings and RAG;
- pgvector exact cosine search;
- API key + PostgreSQL rate limiter;
- static UI;
- unit/integration/e2e and GitHub Actions.

## Demo

Показать fixture demo, live smoke отдельно и 429 scenario.

## Ограничения

Честно перечислить: text PDF only, semantic-only search, exact scan, fixed-window boundary burst, shared DB/volume.

## Документация

Ссылки на architecture, algorithm, testing, operations, code-map, traceability, decisions.

## License

MIT.
