"""Application service for campaign entities, aliases, mentions, and merges."""

from __future__ import annotations

import difflib
import re
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError

from dm_assistant.db import build_session_factory, transactional_session
from dm_assistant.errors import ConflictError, InvalidInputError, ResourceNotFoundError
from dm_assistant.modules.campaign_knowledge.contracts import (
    AddEntityAlias,
    AddEntityMention,
    ArchiveEntity,
    CreateEntity,
    EntityAliasRecord,
    EntityKind,
    EntityMatchKind,
    EntityMentionRecord,
    EntityMergeRecord,
    EntityRecord,
    EntityResolutionResult,
    EntityResolutionState,
    EntityStatus,
    MergeEntities,
    ResolvedEntityCandidate,
    SplitEntity,
)
from dm_assistant.modules.campaign_knowledge.models import (
    CampaignEntity,
    CampaignEntityAlias,
    CampaignEntityMention,
    CampaignEntityMergeHistory,
)

_WHITESPACE_RE = re.compile(r"\s+")
_AMBIGUITY_DELTA = 0.05


class CampaignKnowledgeService:
    """Store and resolve campaign entities without auto-merging ambiguities."""

    def __init__(self, engine: Engine) -> None:
        self._factory = build_session_factory(engine)

    def create_entity(self, command: CreateEntity) -> EntityRecord:
        canonical_name = _normalize_text(command.canonical_name)
        with transactional_session(self._factory) as session:
            self._ensure_name_available(session, command.campaign_id, canonical_name)
            entity = CampaignEntity(
                id=uuid.uuid4(),
                campaign_id=command.campaign_id,
                canonical_name=canonical_name,
                normalized_name=canonical_name.casefold(),
                kind=command.kind.value,
                status=EntityStatus.ACTIVE.value,
            )
            session.add(entity)
            try:
                session.flush()
            except IntegrityError as exc:  # pragma: no cover - defensive
                raise ConflictError("Entity name already exists.") from exc
            return _to_entity_record(entity)

    def add_alias(self, command: AddEntityAlias) -> EntityAliasRecord:
        alias = _normalize_text(command.alias)
        with transactional_session(self._factory) as session:
            entity = self._get_entity(session, command.campaign_id, command.entity_id)
            self._ensure_name_available(session, command.campaign_id, alias)
            record = CampaignEntityAlias(
                id=uuid.uuid4(),
                campaign_id=command.campaign_id,
                entity_id=entity.id,
                alias=alias,
                normalized_alias=alias.casefold(),
            )
            session.add(record)
            try:
                session.flush()
            except IntegrityError as exc:  # pragma: no cover - defensive
                raise ConflictError("Alias already exists.") from exc
            return _to_alias_record(record)

    def add_mention(self, command: AddEntityMention) -> EntityMentionRecord:
        with transactional_session(self._factory) as session:
            entity = self._get_entity(session, command.campaign_id, command.entity_id)
            record = CampaignEntityMention(
                id=uuid.uuid4(),
                campaign_id=command.campaign_id,
                entity_id=entity.id,
                source_label=_normalize_text(command.source_label),
                source_excerpt=_normalize_text(command.source_excerpt),
                source_span_start=command.source_span_start,
                source_span_end=command.source_span_end,
            )
            session.add(record)
            session.flush()
            return _to_mention_record(record)

    def merge_entities(self, command: MergeEntities) -> EntityMergeRecord:
        with transactional_session(self._factory) as session:
            target = self._get_entity(session, command.campaign_id, command.target_entity_id)
            source = self._get_entity(session, command.campaign_id, command.source_entity_id)
            history = self._redirect_entity(
                session,
                source=source,
                target=target,
                event_kind="merge",
                event_note=command.merge_reason,
            )
            return _to_merge_record(history)

    def split_entity(self, command: SplitEntity) -> EntityMergeRecord:
        with transactional_session(self._factory) as session:
            source = self._get_entity(session, command.campaign_id, command.source_entity_id)
            self._ensure_name_available(session, command.campaign_id, command.corrected_name)
            corrected = CampaignEntity(
                id=uuid.uuid4(),
                campaign_id=command.campaign_id,
                canonical_name=command.corrected_name,
                normalized_name=_normalize_text(command.corrected_name).casefold(),
                kind=source.kind,
                status=EntityStatus.ACTIVE.value,
            )
            session.add(corrected)
            session.flush()
            history = self._redirect_entity(
                session,
                source=source,
                target=corrected,
                event_kind="split",
                event_note=command.split_reason,
            )
            return _to_merge_record(history)

    def review_correction(self, command: SplitEntity) -> EntityMergeRecord:
        return self.split_entity(command)

    def archive_entity(self, command: ArchiveEntity) -> EntityRecord:
        with transactional_session(self._factory) as session:
            entity = self._get_entity(session, command.campaign_id, command.entity_id)
            self._archive_entity(session, entity, command.archive_reason)
            return _to_entity_record(entity)

    def resolve_candidates(
        self,
        campaign_id: uuid.UUID,
        query: str,
        *,
        limit: int = 5,
    ) -> EntityResolutionResult:
        normalized = _normalize_text(query)
        casefolded = normalized.casefold()
        with transactional_session(self._factory) as session:
            entities = list(
                session.scalars(
                    select(CampaignEntity)
                    .where(CampaignEntity.campaign_id == campaign_id)
                    .order_by(CampaignEntity.canonical_name, CampaignEntity.id)
                )
            )
            aliases = list(
                session.scalars(
                    select(CampaignEntityAlias)
                    .where(CampaignEntityAlias.campaign_id == campaign_id)
                    .order_by(CampaignEntityAlias.alias, CampaignEntityAlias.id)
                )
            )
            alias_by_entity: dict[uuid.UUID, list[CampaignEntityAlias]] = {}
            for alias in aliases:
                alias_by_entity.setdefault(alias.entity_id, []).append(alias)

            exact = _resolve_exact_candidates(
                session=session,
                entities=entities,
                alias_by_entity=alias_by_entity,
                normalized_query=casefolded,
            )
            if exact:
                candidates = tuple(sorted(exact, key=lambda item: item.canonical_name))
                state = (
                    EntityResolutionState.AMBIGUOUS
                    if len(candidates) > 1
                    else EntityResolutionState.EXACT
                )
                return EntityResolutionResult(
                    campaign_id=campaign_id,
                    query=query,
                    resolution_state=state,
                    candidates=candidates[:limit],
                )

            fuzzy = _resolve_fuzzy_candidates(
                entities=entities,
                alias_by_entity=alias_by_entity,
                normalized_query=casefolded,
                limit=limit,
            )
            if not fuzzy:
                return EntityResolutionResult(
                    campaign_id=campaign_id,
                    query=query,
                    resolution_state=EntityResolutionState.NONE,
                )
            state = (
                EntityResolutionState.AMBIGUOUS
                if len(fuzzy) > 1 and fuzzy[0].score - fuzzy[1].score < _AMBIGUITY_DELTA
                else EntityResolutionState.FUZZY
            )
            return EntityResolutionResult(
                campaign_id=campaign_id,
                query=query,
                resolution_state=state,
                candidates=tuple(fuzzy[:limit]),
            )

    def _ensure_name_available(self, session: Any, campaign_id: uuid.UUID, name: str) -> None:
        normalized = _normalize_text(name).casefold()
        if session.scalar(
            select(CampaignEntity.id).where(
                CampaignEntity.campaign_id == campaign_id,
                CampaignEntity.normalized_name == normalized,
            )
        ) is not None:
            raise ConflictError("An entity with that name already exists.")
        if session.scalar(
            select(CampaignEntityAlias.id).where(
                CampaignEntityAlias.campaign_id == campaign_id,
                CampaignEntityAlias.normalized_alias == normalized,
            )
        ) is not None:
            raise ConflictError("An entity with that alias already exists.")

    def _get_entity(
        self,
        session: Any,
        campaign_id: uuid.UUID,
        entity_id: uuid.UUID,
    ) -> CampaignEntity:
        entity = session.get(CampaignEntity, entity_id)
        if entity is None or entity.campaign_id != campaign_id:
            raise ResourceNotFoundError("Entity not found.")
        return entity

    def _archive_entity(
        self,
        session: Any,
        entity: CampaignEntity,
        archive_reason: str | None,
    ) -> CampaignEntityMergeHistory:
        now = datetime.now(tz=UTC)
        entity.status = EntityStatus.ARCHIVED.value
        entity.archived_at = now
        entity.archive_reason = archive_reason
        return self._create_merge_history(
            session,
            campaign_id=entity.campaign_id,
            source_entity_id=entity.id,
            target_entity_id=entity.id,
            event_kind="archive",
            event_note=archive_reason,
        )

    def _redirect_entity(
        self,
        session: Any,
        *,
        source: CampaignEntity,
        target: CampaignEntity,
        event_kind: str,
        event_note: str | None,
    ) -> CampaignEntityMergeHistory:
        now = datetime.now(tz=UTC)
        source.status = EntityStatus.ARCHIVED.value
        source.redirect_entity_id = target.id
        source.archived_at = now
        source.archive_reason = event_note
        session.add(source)
        return self._create_merge_history(
            session,
            campaign_id=source.campaign_id,
            source_entity_id=source.id,
            target_entity_id=target.id,
            event_kind=event_kind,
            event_note=event_note,
        )

    def _create_merge_history(
        self,
        session: Any,
        *,
        campaign_id: uuid.UUID,
        source_entity_id: uuid.UUID,
        target_entity_id: uuid.UUID,
        event_kind: str,
        event_note: str | None,
    ) -> CampaignEntityMergeHistory:
        record = CampaignEntityMergeHistory(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            event_kind=event_kind,
            event_note=event_note,
        )
        session.add(record)
        session.flush()
        return record


