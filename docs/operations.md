# Запуск и реальная LLM

Runbook рассчитан на чистую машину с Docker Engine/Compose. Все команды выполняются из корня repository. Для быстрого старта достаточно [первых 10 минут](getting-started.md); здесь находится полный ручной acceptance-сценарий.

## Режимы AI

| Режим | Embeddings | Generation | Когда использовать |
|---|---|---|---|
| `AI_MODE=fake` | hashing trick | deterministic fragment concat | CI, unit/E2E, быстрая демонстрация |
| `AI_MODE=live` | `qwen3-embedding:0.6b` | `qwen3:1.7b` | ручная semantic/RAG демонстрация |

Fake provider проверяет pipeline, но не качество естественного языка. Live provider действительно обращается к локальному Ollama.

## Чистый запуск

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

`migrate` обязан завершиться успешно, а `api`, `postgres`, `nats` — стать healthy. Crawler/indexer являются workers без HTTP healthcheck; их готовность видна по отсутствию crash loop и логам.

```powershell
docker compose logs --tail 50 migrate api crawler indexer
Invoke-RestMethod http://localhost:8000/health/live
Invoke-RestMethod http://localhost:8000/health/ready
```

## Реальная LLM Ollama

Измените только одну строку `.env`:

```dotenv
AI_MODE=live
```

Запустите optional profile:

```powershell
docker compose --profile ai up --build -d
docker compose --profile ai ps
docker compose --profile ai logs -f model-init
```

`model-init` одноразово скачивает embedding и generation models. Первый запуск требует сеть, место на диске и время. Завершение `model-init` с кодом 0 означает, что обе модели доступны Ollama volume.

### Доказательство live-режима

```powershell
docker compose exec ollama ollama list
docker compose exec api python -c "from tender_lens.config import get_settings; s=get_settings(); print(s.ai_mode, s.embedding_model, s.generation_model)"
Invoke-RestMethod http://localhost:8000/health/ready
```

Ожидаются `qwen3-embedding:0.6b`, `qwen3:1.7b`, строка `live ...`, и `dependencies.ai=true`. Дополнительное доказательство реального generation — logs Ollama во время `/ask`:

```powershell
docker compose logs -f ollama
```

## Управление API-ключами

### Создать

```powershell
docker compose run --rm api python -m tender_lens.cli create-api-key --name manual-demo --limit 5
```

Сохраните `api_key: tl_...` в password manager/локальной session. Не добавляйте его в `.env`, Git или screenshot. Имя `manual-demo` и UUID не заменяют secret.

### Посмотреть metadata

```powershell
docker compose run --rm api python -m tender_lens.cli list-api-keys
```

### Отключить

```powershell
docker compose run --rm api python -m tender_lens.cli disable-api-key manual-demo
```

## Получение закупок

### TED

```powershell
docker compose run --rm crawler python -m tender_lens.crawler --once --source ted --max-items 5
```

### Contracts Finder

```powershell
docker compose run --rm crawler python -m tender_lens.crawler --once --source contracts_finder --max-items 5
```

### Offline fixture

```powershell
docker compose run --rm api python -m tender_lens.cli seed-demo --fixture-dir examples/fixtures
```

Fixture path полностью детерминирован. Live API может вернуть записи без attachment или временно блокировать отдельный attachment host; это фиксируется в DB и log, но не ломает весь source.

## Наблюдение конвейера

```powershell
docker compose logs -f --tail 100 crawler indexer
```

Структурированный log одной закупки связывается через `tender_id`; event — через `event_id`. Успех indexer выглядит как `Индексация завершена: ready (N chunks)`.

### PostgreSQL

```powershell
docker compose exec postgres psql -U tender_lens -d tender_lens -c `
  "SELECT s.code, count(*) AS tenders, count(*) FILTER (WHERE t.index_status='ready') AS ready FROM sources s LEFT JOIN tenders t ON t.source_id=s.id GROUP BY s.code ORDER BY s.code;"
```

```powershell
docker compose exec postgres psql -U tender_lens -d tender_lens -c `
  "SELECT download_status, count(*) FROM attachments GROUP BY download_status ORDER BY download_status;"
```

```powershell
docker compose exec postgres psql -U tender_lens -d tender_lens -c `
  "SELECT count(*) AS chunks, min(vector_dims(embedding)) AS min_dims, max(vector_dims(embedding)) AS max_dims FROM chunks;"
