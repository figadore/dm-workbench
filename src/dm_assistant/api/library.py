"""Authenticated JSON adapter for immutable Library document views and search."""

import uuid

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from dm_assistant.api.dungeons import _require_api_csrf
from dm_assistant.modules.library.catalog import LibraryDocumentCatalog
from dm_assistant.modules.library.contracts import (
    AuthorityClass,
    CorpusKind,
    DocumentType,
    IngestSource,
    LexicalSearchQuery,
    RevisionClassification,
    Ruleset,
    SourceLocator,
    SourceScope,
    SourceVisibility,
    VisibilityLabel,
)
from dm_assistant.modules.library.retrieval import LibraryLexicalSearchService
from dm_assistant.modules.library.workflows import LibrarySourceWorkflow


class IngestLibrarySourceApiRequest(BaseModel):
    """JSON transport for one allowlisted immutable source ingestion."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    campaign_id: uuid.UUID | None = None
    corpus: CorpusKind = CorpusKind.CAMPAIGN
    root_label: str = Field(min_length=1, max_length=80)
    relative_path: str = Field(min_length=1, max_length=2000)
    title: str = Field(min_length=1, max_length=500)
    document_type: DocumentType
    authority_class: AuthorityClass
    ruleset: Ruleset | None = None
    visibility_policy: SourceVisibility = SourceVisibility.DM_ONLY


def create_library_api_router(
    catalog: LibraryDocumentCatalog,
    search: LibraryLexicalSearchService,
    sources: LibrarySourceWorkflow,
) -> APIRouter:
    router = APIRouter(prefix="/api/library", tags=["library"])

    @router.post("/ingest")
    def ingest_source(
        command: IngestLibrarySourceApiRequest,
        request: Request,
    ) -> dict[str, object]:
        _require_api_csrf(request)
        result = sources.ingest(
            IngestSource(
                scope=SourceScope(
                    campaign_id=command.campaign_id,
                    corpus=command.corpus,
                ),
                locator=SourceLocator(
                    root_label=command.root_label,
                    relative_path=command.relative_path,
                ),
                classification=RevisionClassification(
                    corpus=command.corpus,
                    document_type=command.document_type,
                    authority_class=command.authority_class,
                    ruleset=command.ruleset,
                    visibility=VisibilityLabel(policy=command.visibility_policy),
                ),
                title=command.title,
            )
        )
        return result.model_dump(mode="json")

    @router.get("/documents")
    def list_documents(
        campaign_id: uuid.UUID | None = None,
        corpus: CorpusKind = CorpusKind.CAMPAIGN,
    ) -> tuple[dict[str, object], ...]:
        scope = SourceScope(campaign_id=campaign_id, corpus=corpus)
        return tuple(
            {"id": str(item.id), "source_path": item.source_path, "retired": item.retired}
            for item in catalog.list_documents(scope)
        )

    @router.get("/documents/{document_id}")
    def show_document(
        document_id: uuid.UUID,
        campaign_id: uuid.UUID | None = None,
        revision_id: uuid.UUID | None = None,
        corpus: CorpusKind = CorpusKind.CAMPAIGN,
    ) -> dict[str, object]:
        detail = catalog.show_document(
            SourceScope(campaign_id=campaign_id, corpus=corpus),
            document_id,
            revision_id,
        )
        return {
            "id": str(detail.id),
            "source_path": detail.source_path,
            "revision_id": str(detail.revision_id),
            "revision_number": detail.revision_number,
            "content_hash": detail.content_hash,
            "content": detail.content_snapshot,
            "title": detail.title,
            "document_type": detail.document_type,
            "authority_class": detail.authority_class,
            "ruleset": detail.ruleset,
            "visibility_policy": detail.visibility_policy,
        }

    @router.get("/search")
    def lexical_search(
        query: str,
        campaign_id: uuid.UUID | None = None,
        corpus: CorpusKind = CorpusKind.CAMPAIGN,
        include_preparation: bool = False,
    ) -> dict[str, object]:
        scope = SourceScope(campaign_id=campaign_id, corpus=corpus)
        results = search.search(
            LexicalSearchQuery(
                scope=scope,
                query=query,
                include_preparation=include_preparation,
                visible_policies=(SourceVisibility.DM_ONLY,),
            )
        )
        return {
            "scope": {
                "campaign_id": str(campaign_id) if campaign_id is not None else None,
                "corpus": corpus.value,
            },
            "results": [item.model_dump(mode="json") for item in results],
        }

    return router