def _normalize_text(value: str) -> str:
    normalized = _WHITESPACE_RE.sub(" ", value.strip())
    if not normalized:
        raise InvalidInputError("Text must contain visible characters.")
    return normalized


def _resolve_exact_candidates(
    *,
    session: Any,
    entities: Iterable[CampaignEntity],
    alias_by_entity: dict[uuid.UUID, list[CampaignEntityAlias]],
    normalized_query: str,
) -> tuple[ResolvedEntityCandidate, ...]:
    candidates: list[ResolvedEntityCandidate] = []
    for entity in entities:
        if entity.normalized_name == normalized_query:
            candidate, _ = _resolve_entity_candidate(
                session,
                entity,
                EntityMatchKind.EXACT_NAME,
            )
            candidates.append(candidate)
            continue
        for alias in alias_by_entity.get(entity.id, []):
            if alias.normalized_alias == normalized_query:
                candidate, _ = _resolve_entity_candidate(
                    session,
                    entity,
                    EntityMatchKind.EXACT_ALIAS,
                    matched_alias=alias.alias,
                )
                candidates.append(candidate)
                break
    return tuple(_dedupe_candidates(candidates))


def _resolve_fuzzy_candidates(
    *,
    entities: Iterable[CampaignEntity],
    alias_by_entity: dict[uuid.UUID, list[CampaignEntityAlias]],
    normalized_query: str,
    limit: int,
) -> list[ResolvedEntityCandidate]:
    candidates: list[ResolvedEntityCandidate] = []
    for entity in entities:
        if entity.status != EntityStatus.ACTIVE.value:
            continue
        best_alias: CampaignEntityAlias | None = None
        best_score = _score(normalized_query, entity.normalized_name)
        match_kind = EntityMatchKind.FUZZY_NAME
        for alias in alias_by_entity.get(entity.id, []):
            alias_score = _score(normalized_query, alias.normalized_alias)
            if alias_score > best_score:
                best_score = alias_score
                best_alias = alias
                match_kind = EntityMatchKind.FUZZY_ALIAS
        if best_score >= 0.72:
            candidates.append(
                ResolvedEntityCandidate(
                    entity_id=entity.id,
                    canonical_name=entity.canonical_name,
                    kind=EntityKind(entity.kind),
                    status=EntityStatus(entity.status),
                    match_kind=match_kind,
                    score=round(best_score, 4),
                    matched_text=best_alias.alias if best_alias else entity.canonical_name,
                )
            )
    candidates.sort(key=lambda item: (-item.score, item.canonical_name.lower(), item.entity_id))
    return candidates[:limit]


