"""Exact cosine retrieval и grounded RAG поверх PostgreSQL/pgvector."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tender_lens.ai import AIProvider, build_rag_prompt
from tender_lens.schemas import AttachmentBrief, AskResponse, SearchResponse, SearchResult


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.10g}" for value in vector) + "]"


class SearchService:
    def __init__(self, ai: AIProvider) -> None:
        self._ai = ai

    async def search(self, session: AsyncSession, query: str, limit: int) -> SearchResponse:
        vectors = await self._ai.embed([query])
        if len(vectors) != 1:
            raise RuntimeError("AI provider нарушил контракт одного query embedding")

        sql = text(
            """
            SELECT
                c.tender_id,
                t.title,
                s.code AS source,
                t.source_url,
                c.content AS snippet,
                GREATEST(
                    -1.0,
                    LEAST(1.0, 1 - (c.embedding <=> CAST(:embedding AS vector)))
                ) AS score,
                a.id AS attachment_id,
                a.filename AS attachment_filename
            FROM chunks c
            JOIN tenders t ON t.id = c.tender_id
            JOIN sources s ON s.id = t.source_id
            LEFT JOIN attachments a ON a.id = c.attachment_id
            WHERE t.index_status = 'ready'
            ORDER BY c.embedding <=> CAST(:embedding AS vector), c.id
            LIMIT :limit
            """
        )
        rows = (
            await session.execute(
                sql,
                {"embedding": vector_literal(vectors[0]), "limit": limit},
            )
        ).mappings()
        items: list[SearchResult] = []
        for row in rows:
            attachment = None
            if row["attachment_id"] is not None:
                attachment = AttachmentBrief(
                    id=row["attachment_id"], filename=row["attachment_filename"]
                )
            snippet = " ".join(str(row["snippet"]).split())[:1000]
            items.append(
                SearchResult(
                    tender_id=row["tender_id"],
                    title=row["title"],
                    source=row["source"],
                    source_url=row["source_url"],
                    snippet=snippet,
                    score=float(row["score"]),
                    attachment=attachment,
                )
            )
        return SearchResponse(query=query, items=items)

    async def ask(self, session: AsyncSession, query: str, limit: int) -> AskResponse:
        search = await self.search(session, query, limit)
        if not search.items:
            return AskResponse(
                answer="Данных недостаточно для ответа по загруженной базе закупок.",
                sources=[],
            )
        system, prompt = build_rag_prompt(query, search.items)
        answer = await self._ai.generate(system=system, prompt=prompt)
        return AskResponse(answer=answer, sources=search.items)


class InMemorySearchService:
    """Упрощённая реализация для HTTP-тестов без PostgreSQL."""

    def __init__(
        self,
        items: list[SearchResult] | None = None,
        answer: str = "Тестовый ответ",
    ) -> None:
        self.items = items or []
        self.answer_text = answer

    async def search(self, session: Any, query: str, limit: int) -> SearchResponse:
        del session
        return SearchResponse(query=query, items=self.items[:limit])

    async def ask(self, session: Any, query: str, limit: int) -> AskResponse:
        del session, query
        return AskResponse(answer=self.answer_text, sources=self.items[:limit])
