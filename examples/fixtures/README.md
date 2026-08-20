# Fixtures

Все fixtures компактны, синтетичны и не содержат персональных данных.

- `ted_search_response.json` — минимальный пример ответа TED Search для разработки mapping. Реальный adapter обязан сверить имена полей с текущим Swagger/live smoke и обновить fixture в отдельном commit, если контракт отличается.
- `contracts_finder_ocds.json` — пример OCDS release.
- `normalized_tender.json` — ожидаемая внутренняя модель.
- `tender_changed_event.json` — событие NATS.
- `sample_tender.pdf` — PDF с текстовым слоем для extraction/RAG тестов.
- `sample_notice.xml`, `sample_notice.html`, `sample_notice.txt` — примеры поддерживаемых вложений.
- `unsupported.bin` — файл, который сохраняется, но не индексируется.

Обычные тесты не должны обращаться к live API. Fixtures обновляются только после ручной проверки официального endpoint и с указанием даты в commit/документации.