def _resolve_entity_candidate(
    session: Any,
    entity: CampaignEntity,
    match_kind: EntityMatchKind,
    *,
    matched_alias: str | None = None,
) -> tuple[ResolvedEntityCandidate, CampaignEntity]:
    root = _resolve_redirect(session, entity)
    redirected_from = None if root.id == entity.id else entity.id
    candidate = ResolvedEntityCandidate(
        entity_id=root.id,
        canonical_name=root.canonical_name,
        kind=EntityKind(root.kind),
        status=EntityStatus(root.status),
        match_kind=EntityMatchKind.REDIRECT if redirected_from else match_kind,
        score=1.0,
        redirected_from_entity_id=redirected_from,
        matched_text=matched_alias or entity.canonical_name,
    )
    return candidate, root


def _resolve_redirect(session: Any, entity: CampaignEntity) -> CampaignEntity:
    current = entity
    seen: set[uuid.UUID] = set()
    while current.redirect_entity_id is not None:
        if current.id in seen:
            raise ConflictError("Entity redirect cycle detected.")
        seen.add(current.id)
        redirected = session.get(CampaignEntity, current.redirect_entity_id)
        if redirected is None:
            raise ConflictError("Entity redirect target is missing.")
        current = redirected
    return current


def _dedupe_candidates(
    candidates: Iterable[ResolvedEntityCandidate],
) -> list[ResolvedEntityCandidate]:
    deduped: dict[uuid.UUID, ResolvedEntityCandidate] = {}
    for candidate in candidates:
        existing = deduped.get(candidate.entity_id)
        if existing is None or candidate.score > existing.score:
            deduped[candidate.entity_id] = candidate
    return list(deduped.values())


