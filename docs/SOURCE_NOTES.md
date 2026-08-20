# Проверенные внешние контракты и ссылки

Агент обязан открыть эти страницы перед live-реализацией, потому что внешние API меняются. Fixtures не заменяют текущую документацию.

## Codex

- AGENTS.md: https://developers.openai.com/codex/agent-configuration/agents-md
- Non-interactive mode: https://developers.openai.com/codex/non-interactive-mode

Используемые возможности:

- инструкции проекта через `AGENTS.md`;
- `codex exec` для non-interactive запуска;
- `--sandbox workspace-write`;
- JSONL events;
- `--output-schema` и `--output-last-message` для структурированного финального отчёта.

## TED Search API

- Документация: https://docs.ted.europa.eu/api/latest/search.html
- Endpoint: `POST https://api.ted.europa.eu/v3/notices/search`
- Search API предназначен для поиска опубликованных notices и не требует authentication.
- Проверено 2026-08-20: default query `notice-type = cn-standard SORT BY publication-date DESC`; используются текущие fields `publication-date`, `description-proc`, `estimated-value-proc` и совместимые fallback aliases для fixtures.

Перед coding:

1. открыть текущий Swagger;
2. выполнить минимальный запрос;
3. выбрать только нужные fields;
4. подтвердить pagination/iteration token;
5. обновить fixture при расхождении.

## UK Contracts Finder OCDS Search

- Общая документация: https://www.contractsfinder.service.gov.uk/apidocumentation/
- Метод: https://www.contractsfinder.service.gov.uk/apidocumentation/Notices/1/GET-Published-Notice-OCDS-Search
- Endpoint: `GET https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search`
- Параметры: `publishedFrom`, `publishedTo`, `stages`, `limit`, `cursor`.
- `limit`: 1..100, default 100.
- Документация требует прекратить запросы минимум на 5 минут после rate-limit 403.

## Ollama

- Embeddings: https://docs.ollama.com/capabilities/embeddings
- Model: https://ollama.com/library/qwen3-embedding
- Generation model: https://ollama.com/library/qwen3:1.7b

MVP использует batch input через `/api/embed`, одинаковую embedding model для index/query и проверку dimensions=1024.

## pgvector

- Repository/docs: https://github.com/pgvector/pgvector

MVP использует:

- `CREATE EXTENSION vector`;
- `vector(1024)`;
- cosine distance operator `<=>`;
- similarity `1 - distance`;
- exact search по умолчанию;
- без HNSW/IVFFlat до измеренной необходимости.

## NATS JetStream

- Documentation: https://docs.nats.io/nats-concepts/jetstream

MVP использует file-backed stream, durable pull consumer, explicit ACK и at-least-once processing. Indexer обязан быть идемпотентным.