```

### NATS

Monitoring endpoint: [http://localhost:8222/jsz?streams=true&consumers=true](http://localhost:8222/jsz?streams=true&consumers=true). Ищите stream `TENDERS` и consumer `INDEXER`. `num_ack_pending` после спокойного периода должен возвращаться к нулю.

### Вложения

```powershell
docker compose exec crawler python -c "from pathlib import Path; p=Path('/data/attachments'); print(sum(x.is_file() for x in p.rglob('*')), 'files')"
```

Файл считается готовым только если row имеет `download_status=ready`, `sha256`, `size_bytes` и существующий `local_path`.

## Search и Ask вручную

```powershell
$apiKey = "tl_ЗАМЕНИТЕ"
$headers = @{ "X-API-Key" = $apiKey }
$search = @{ query = "серверы хранение гарантия"; limit = 5 } | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/api/v1/search -Method Post `
  -Headers $headers -ContentType "application/json" -Body $search
```

```powershell
$ask = @{ query = "Какие серверы и гарантия требуются?"; limit = 5 } | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/api/v1/ask -Method Post `
  -Headers $headers -ContentType "application/json" -Body $ask
```

В live-режиме ответ должен быть естественным текстом, а `sources` — непустым списком тех же evidence fragments. Для заведомо нерелевантного вопроса допустим и желателен ответ «Недостаточно данных в базе знаний».

## Полный ручной acceptance checklist

### 1. Повторный crawl без дубликатов

1. Запишите count по source.
2. Дважды запустите одну и ту же fixture/live порцию.
3. Снова проверьте count и uniqueness.

```powershell
docker compose exec postgres psql -U tender_lens -d tender_lens -c `
  "SELECT source_id, external_id, count(*) FROM tenders GROUP BY source_id, external_id HAVING count(*) > 1;"
```

Ожидается 0 rows.

### 2. Attachment safety

- имя в volume не содержит `..`/path traversal;
- нет оставшихся `.part` после успешного завершения;
- фактический размер не выше `MAX_ATTACHMENT_BYTES`;
- SHA-256 заполнен;
- failed file имеет `error_message`, другие tenders продолжают обрабатываться.

```powershell
docker compose exec crawler python -c "from pathlib import Path; p=Path('/data/attachments'); print(list(p.rglob('*.part')))"
```

Ожидается `[]`.

### 3. Index consistency

```powershell
docker compose exec postgres psql -U tender_lens -d tender_lens -c `
  "SELECT count(*) FROM tenders WHERE index_status='ready' AND indexed_hash IS DISTINCT FROM content_hash;"
```

Ожидается `0`.

### 4. Rate limiter

Создайте новый key с limit 5 и выполните один и тот же Search шесть раз в пределах минуты:

```powershell
1..6 | ForEach-Object {
  try {
    $response = Invoke-WebRequest http://localhost:8000/api/v1/search -Method Post `
      -Headers $headers -ContentType "application/json" -Body $search
    "$_ -> $($response.StatusCode), Retry-After=$($response.Headers['Retry-After'])"
  } catch {
    "$_ -> $([int]$_.Exception.Response.StatusCode), Retry-After=$($_.Exception.Response.Headers['Retry-After'])"
  }
}
```

Ожидается: первые пять `200` без `Retry-After`, шестой `429` с ним.

### 5. Нерелевантный Ask не вызывает generation

Автоматически это доказывает unit test со spy provider. Вручную очистите Ollama log, задайте бессвязный query и убедитесь: при пустых sources API возвращает deterministic message, а `/api/generate` в log не появился.

### 6. Source isolation и cursor

```powershell
docker compose exec postgres psql -U tender_lens -d tender_lens -c `
  "SELECT code, cursor, last_sync_at FROM sources ORDER BY code;"
```

TED и Contracts Finder имеют независимые rows. Искусственный сбой одного source не должен останавливать следующий; это детерминированно покрыто integration tests.

## TED: почему detail page бывает пустой

URL вида `https://ted.europa.eu/bg/notice/-/detail/584491-2026` может показывать пустую страницу/WAF challenge в конкретном browser/network. Crawler не использует эту HTML-страницу для ingestion: он обращается к официальному Search API. Для проверки содержимого извне обычно доступны языковые endpoints notice HTML/PDF/XML, но их доступность остаётся ответственностью TED.

## Обновление контейнеров

```powershell
docker compose --profile ai pull
docker compose --profile ai up --build -d
docker compose ps
```

Перед изменением pinned versions прочитайте changelog dependency и прогоните полный test suite. Не обновляйте production image только ради `latest` tag.

## Остановка и данные

```powershell
docker compose down
```

Named volumes остаются. `docker compose down -v` необратимо удалит локальную БД, NATS state, Ollama models и attachments; используйте его только для сознательного clean-room теста.
