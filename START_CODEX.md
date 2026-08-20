# Стартовый промпт

Скопируйте текст ниже в Codex, если запускаете агента интерактивно из корня распакованного SDD pack.

```text
Ты находишься в корне SDD-комплекта TenderLens. Выполни проект полностью самостоятельно.

Сначала без исключений прочитай `AGENTS.md`, затем `README_FIRST.md`, `CODEX_MASTER_PROMPT.md`, все `specs/*.md`, все `schemas/*.json`, схемы в `docs/diagrams/`, эталон UI в `docs/ui/`, fixtures и prototype. Проверь Git, GitHub CLI, Docker и текущий remote.

Далее исполняй `CODEX_MASTER_PROMPT.md` буквально, а `specs/10-implementation-plan.md` используй как единственный порядок этапов. Не переходи к следующему stage, пока локальные проверки и GitHub Actions текущего stage не стали зелёными. После implementation и test/docs части каждого stage делай отдельный commit, push и проверяй CI через `gh`. Любое изменение поведения одновременно синхронизируй с code-map, traceability и документацией.

Не добавляй Redis, frontend framework, отдельный catalog-service, MinIO, LangChain, FTS/hybrid search или другие компоненты вне scope. Не утверждай, что push, CI, live smoke, PR или merge выполнены без проверяемого результата. При внешнем блокере выполни всё независимое, создай `BLOCKERS.md` и продолжи до максимально возможной готовности.

Начинай со Stage 00. Не ограничивайся планом: создавай код, запускай команды, тестируй, исправляй, коммить, пушь, проверяй GitHub Actions и доводи проект до Definition of Done.
```


## Неинтерактивный запуск

```bash
./run-codex.sh
```

Скрипт включает live web search и outbound network для команд внутри `workspace-write`, но не отключает sandbox.
