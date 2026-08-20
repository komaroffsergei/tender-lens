# Security policy

TenderLens является демонстрационным проектом.

Не публикуйте API-ключи, `.env`, live attachments или дампы БД. Для сообщения об уязвимости используйте приватный канал владельца репозитория, а не public issue с готовым exploit.

Защитные меры MVP:

- хранение только SHA-256 API-key;
- allowlist redirect hosts;
- ограничение размера файлов и безопасные имена;
- `defusedxml`;
- non-root container;
- prompt-injection boundary;
- generic external errors и request IDs;
- отсутствие raw payload/local path в API;
- fake-only CI без live network/model pull.
