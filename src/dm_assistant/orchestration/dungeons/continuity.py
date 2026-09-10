"""Provider-free creative-continuity derivation and task projection."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Literal, cast

from pydantic import JsonValue

from dm_assistant.errors import ConflictError
from dm_assistant.modules.preparation import (
    DungeonGenerationContext,
    GenerationContextEnvelope,
    canonical_json_sha256,
)
from dm_assistant.orchestration.dungeons.contracts import (
    DUNGEON_CREATIVE_CONTINUITY_VERSION,
    DungeonContinuityBranchIntent,
    DungeonContinuityGateIntent,
    DungeonContinuityLoopIntent,
    DungeonContinuityObjectiveIntent,
    DungeonContinuityRoomIntent,
    DungeonCreativeContinuityProjection,
    DungeonEnrichmentContinuityContext,
)
from dm_dungeon import DungeonPackage, DungeonPlan, compile_dungeon_plan

_DUNGEON_CONTEXT_KIND = "dungeon_generation"


def derive_dungeon_creative_continuity(
    envelope: GenerationContextEnvelope,
    plan: DungeonPlan,
) -> DungeonCreativeContinuityProjection:
    """Derive one bounded, self-hashed projection from authorized context and plan."""

    if envelope.context_kind != _DUNGEON_CONTEXT_KIND:
        raise ConflictError(
            "Creative continuity requires a dungeon generation context envelope."
        )
    try:
        context = DungeonGenerationContext.model_validate_json(
            json.dumps(envelope.payload)
        )
    except ValueError as error:
        raise ConflictError(
            "Creative continuity requires a valid dungeon generation payload."
        ) from error
    if envelope.payload_version != context.context_version:
        raise ConflictError("Creative continuity context version is stale.")

    compiled = compile_dungeon_plan(plan)
    if not compiled.accepted:
        raise ConflictError("Creative continuity requires an accepted structural plan.")

    grounded_pins = (
        envelope.campaign_revision_id,
        envelope.corpus_snapshot_id,
        envelope.rules_profile_id,
    )
    if context.grounding_mode == "standalone":
        if any(value is not None for value in grounded_pins):
            raise ConflictError(
                "Standalone creative continuity cannot inherit campaign grounding."
            )
        if envelope.source_links:
            raise ConflictError(
                "Standalone creative continuity must leave campaign lore unknown."
            )
    elif context.grounding_mode == "selected_campaign":
        if any(value is None for value in grounded_pins):
            raise ConflictError(
                "Selected campaign grounding requires exact revision and snapshot pins."
            )
    elif any(value is not None for value in grounded_pins):
        raise ConflictError(
            "Synthetic eval continuity cannot claim campaign grounding pins."
        )

    sources_by_id = {}
    for source in envelope.source_links:
        if source.source_id in sources_by_id:
            raise ConflictError("Creative continuity source IDs must be unique.")
        if source.visibility_policy != envelope.visibility_policy:
            raise ConflictError(
                "Creative continuity source visibility exceeds the selected task scope."
            )
        sources_by_id[source.source_id] = source

    cited_source_ids: set[str] = set()
    for fact in context.selected_facts:
        if context.grounding_mode == "standalone":
            raise ConflictError(
                "Ungrounded standalone creative continuity cannot contain selected lore."
            )
        if fact.visibility_policy != envelope.visibility_policy:
            raise ConflictError(
                "Creative continuity fact visibility exceeds the selected task scope."
            )
        for source_id in fact.source_ids:
            if source_id not in sources_by_id:
                raise ConflictError(
                    "Creative continuity fact cites an unauthorized or stale source."
                )
            cited_source_ids.add(source_id)

    source_links = tuple(
        source
        for source in envelope.source_links
        if source.source_id in cited_source_ids
    )
    campaign_lore_status: Literal["unknown", "selected"] = (
        "selected" if context.selected_facts else "unknown"
    )
    candidate = DungeonCreativeContinuityProjection.model_construct(
        projection_version=DUNGEON_CREATIVE_CONTINUITY_VERSION,
        source_envelope_sha256=canonical_json_sha256(envelope.model_dump(mode="json")),
        source_payload_sha256=envelope.payload_sha256,
        structural_plan_sha256=canonical_json_sha256(plan.model_dump(mode="json")),
        premise=plan.premise,
        themes=plan.themes,
        room_intents=tuple(
            DungeonContinuityRoomIntent(
                room_ref=room.ref,
                name=room.name,
                role=room.role,
                purpose=room.purpose,
                tags=room.tags,
            )
            for room in plan.rooms
        ),
        critical_path=plan.critical_path,
        branches=tuple(
            DungeonContinuityBranchIntent(
                branch_ref=branch.ref,
                from_room_ref=branch.from_room,
                room_refs=branch.rooms,
            )
            for branch in plan.branches
        ),
        loops=tuple(
            DungeonContinuityLoopIntent(
                loop_ref=loop.ref,
                from_room_ref=loop.from_room,
                to_room_ref=loop.to_room,
                secret=loop.secret,
            )
            for loop in plan.loops
        ),
        gates=tuple(
            DungeonContinuityGateIntent(
                gate_ref=gate.ref,
                between_room_refs=(
                    gate.between_rooms[0],
                    gate.between_rooms[1],
                ),
                dependency_room_ref=gate.dependency_room,
                dependency_name=gate.dependency_name,
            )
            for gate in plan.gates
        ),
        objective_intents=tuple(
            DungeonContinuityObjectiveIntent(
                room_ref=content.room_ref,
                name=content.objective,
            )
            for content in plan.room_contents
            if content.objective is not None
        ),
        tones=context.tones,
        motif_variation_constraints=context.motif_variation_constraints,
        campaign_lore_status=campaign_lore_status,
        selected_facts=context.selected_facts,
        source_links=source_links,
        projection_sha256="0" * 64,
    )
    projection_document = cast(
        dict[str, JsonValue],
        candidate.model_dump(mode="json", exclude={"projection_sha256"}),
    )
    return DungeonCreativeContinuityProjection.model_validate(
        {
            **candidate.model_dump(mode="python", exclude={"projection_sha256"}),
            "projection_sha256": canonical_json_sha256(projection_document),
        }
    )


def build_dungeon_enrichment_continuity_context(
    *,
    projection: DungeonCreativeContinuityProjection,
    plan: DungeonPlan,
    package: DungeonPackage,
    room_ids: Iterable[str],
    selected_fact_ids: Iterable[str] = (),
) -> DungeonEnrichmentContinuityContext:
    """Project only exact-room intent and explicitly selected authorized facts."""

    projection_document = projection.model_dump(
        mode="json", exclude={"projection_sha256"}
    )
    if canonical_json_sha256(projection_document) != projection.projection_sha256:
        raise ConflictError("Creative continuity projection hash is stale.")
    if canonical_json_sha256(plan.model_dump(mode="json")) != (
        projection.structural_plan_sha256
    ):
        raise ConflictError("Creative continuity does not match the accepted plan.")

    compiled = compile_dungeon_plan(plan)
    if (
        not compiled.accepted
        or compiled.certificate is None
        or compiled.topology is None
        or package.topology != compiled.topology
    ):
        raise ConflictError(
            "Creative continuity does not match the accepted exact package."
        )

    room_ref_by_id = {room.room_id: room.ref for room in compiled.certificate.rooms}
    selected_room_ids = set(room_ids)
    if not selected_room_ids:
        raise ConflictError("Enrichment continuity requires at least one exact room.")
    if not selected_room_ids.issubset(room_ref_by_id):
        raise ConflictError("Enrichment continuity selected an unknown exact room.")
    selected_room_refs = {room_ref_by_id[room_id] for room_id in selected_room_ids}

    requested_fact_ids = tuple(selected_fact_ids)
    if len(requested_fact_ids) != len(set(requested_fact_ids)):
        raise ConflictError("Enrichment continuity fact IDs must be unique.")
    facts_by_id = {fact.fact_id: fact for fact in projection.selected_facts}
    if not set(requested_fact_ids).issubset(facts_by_id):
        raise ConflictError(
            "Enrichment continuity selected an unauthorized or stale fact."
        )
    selected_facts = tuple(
        fact for fact in projection.selected_facts if fact.fact_id in requested_fact_ids
    )
    selected_source_ids = {
        source_id for fact in selected_facts for source_id in fact.source_ids
    }
    source_links = tuple(
        source
        for source in projection.source_links
        if source.source_id in selected_source_ids
    )

    return DungeonEnrichmentContinuityContext(
        projection_version=projection.projection_version,
        projection_sha256=projection.projection_sha256,
        premise=projection.premise,
        themes=projection.themes,
        room_intents=tuple(
            room
            for room in projection.room_intents
            if room.room_ref in selected_room_refs
        ),
        critical_path=projection.critical_path,
        branches=tuple(
            branch
            for branch in projection.branches
            if branch.from_room_ref in selected_room_refs
            or selected_room_refs.intersection(branch.room_refs)
        ),
        loops=tuple(
            loop
            for loop in projection.loops
            if loop.from_room_ref in selected_room_refs
            or loop.to_room_ref in selected_room_refs
        ),
        gates=tuple(
            gate
            for gate in projection.gates
            if selected_room_refs.intersection(gate.between_room_refs)
            or gate.dependency_room_ref in selected_room_refs
        ),
        objective_intents=tuple(
            objective
            for objective in projection.objective_intents
            if objective.room_ref in selected_room_refs
        ),
        tones=projection.tones,
        motif_variation_constraints=projection.motif_variation_constraints,
        campaign_lore_status=("selected" if selected_facts else "unknown"),
        selected_facts=selected_facts,
        source_links=source_links,
    )
