# Состояние проекта

## Готовность

TenderLens доведён до публикуемого решения задания №7.

- стандартный запуск из `.env.example` проверен;
- TED и Contracts Finder работают через единый async-контракт;
- официальные host вложений разрешены точечно;
- PostgreSQL/pgvector и NATS проверяются в GitHub Actions;
- низкорелевантный RAG-контекст отфильтровывается;
- `Retry-After` возвращается только на 429;
- Black, Flake8 и MyPy являются блокирующими CI-проверками;
- migration проверяется в направлениях upgrade и downgrade;
- Docker image запускается от пользователя `app`;
- fixture E2E проходит через реальный JetStream и защищённый API.

## Проверенная поставка

| Область | Результат |
|---|---|
| Unit/API | 114 passed |
| PostgreSQL/NATS integration | 13 passed |
| Полный fixture E2E | 4 passed |
| Полный локальный прогон | 131 passed |
| GitHub Actions | quality, integration и container jobs |
| Публичный репозиторий | `komaroffsergei/tender-lens` |

Live-smoke внешних источников не запускается в CI. Он предназначен только для ручной проверки актуальности внешних контрактов.
