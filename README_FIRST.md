# TenderLens SDD Pack

Этот комплект предназначен для запуска полностью самостоятельной реализации проекта через Codex Agent. Он не является готовым приложением: это спецификация, правила агента, тестовый план, схемы, примеры контрактов и эталон интерфейса.

## Что внутри

- `START_CODEX.md` — короткий текст для интерактивного запуска.
- `CODEX_MASTER_PROMPT.md` — основной промпт для Codex, управляющий всей разработкой от пустого репозитория до merge в `main`.
- `AGENTS.md` — короткие постоянные правила проекта. Codex читает этот файл перед работой.
- `specs/` — неизбыточная, но полная SDD-спецификация.
- `schemas/` — JSON Schema событий, нормализованной закупки и финального отчёта агента.
- `docs/diagrams/` — Mermaid/Graphviz-схемы и проверенные PNG-версии.
- `docs/ui/` — desktop и mobile эталоны интерфейса.
- `docs/INTERVIEW_CHEATSHEET.md` — объяснение архитектуры и ответы перед собеседованием.
- `docs/SOURCE_NOTES.md` — официальные внешние контракты, которые агент обязан перепроверить перед live-реализацией.
- `prototype/` — статический HTML/CSS/JS-прототип интерфейса с фиктивными данными.
- `examples/fixtures/` — примеры входных данных и небольшой PDF для тестов.
- `.github/workflows/ci-template.yml` — ориентир для итогового CI, а не файл, который следует бездумно копировать без проверки.
- `.github/codex/prompts/review.md` — независимое ревью после каждого этапа.
- `README_TEMPLATE.md`, `LICENSE`, `.gitignore` — исходные материалы первого commit.

## Подготовка

Нужны:

- Git;
- GitHub CLI `gh` с действующей авторизацией и правом создавать/изменять репозиторий;
- Docker и Docker Compose;
- Codex CLI;
- доступ в интернет для GitHub, TED, Contracts Finder, Docker Hub и загрузки моделей Ollama.

Проверьте:

```bash
git --version
gh auth status
docker version
docker compose version
codex --version
```

## Рекомендуемый запуск

1. Распаковать комплект в пустой каталог проекта.
2. Открыть каталог в терминале.
3. Запустить Codex в режиме записи в рабочую область:

```bash
codex --search exec \
  --sandbox workspace-write \
  -c sandbox_workspace_write.network_access=true \
  --json \
  --output-schema schemas/codex-final-report.schema.json \
  --output-last-message codex-final-report.json \
  - < CODEX_MASTER_PROMPT.md \
  | tee codex-run.jsonl
```

Либо запустите подготовленный скрипт:

```bash
./run-codex.sh
```

Сетевой доступ внутри `workspace-write` нужен для `gh`, GitHub Actions, Docker registry и live-smoke внешних источников. Запускайте pack только в отдельном пустом каталоге и не используйте режим обхода sandbox. Доступ к Docker socket зависит от политики локальной установки Codex; если он запрещён, агент обязан оформить точный blocker вместо выдуманного результата.

`codex-run.jsonl` сохранит события выполнения, а `codex-final-report.json` — итоговый структурированный отчёт.

## Важное ограничение

Ни один промпт не гарантирует безошибочную разработку. Этот комплект вместо обещаний из мира презентаций вводит жёсткие контрольные точки: агент не должен переходить к следующему этапу, пока локальные проверки и GitHub Actions не завершились успешно.

Если отсутствуют права на GitHub, Docker не запускается или внешний API недоступен, агент обязан зафиксировать реальную причину в `BLOCKERS.md`. Он не имеет права изображать успешный push, CI или live-тест.

## Быстрая визуальная проверка

Перед запуском откройте:

- `docs/diagrams/architecture.png`;
- `docs/diagrams/data-model.png`;
- `docs/ui/search-wireframe.png`;
- `examples/fixtures/sample_tender.pdf`.

Команда проверки структуры и JSON Schema находится в `docs/PACK_VALIDATION.md`.