def _score(query: str, candidate: str) -> float:
    return difflib.SequenceMatcher(None, query.casefold(), candidate.casefold()).ratio()


def _to_entity_record(entity: CampaignEntity) -> EntityRecord:
    return EntityRecord(
        id=entity.id,
        campaign_id=entity.campaign_id,
        canonical_name=entity.canonical_name,
        kind=EntityKind(entity.kind),
        status=EntityStatus(entity.status),
        redirect_entity_id=entity.redirect_entity_id,
        archived_at=entity.archived_at,
        archive_reason=entity.archive_reason,
    )


def _to_alias_record(alias: CampaignEntityAlias) -> EntityAliasRecord:
    return EntityAliasRecord(
        id=alias.id,
        campaign_id=alias.campaign_id,
        entity_id=alias.entity_id,
        alias=alias.alias,
    )


def _to_mention_record(mention: CampaignEntityMention) -> EntityMentionRecord:
    return EntityMentionRecord(
        id=mention.id,
        campaign_id=mention.campaign_id,
        entity_id=mention.entity_id,
        source_label=mention.source_label,
        source_excerpt=mention.source_excerpt,
        source_span_start=mention.source_span_start,
        source_span_end=mention.source_span_end,
    )


def _to_merge_record(history: CampaignEntityMergeHistory) -> EntityMergeRecord:
    return EntityMergeRecord(
        id=history.id,
        campaign_id=history.campaign_id,
        source_entity_id=history.source_entity_id,
        target_entity_id=history.target_entity_id,
        event_kind=history.event_kind,  # type: ignore[arg-type]
        event_note=history.event_note,
    )
