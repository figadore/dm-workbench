"""Typed source classification, discovery, and reconciliation contracts."""

import hashlib
import re
import uuid
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

_ROOT_LABEL_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RootLabel = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=80,
        pattern=r"^[a-z0-9][a-z0-9._-]{0,79}$",
    ),
]
RelativeSourcePath = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
Sha256 = Annotated[
    str,
    StringConstraints(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
]


class LibraryContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CorpusKind(StrEnum):
    CAMPAIGN = "campaign"
    RULES = "rules"


class DocumentType(StrEnum):
    CANON_NOTE = "canon_note"
    RAW_SESSION_RECORD = "raw_session_record"
    PLAN_OR_ADVENTURE = "plan_or_adventure"
    REFERENCE_LORE = "reference_lore"
    PLAYER_HANDOUT = "player_handout"
    CHARACTER_SHEET = "character_sheet"
    IMPORTANT_ITEM_RECORD = "important_item_record"
    CREATURE_OR_BESTIARY_RECORD = "creature_or_bestiary_record"
    DUNGEON_OR_ENCOUNTER_BRIEF = "dungeon_or_encounter_brief"
    HOUSE_RULE_OR_RULING = "house_rule_or_ruling"
    RULES_REFERENCE = "rules_reference"


class AuthorityClass(StrEnum):
    CANONICAL_CLAIM = "canonical_claim"
    RAW_RECORD = "raw_record"
    PREPARATION = "preparation"
    REFERENCE = "reference"
    OFFICIAL_RULES = "official_rules"
    USER_AUTHORED_RULES = "user_authored_rules"


class Ruleset(StrEnum):
    DND_5E_2014 = "dnd_5e_2014"
    DND_5E_2024 = "dnd_5e_2024"
    SYSTEM_AGNOSTIC = "system_agnostic"
    OTHER = "other"


class SourceVisibility(StrEnum):
    DM_ONLY = "dm_only"
    ALL_CAMPAIGN_PLAYERS = "all_campaign_players"
    EXPLICIT_AUDIENCE = "explicit_audience"
    PUBLIC = "public"


class PathEventKind(StrEnum):
    DISCOVERED = "discovered"
    MOVED = "moved"
    CONTENT_CHANGED = "content_changed"
    RESTORED = "restored"
    RETIRED = "retired"


class IngestionStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"


class SnapshotState(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class IngestionOutcome(StrEnum):
    CREATED = "created"
    DUPLICATE_CREATED = "duplicate_created"
    UNCHANGED = "unchanged"
    UPDATED = "updated"
    MOVED = "moved"
    RESTORED = "restored"
    REVIEW_REQUIRED = "review_required"


class ReconciliationAmbiguityReason(StrEnum):
    POSSIBLE_MOVED_AND_EDITED = "possible_moved_and_edited"
    MULTIPLE_EXACT_MOVE_CANDIDATES = "multiple_exact_move_candidates"
    MULTIPLE_RETIRED_PATH_CANDIDATES = "multiple_retired_path_candidates"


class SourcePresence(StrEnum):
    PRESENT = "present"
    MISSING = "missing"


class VisibilityLabel(LibraryContract):
    policy: SourceVisibility
    audience_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_explicit_audience_only_when_selected(self) -> Self:
        if self.policy is SourceVisibility.EXPLICIT_AUDIENCE:
            if not self.audience_ids:
                raise ValueError("explicit audience visibility requires audience IDs")
        elif self.audience_ids:
            raise ValueError("audience IDs require explicit audience visibility")
        if len(self.audience_ids) != len(set(self.audience_ids)):
            raise ValueError("audience IDs must be unique")
        return self


class RevisionClassification(LibraryContract):
    corpus: CorpusKind
    document_type: DocumentType
    authority_class: AuthorityClass
    ruleset: Ruleset | None
    visibility: VisibilityLabel

    @model_validator(mode="after")
    def require_safe_classification_combinations(self) -> Self:
        if self.corpus is CorpusKind.RULES and self.ruleset is None:
            raise ValueError("rules corpus revisions require a ruleset")
        if (
            self.authority_class
            in {
                AuthorityClass.CANONICAL_CLAIM,
                AuthorityClass.RAW_RECORD,
                AuthorityClass.PREPARATION,
            }
            and self.corpus is not CorpusKind.CAMPAIGN
        ):
            raise ValueError("campaign authority requires campaign corpus")
        if self.authority_class is AuthorityClass.OFFICIAL_RULES:
            if self.corpus is not CorpusKind.RULES:
                raise ValueError("official rules authority requires rules corpus")
            if self.visibility.policy is not SourceVisibility.DM_ONLY:
                raise ValueError("official rules default to dm_only visibility")
        if (
            self.authority_class is AuthorityClass.USER_AUTHORED_RULES
            and self.ruleset is None
        ):
            raise ValueError("user-authored rules authority requires a ruleset")
        if self.document_type in {
            DocumentType.PLAN_OR_ADVENTURE,
            DocumentType.DUNGEON_OR_ENCOUNTER_BRIEF,
        }:
            if self.corpus is not CorpusKind.CAMPAIGN:
                raise ValueError("preparation documents require campaign corpus")
            if self.authority_class is not AuthorityClass.PREPARATION:
                raise ValueError("preparation documents require preparation authority")
            if self.visibility.policy is not SourceVisibility.DM_ONLY:
                raise ValueError("preparation documents require dm_only visibility")
        if (
            self.document_type is DocumentType.CANON_NOTE
            and self.authority_class is not AuthorityClass.CANONICAL_CLAIM
        ):
            raise ValueError("canon notes require canonical_claim authority")
        if (
            self.document_type is DocumentType.RAW_SESSION_RECORD
            and self.authority_class is not AuthorityClass.RAW_RECORD
        ):
            raise ValueError("raw session records require raw_record authority")
        if (
            self.document_type is DocumentType.RULES_REFERENCE
            and self.corpus is not CorpusKind.RULES
        ):
            raise ValueError("rules references require rules corpus")
        if (
            self.document_type
            in {
                DocumentType.CREATURE_OR_BESTIARY_RECORD,
                DocumentType.HOUSE_RULE_OR_RULING,
            }
            and self.ruleset is None
        ):
            raise ValueError("creature and house-rule records require a ruleset")
        if (
            self.document_type is DocumentType.HOUSE_RULE_OR_RULING
            and self.authority_class is not AuthorityClass.USER_AUTHORED_RULES
        ):
            raise ValueError("house rules require user_authored_rules authority")
        return self


class SourceScope(LibraryContract):
    campaign_id: uuid.UUID | None
    corpus: CorpusKind

    @model_validator(mode="after")
    def require_campaign_owner(self) -> Self:
        if self.corpus is CorpusKind.CAMPAIGN and self.campaign_id is None:
            raise ValueError("campaign corpus requires a campaign ID")
        return self


class LexicalSearchQuery(LibraryContract):
    """Authorized lexical search scope and bounded result settings."""

    scope: SourceScope
    query: str = Field(min_length=1, max_length=500)
    snapshot_id: uuid.UUID | None = None
    authority_classes: tuple[AuthorityClass, ...] = ()
    visible_policies: tuple[SourceVisibility, ...] = (
        SourceVisibility.DM_ONLY,
        SourceVisibility.EXPLICIT_AUDIENCE,
        SourceVisibility.ALL_CAMPAIGN_PLAYERS,
        SourceVisibility.PUBLIC,
    )
    rulesets: tuple[Ruleset, ...] = ()
    include_preparation: bool = False
    limit: int = Field(default=10, ge=1, le=100)
    snippet_chars: int = Field(default=320, ge=80, le=2000)

    @field_validator("query")
    @classmethod
    def require_search_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("search query must contain non-whitespace text")
        return value


class LexicalSearchResult(LibraryContract):
    """Bounded lexical evidence with an immutable chunk citation."""

    citation_id: str
    document_id: uuid.UUID
    document_revision_id: uuid.UUID
    chunk_id: uuid.UUID
    heading_path: tuple[str, ...]
    start_offset: int
    end_offset: int
    snippet: str
    score: float


class VectorRetrievalMode(StrEnum):
    """Whether evidence was ranked by vectors or the lexical fallback."""

    VECTOR = "vector"
    LEXICAL_FALLBACK = "lexical_fallback"


class VectorSearchQuery(LibraryContract):
    """A vector request pinned to both retrieval snapshot and completed run."""

    lexical: LexicalSearchQuery
    embedding_run_id: uuid.UUID

    @model_validator(mode="after")
    def require_explicit_snapshot(self) -> Self:
        if self.lexical.snapshot_id is None:
            raise ValueError("vector search requires an explicit corpus snapshot")
        return self


class VectorSearchResult(LibraryContract):
    """One vector-ranked immutable chunk citation."""

    citation_id: str
    document_id: uuid.UUID
    document_revision_id: uuid.UUID
    chunk_id: uuid.UUID
    heading_path: tuple[str, ...]
    start_offset: int
    end_offset: int
    snippet: str
    score: float


class VectorSearchResponse(LibraryContract):
    """Bounded evidence and an inspectable ranking mode without vector payloads."""

    mode: VectorRetrievalMode
    results: tuple[VectorSearchResult, ...]


class HybridRetrievalMode(StrEnum):
    """Whether hybrid ranking had an eligible vector candidate set."""

    HYBRID = "hybrid"
    LEXICAL_FALLBACK = "lexical_fallback"


class HybridSearchQuery(LibraryContract):
    """Versioned deterministic fusion settings over a pinned search scope."""

    lexical: LexicalSearchQuery
    embedding_run_id: uuid.UUID
    rrf_version: Literal["rrf-v1"] = "rrf-v1"
    rrf_rank_constant: int = Field(default=60, ge=1, le=1000)
    exact_name_boost: float = Field(default=0.1, ge=0, le=1)
    neighboring_chunks_each_side: int = Field(default=1, ge=0, le=2)

    @model_validator(mode="after")
    def require_explicit_snapshot(self) -> Self:
        if self.lexical.snapshot_id is None:
            raise ValueError("hybrid search requires an explicit corpus snapshot")
        return self


class NeighboringChunk(LibraryContract):
    """An authorized adjacent span that gives a selected citation local context."""

    citation_id: str
    chunk_id: uuid.UUID
    heading_path: tuple[str, ...]
    start_offset: int
    end_offset: int
    snippet: str


class HybridSearchResult(LibraryContract):
    """One fused immutable citation with optional bounded adjacent evidence."""

    citation_id: str
    document_id: uuid.UUID
    document_revision_id: uuid.UUID
    chunk_id: uuid.UUID
    heading_path: tuple[str, ...]
    start_offset: int
    end_offset: int
    snippet: str
    score: float
    lexical_rank: int | None = Field(default=None, ge=1)
    vector_rank: int | None = Field(default=None, ge=1)
    neighboring_chunks: tuple[NeighboringChunk, ...] = ()


class HybridSearchResponse(LibraryContract):
    """Fused bounded evidence without raw vector data or hidden candidates."""

    mode: HybridRetrievalMode
    rrf_version: Literal["rrf-v1"]
    results: tuple[HybridSearchResult, ...]


class RetrievalRunMode(StrEnum):
    """Resolved ranking path recorded for reproducible retrieval audit."""

    HYBRID = "hybrid"
    LEXICAL_FALLBACK = "lexical_fallback"


class RetrievalCandidateRecord(LibraryContract):
    """Source-body-free candidate rank data retained by a retrieval audit run."""

    citation_id: str = Field(pattern=r"^chunk:[0-9a-f-]{36}$")
    score: float
    lexical_rank: int | None = Field(default=None, ge=1)
    vector_rank: int | None = Field(default=None, ge=1)


class RetrievalRunSnapshot(LibraryContract):
    """Immutable retrieval audit record with scope/version and citation pins only."""

    id: uuid.UUID
    corpus_snapshot_id: uuid.UUID
    embedding_run_id: uuid.UUID | None
    mode: RetrievalRunMode
    query_sha256: Sha256
    retrieval_versions: dict[str, str]
    resolved_scope: dict[str, JsonValue]
    candidates: tuple[RetrievalCandidateRecord, ...]
    selected_citation_ids: tuple[str, ...]
    duration_milliseconds: float = Field(ge=0)


class SourceLocator(LibraryContract):
    root_label: RootLabel
    relative_path: RelativeSourcePath

    @field_validator("root_label")
    @classmethod
    def validate_root_label(cls, value: str) -> str:
        if _ROOT_LABEL_PATTERN.fullmatch(value) is None:
            raise ValueError("source root label must be a safe lowercase identifier")
        return value

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        if (
            value.startswith("/")
            or "\\" in value
            or "\x00" in value
            or re.match(r"^[A-Za-z]:/", value) is not None
        ):
            raise ValueError("source path must be a safe relative POSIX path")
        parts = value.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("source path must be normalized without traversal")
        return value

    @property
    def registry_path(self) -> str:
        return f"{self.root_label}/{self.relative_path}"

    @classmethod
    def from_registry_path(cls, value: str) -> "SourceLocator":
        root_label, separator, relative_path = value.partition("/")
        if not separator:
            raise ValueError("registry path does not contain a root label")
        return cls(root_label=root_label, relative_path=relative_path)


class DiscoveredSource(LibraryContract):
    locator: SourceLocator
    source_path: str
    content_sha256: Sha256
    byte_size: int = Field(ge=0)
    content: str

    @model_validator(mode="after")
    def verify_exact_content_identity(self) -> Self:
        encoded = self.content.encode("utf-8")
        if self.source_path != self.locator.registry_path:
            raise ValueError("source path does not match locator")
        if _SHA256_PATTERN.fullmatch(self.content_sha256) is None:
            raise ValueError("content SHA-256 is invalid")
        if self.byte_size != len(encoded):
            raise ValueError("source byte size does not match UTF-8 content")
        if hashlib.sha256(encoded).hexdigest() != self.content_sha256:
            raise ValueError("source hash does not match UTF-8 content")
        return self


class IngestSource(LibraryContract):
    scope: SourceScope
    locator: SourceLocator
    classification: RevisionClassification
    title: str = Field(min_length=1, max_length=500)
    source_metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def reject_blank_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source title cannot be blank")
        return value

    @model_validator(mode="after")
    def require_matching_corpus(self) -> Self:
        if self.scope.corpus is not self.classification.corpus:
            raise ValueError("source scope and classification corpus must match")
        return self


class ReconcileMissingSources(LibraryContract):
    scope: SourceScope
    root_label: RootLabel
    confirm_retirement: Literal[True]

    @field_validator("root_label")
    @classmethod
    def validate_root_label(cls, value: str) -> str:
        if _ROOT_LABEL_PATTERN.fullmatch(value) is None:
            raise ValueError("source root label must be a safe lowercase identifier")
        return value


class ReconciliationAmbiguity(LibraryContract):
    reason: ReconciliationAmbiguityReason
    candidate_document_ids: tuple[uuid.UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_stable_unique_candidates(self) -> Self:
        values = tuple(str(item) for item in self.candidate_document_ids)
        if len(values) != len(set(values)) or values != tuple(sorted(values)):
            raise ValueError("ambiguity candidates must be unique and sorted")
        return self


class IngestionResult(LibraryContract):
    run_id: uuid.UUID
    status: IngestionStatus
    outcome: IngestionOutcome
    source_path: str
    content_sha256: Sha256
    document_id: uuid.UUID | None = None
    revision_id: uuid.UUID | None = None
    revision_number: int | None = Field(default=None, ge=1)
    duplicate_document_ids: tuple[uuid.UUID, ...] = ()
    ambiguity: ReconciliationAmbiguity | None = None

    @model_validator(mode="after")
    def require_outcome_shape(self) -> Self:
        if self.outcome is IngestionOutcome.REVIEW_REQUIRED:
            if self.status is not IngestionStatus.REVIEW_REQUIRED:
                raise ValueError("review outcome requires review_required status")
            if self.ambiguity is None:
                raise ValueError("review outcome requires ambiguity details")
            if any(
                item is not None
                for item in (self.document_id, self.revision_id, self.revision_number)
            ):
                raise ValueError("review outcome cannot select a document revision")
        else:
            if self.status is not IngestionStatus.SUCCEEDED:
                raise ValueError("completed ingestion requires succeeded status")
            if self.ambiguity is not None:
                raise ValueError("completed ingestion cannot include ambiguity")
            if any(
                item is None
                for item in (self.document_id, self.revision_id, self.revision_number)
            ):
                raise ValueError("completed ingestion requires a document revision")
        duplicates = tuple(str(item) for item in self.duplicate_document_ids)
        if len(duplicates) != len(set(duplicates)) or duplicates != tuple(
            sorted(duplicates)
        ):
            raise ValueError("duplicate document IDs must be unique and sorted")
        return self


class MissingReconciliationResult(LibraryContract):
    run_id: uuid.UUID
    status: Literal[IngestionStatus.SUCCEEDED]
    root_label: RootLabel
    retired_document_ids: tuple[uuid.UUID, ...]

    @model_validator(mode="after")
    def require_stable_unique_documents(self) -> Self:
        values = tuple(str(item) for item in self.retired_document_ids)
        if len(values) != len(set(values)) or values != tuple(sorted(values)):
            raise ValueError("retired document IDs must be unique and sorted")
        return self
