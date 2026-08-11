"""Filtered PostgreSQL lexical retrieval over active corpus snapshots."""

from __future__ import annotations

import re

from sqlalchemy import Engine, Text, and_, case, cast, func, select

from dm_assistant.db import build_session_factory
from dm_assistant.modules.library.contracts import (
    AuthorityClass,
    LexicalSearchQuery,
    LexicalSearchResult,
    SnapshotState,
)
from dm_assistant.modules.library.models import (
    CorpusSnapshot,
    CorpusSnapshotDocument,
    DocumentChunk,
    DocumentRevision,
)


class LibraryLexicalSearchService:
    """Search only evidence authorized by scope and active snapshot state."""

    def __init__(self, engine: Engine) -> None:
        self._session_factory = build_session_factory(engine)

    def search(self, request: LexicalSearchQuery) -> tuple[LexicalSearchResult, ...]:
        """Return bounded lexical evidence from one active snapshot."""
        with self._session_factory() as session:
            tsquery = func.websearch_to_tsquery("simple", request.query)
            conditions = [
                CorpusSnapshot.state == SnapshotState.ACTIVE.value,
                CorpusSnapshot.campaign_id == request.scope.campaign_id,
                CorpusSnapshot.corpus == request.scope.corpus.value,
                CorpusSnapshotDocument.campaign_id == request.scope.campaign_id,
                CorpusSnapshotDocument.corpus == request.scope.corpus.value,
                DocumentChunk.campaign_id == request.scope.campaign_id,
                DocumentChunk.corpus == request.scope.corpus.value,
                DocumentChunk.search_vector.op("@@")(tsquery),
                DocumentChunk.visibility_policy.in_(
                    policy.value for policy in request.visible_policies
                ),
            ]
            if request.snapshot_id is not None:
                conditions.append(CorpusSnapshot.id == request.snapshot_id)
            if request.authority_classes:
                conditions.append(
                    DocumentChunk.authority_class.in_(
                        authority.value for authority in request.authority_classes
                    )
                )
            if request.rulesets:
                conditions.append(
                    DocumentChunk.ruleset.in_(
                        ruleset.value for ruleset in request.rulesets
                    )
                )
            if not request.include_preparation:
                conditions.append(
                    DocumentChunk.authority_class
                    != AuthorityClass.PREPARATION.value
                )

            heading_text = cast(DocumentChunk.heading_path, Text)
            exact_query = f"%{request.query}%"
            score = (
                func.ts_rank_cd(DocumentChunk.search_vector, tsquery)
                + case((heading_text.ilike(exact_query), 0.5), else_=0.0)
                + case((DocumentChunk.content.ilike(exact_query), 0.25), else_=0.0)
            ).label("score")
            statement = (
                select(
                    DocumentChunk.id,
                    CorpusSnapshotDocument.document_id,
                    DocumentChunk.document_revision_id,
                    DocumentChunk.heading_path,
                    DocumentChunk.start_offset,
                    DocumentChunk.end_offset,
                    DocumentChunk.content,
                    score,
                )
                .join(
                    CorpusSnapshotDocument,
                    CorpusSnapshotDocument.document_revision_id
                    == DocumentChunk.document_revision_id,
                )
                .join(
                    CorpusSnapshot,
                    CorpusSnapshot.id
                    == CorpusSnapshotDocument.corpus_snapshot_id,
                )
                .join(
                    DocumentRevision,
                    DocumentRevision.id == DocumentChunk.document_revision_id,
                )
                .where(and_(*conditions))
                .order_by(score.desc(), DocumentChunk.id)
                .limit(request.limit)
            )
            rows = session.execute(statement).all()

        return tuple(
            LexicalSearchResult(
                citation_id=f"chunk:{chunk_id}",
                document_id=document_id,
                document_revision_id=revision_id,
                chunk_id=chunk_id,
                heading_path=tuple(heading_path),
                start_offset=start_offset,
                end_offset=end_offset,
                snippet=_bounded_snippet(content, request.query, request.snippet_chars),
                score=float(score),
            )
            for (
                chunk_id,
                document_id,
                revision_id,
                heading_path,
                start_offset,
                end_offset,
                content,
                score,
            ) in rows
        )


def _bounded_snippet(content: str, query: str, limit: int) -> str:
    if len(content) <= limit:
        return content
    terms = [term for term in re.findall(r"\w+", query, flags=re.UNICODE) if term]
    lowered = content.casefold()
    position = min(
        (lowered.find(term.casefold()) for term in terms if lowered.find(term.casefold()) >= 0),
        default=0,
    )
    start = max(0, position - limit // 3)
    end = min(len(content), start + limit)
    snippet = content[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet += "..."
    return snippet
