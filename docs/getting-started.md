# Первые 10 минут

Эта страница даёт минимальный маршрут: поднять систему, получить ключ, загрузить данные и выполнить Search/Ask. Для объяснения каждой переменной и сервиса перейдите к [эксплуатации](operations.md).

## 0. Ментальная модель

Один repository и один Docker image запускаются в разных ролях:

```text
crawler  = получает и сохраняет
indexer  = извлекает текст и векторизует
api      = проверяет ключ, ищет и отвечает
```

PostgreSQL хранит состояние. NATS переносит сигнал «закупка изменилась». Общий volume переносит сами файлы от crawler к indexer. Ollama используется только в `AI_MODE=live`.

## 1. Запуск

=== "PowerShell"

    ```powershell
    Copy-Item .env.example .env
    docker compose up --build -d
    docker compose ps
    ```

=== "bash"

    ```bash
    cp .env.example .env
    docker compose up --build -d
    docker compose ps
    ```

По умолчанию `AI_MODE=fake`: сеть нужна источникам закупок, но модели не скачиваются. Для настоящего Ollama сразу используйте [live-режим](operations.md#llm-ollama).

## 2. Проверка готовности

```powershell
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
docker compose logs --tail 30 crawler indexer api
```

Ожидается:

- `/health/live` → `status: ok`;
- `/health/ready` → PostgreSQL и AI имеют значение `true`;
- `postgres`, `nats`, `api` имеют `healthy`, `migrate` завершён с кодом `0`.

## 3. API-ключ

```powershell
docker compose run --rm api python -m tender_lens.cli create-api-key --name demo --limit 5
```

Скопируйте значение `api_key`, начинающееся с `tl_`. Оно показывается один раз. В БД сохраняется только SHA-256 hash; реализация — [`generate_api_key()` и `hash_api_key()`](https://github.com/komaroffsergei/tender-lens/blob/main/src/tender_lens/api/auth.py#L20-L27).

!!! note "Почему интерфейс просит ключ"
    Search, Ask и карточка закупки — защищённые endpoints. Ключ идентифицирует лимит пользователя. UI держит его в `sessionStorage` только до закрытия вкладки.

## 4. Данные

Быстрый предсказуемый вариант:

```powershell
docker compose run --rm api python -m tender_lens.cli seed-demo --fixture-dir examples/fixtures
```

Live-вариант TED:

```powershell
docker compose run --rm crawler python -m tender_lens.crawler --once --source ted --max-items 5
```

Live-вариант Contracts Finder:

```powershell
docker compose run --rm crawler python -m tender_lens.crawler --once --source contracts_finder --max-items 5
```

Indexer работает постоянно и получит опубликованные события. Следите за ним:

```powershell
docker compose logs -f --tail 50 indexer
```

## 5. Первый запрос

Откройте [http://localhost:8000](http://localhost:8000), вставьте `tl_…`, введите запрос и выберите «Поиск» или «Ответ по базе».

Через PowerShell:

```powershell
$headers = @{ "X-API-Key" = "tl_ЗАМЕНИТЕ_НА_ВАШ_КЛЮЧ" }
$body = @{ query = "поставка серверов с гарантией"; limit = 5 } | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/api/v1/search `
  -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

## 6. Быстрая диагностика результата

| Симптом | Что проверить первым |
|---|---|
| `401` | заголовок `X-API-Key`, не имя ключа и не его UUID |
| `429` | прошло ли текущее UTC-минутное окно |
| Search пуст | есть ли `ready` tenders и достаточно ли similarity |
| Ask сообщает «Недостаточно данных» | это штатный результат после фильтра релевантности |
| `ready.ai=false` | запущен ли Ollama и загружены ли обе модели |
| вложение не скачано | host allowlist, размер, HTTP status в crawler logs |

Полное дерево решений находится в [диагностике](operations/troubleshooting.md).

## 7. Остановка

```powershell
docker compose down
```

Команда сохраняет named volumes. Удаление volumes (`-v`) уничтожает PostgreSQL, NATS state, модели и вложения и поэтому в обычный сценарий не входит.
