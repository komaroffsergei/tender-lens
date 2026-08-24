-- Эталон exact cosine запроса; production-версия параметризована через SQLAlchemy.
SELECT
    c.id AS chunk_id,
    c.tender_id,
    c.attachment_id,
    c.content,
    1 - (c.embedding <=> CAST(:query_embedding AS vector)) AS score,
    t.title,
    s.code AS source,
    t.source_url,
    a.filename
FROM chunks AS c
JOIN tenders AS t ON t.id = c.tender_id
JOIN sources AS s ON s.id = t.source_id
LEFT JOIN attachments AS a ON a.id = c.attachment_id
WHERE t.index_status = 'ready'
ORDER BY c.embedding <=> CAST(:query_embedding AS vector)
LIMIT :limit;
