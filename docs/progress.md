# Progress и история поставки

## Реализованные этапы

| Этап | Состояние | Результат |
|---:|---|---|
| 00 | DONE | SDD pack, спецификации, схемы и reference assets |
| 01–03 | DONE | package/tooling, Compose, Alembic, pgvector schema |
| 04–06 | DONE | contracts, hashing, TED/CF adapters, crawler, attachments |
| 07–09 | DONE | JetStream, extraction, chunking, embeddings, exact search |
| 10–14 | DONE | second source, FastAPI, auth, limiter, RAG, static UI |
| 15 | DONE WITH ENV LIMITATIONS | tests/docs/archive/git bundle; cloud CI requires repository remote |

## Содержательные commits feature branch

```text
4876919 feat(stage-01-03): add runtime tooling, compose stack and PostgreSQL schema
85d113b feat(stage-05-06): implement asynchronous source adapters and attachment ingestion
bb5e927 feat(stage-07-09): add JetStream indexing, embeddings and exact vector search
ec8d5cb feat(stage-11-14): expose protected API, rate limiter, demo CLI and static UI
24c0cf9 test(stage-15): complete regression suite, CI and delivery documentation
```

Финальные regression tests и документация зафиксированы в feature branch; merge commit и tag создаются перед упаковкой.

## Проверяемые ограничения среды сборки архива

- локальный Docker daemon отсутствовал, поэтому container/integration stack не запускался здесь;
- PostgreSQL/NATS binaries также отсутствовали;
- GitHub remote пользователя не был указан, поэтому push/PR/cloud Actions нельзя честно выполнить;
- unit/API/static проверки выполнены локально;
- integration/container jobs полностью описаны в `.github/workflows/ci.yml` и запускаются после push в любой GitHub repository.

Это не функциональное ограничение проекта, а ограничение среды подготовки архива. `docs/reports/` содержит фактические команды и результаты без дорисованных зелёных галочек.
