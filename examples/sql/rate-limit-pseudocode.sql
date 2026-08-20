-- Выполняется одной транзакцией. Текущее время приходит из инъецируемого clock.
SELECT *
FROM api_keys
WHERE key_hash = :key_hash
FOR UPDATE;

-- Приложение вычисляет start_of_current_utc_minute.
-- Если window_started_at отличается, request_count сбрасывается в 0.
-- Если request_count >= limit_per_minute, транзакция завершается без increment и API отдаёт 429.

UPDATE api_keys
SET
    window_started_at = :current_window,
    request_count = :next_count,
    last_used_at = :now
WHERE id = :api_key_id;
