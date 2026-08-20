# Codex review prompt после каждого этапа

Проведи независимое ревью текущего stage TenderLens. Ничего не исправляй до завершения анализа.

1. Прочитай `AGENTS.md`, требование stage в `specs/10-implementation-plan.md`, связанные requirements и test IDs.
2. Изучи diff от последнего зелёного stage commit.
3. Проверь прослеживаемость `requirement → code → test → docs`.
4. Найди:
   - поведение вне scope;
   - отсутствующие negative/concurrency tests;
   - синхронный I/O внутри async path;
   - нарушения транзакционных границ;
   - неидемпотентную обработку NATS;
   - утечки API key/paths/raw payload;
   - небезопасную обработку URL/XML/files/HTML;
   - дублирующие абстракции и сущности без назначения;
   - рассинхрон code-map/traceability/README;
   - тесты, которые только подтверждают mock, но не поведение.
5. Запусти узкие проверки stage, затем `make ci`, если stage уже поддерживает её.
6. Сформируй findings по приоритету: blocker, high, medium, low.
7. Для каждого finding укажи файл/строки, нарушенное требование, минимальное исправление и regression test ID.
8. Если blocker/high отсутствуют, явно напиши `STAGE REVIEW PASSED`.
9. После анализа исправь только подтверждённые проблемы, обнови тесты и документацию, затем сделай отдельный `fix(stage-XX)` commit, push и проверь GitHub Actions.
