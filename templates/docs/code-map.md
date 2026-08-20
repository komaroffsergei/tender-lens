# Code map

> Обновляется в каждом stage. Это карта фактического кода, а не список желаний.

## Tree

```text
<актуальное сокращённое дерево>
```

## Entry points

| Role/command | Путь | Назначение | Зависимости |
|---|---|---|---|

## Modules

| Путь | Ответственность | Основные public symbols | Test files |
|---|---|---|---|

## Data ownership

| Таблица/volume/stream | Кто пишет | Кто читает |
|---|---|---|

## NATS

| Stream | Subject | Producer | Consumer | Ack |
|---|---|---|---|---|

## HTTP

| Method/path | Auth | Rate limit | Handler | Tests |
|---|---|---|---|---|

## External dependencies

| System | Client module | Timeout/retry policy | Fake/live tests |
|---|---|---|---|

## Сознательно отсутствует

Перечислить ключевые non-goals, чтобы следующий агент не «достроил» лишнее.
