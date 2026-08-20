# TenderLens: шпаргалка перед собеседованием

## 1. Объяснение за 30 секунд

TenderLens асинхронно получает закупки из TED и Contracts Finder через два адаптера, нормализует их одной Pydantic-моделью и сохраняет в PostgreSQL. Новые и изменённые записи публикуют одно долговечное событие в NATS JetStream. Indexer извлекает текст, режет на chunks, создаёт embeddings локально через Ollama и сохраняет их в pgvector. FastAPI выполняет exact semantic search и grounded RAG-ответ, проверяет API key и ограничивает Search/Ask пятью запросами в минуту. UI — статическая страница без frontend framework.

## 2. Почему не строгие микросервисы

Три роли нужны из-за разного жизненного цикла: crawler зависит от внешних сайтов, indexer медленный и повторяемый, API синхронный. Но отдельные базы, catalog API и frontend application добавили бы distributed consistency и код без пользы для тестового. Поэтому процессы разделены, а package, image и PostgreSQL общие.

## 3. Почему NATS здесь оправдан

Индексатор может быть выключен или временно не иметь Ollama. JetStream сохраняет событие, а consumer дочитывает его позже. ACK выполняется после commit. Повторная доставка безопасна, потому что `indexed_hash` сравнивается с `content_hash`.

## 4. Почему не Redis

Redis потребовался бы только для limiter. В текущем масштабе PostgreSQL row lock обеспечивает атомарность. Минус — fixed-window boundary burst и худшая масштабируемость. При нескольких API replicas/высокой нагрузке следующий шаг — Redis sliding window.

## 5. Почему событие содержит только ID и hash

PostgreSQL уже является источником истины. Полный payload и PDF в брокере увеличили бы размер сообщений и создали две копии состояния. ID+hash достаточно, чтобы indexer прочитал подтверждённое состояние и отсеял stale/repeated event.

## 6. Как не теряется publish без outbox

После commit тендер имеет `index_status=pending`. Если publish упал, crawler на следующем цикле повторно публикует pending records. Это не универсальный outbox, но минимально закрывает конкретный отказ.

## 7. Как устроена идемпотентность indexer

- stale event, hash которого не совпадает с текущим `content_hash`, пропускается;
- уже индексированный hash подтверждается без повторной записи;
- старые chunks удаляются и новые вставляются одной транзакцией;
- ACK только после commit;
- повтор после commit-before-ACK безопасен.

## 8. Почему exact cosine без HNSW

Корпус демонстрации мал. Exact search даёт полный recall и не требует настройки. HNSW имеет смысл после измерения latency/объёма, а не ради наличия ещё одного индекса в README.

## 9. Главный недостаток чистого semantic search

Точные номера закупок, CPV и артикулы могут искаться хуже. Следующий подтверждаемый шаг: PostgreSQL FTS + vector search + RRF и небольшой evaluation corpus. В MVP этого нет сознательно.

## 10. Зачем две модели Ollama

Embedding model превращает query/chunks в векторы. Generation model получает только top chunks и строит читаемый ответ. LLM не нужна для парсинга JSON, hash, upsert или фильтров.

## 11. Как ограничивается hallucination

- retrieval выполняет код;
- prompt запрещает внешние факты;
- контекст отделён как данные;
- source list строит код, не модель;
- при пустом retrieval LLM вообще не вызывается;
- fixture содержит prompt-injection строку и отдельный тест.

## 12. Почему fixed UTC-minute

Он короткий, атомарный и легко проверяется конкурентным тестом. Недостаток: до 10 запросов возле границы двух минут. Это честно записано в trade-offs.

## 13. Что делает проект тестируемым

- adapters тестируются fixtures/respx;
- clock и AI provider заменяемы;
- integration использует реальные PostgreSQL/pgvector и NATS;
- e2e использует локальный fixture source и fake AI;
- live API/Ollama отделены и не ломают CI.

## 14. Пятиминутная демонстрация

1. Показать диаграмму и четыре ограничения MVP.
2. Запустить `make demo-fake`.
3. Показать два adapter fixture → одну Pydantic model.
4. Показать NATS event и `indexed_hash`.
5. Выполнить Search.
6. Выполнить Ask и открыть source.
7. Сделать шестой запрос и показать 429 headers.
8. Открыть GitHub Actions и traceability table.

## 15. Вопросы, к которым готовиться

### Что поменяется при миллионах chunks?

Добавятся измерения, HNSW, фильтры, batch ingestion, возможно partitioning и hybrid search. Решение принимается по benchmark.

### Что поменяется при нескольких хостах?

Local volume заменяется S3-compatible storage, application image остаётся тем же. Возможно физическое разделение DB ownership.

### Почему Pydantic не решает versioning событий?

Pydantic валидирует конкретную схему в процессе. Версия в payload нужна, потому что producer и consumer обновляются не обязательно одновременно.

### Что будет при изменении embedding model?

Старые и новые vectors несовместимы. Нужен controlled reindex; model name хранится на chunks. В MVP модель фиксирована.

### Почему не передать пользовательский search через NATS?

Это синхронный request, для которого NATS добавит timeout/no-responder/error mapping без выгоды. Broker оставлен только для фоновой работы.
