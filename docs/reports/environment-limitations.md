# Ограничения среды локальной поставки

В среде сборки архива отсутствовали:

- Docker Engine / Docker Compose runtime;
- локальные PostgreSQL и NATS server binaries;
- GitHub remote репозитория пользователя;
- сетевой доступ Python/package manager для установки отсутствующих CLI-проверок.

Поэтому здесь **не объявлены выполненными**:

- `docker build` и `docker compose up`;
- integration/E2E с реальными PostgreSQL/pgvector и NATS;
- загрузка моделей Ollama и live crawl внешних источников;
- push, Pull Request и GitHub Actions run.

Для этих проверок добавлены:

- `.github/workflows/ci.yml` с quality, integration и container jobs;
- `docker-compose.yml` и `docker-compose.test.yml`;
- integration/E2E suites, которые включаются через `RUN_INTEGRATION=1`;
- `scripts/demo_fake.sh` и `scripts/live_smoke.sh`;
- инструкции в `README.md`, `docs/testing.md` и `docs/operations.md`.

Локально выполненные команды и их реальные результаты приведены в
`docs/reports/local-validation.txt`. Никаких нарисованных зелёных галочек, человечество
и без них достаточно уверенно усложняет себе жизнь.
