"""Dungeon-only creative-continuity derivation and task slicing coverage."""

import json
from typing import Literal
from uuid import UUID

import pytest
from pydantic import ValidationError

from dm_assistant.errors import ConflictError
from dm_assistant.modules.preparation import (
    ContextSourceLink,
    DungeonGenerationContext,
    DungeonGenerationFact,
    GenerationContextEnvelope,
    VisibilityPolicy,
    canonical_json_sha256,
)
from dm_assistant.orchestration.dungeons import (
    DungeonExplorationAffordanceApproval,
    DungeonExplorationContextSelection,
    DungeonFeatureInteractionContextSelection,
    DungeonObjectiveContextSelection,
    DungeonPuzzleContextSelection,
    DungeonTrapContextSelection,
)
from dm_assistant.orchestration.dungeons.continuity import (
    derive_dungeon_creative_continuity,
)
from dm_assistant.orchestration.dungeons.service import (
    build_dungeon_dm_guide,
    build_dungeon_exploration_enrichment_input,
    build_dungeon_feature_interaction_enrichment_input,
    build_dungeon_objective_enrichment_input,
    build_dungeon_puzzle_enrichment_input,
    build_dungeon_trap_enrichment_input,
)
from dm_dungeon import (
    DungeonPackage,
    DungeonPlan,
    LayoutRequest,
    compile_dungeon_plan,
    generate_layout,
)
from dm_dungeon.layout import ORTHOGONAL_LAYOUT_GENERATOR_VERSION


def _plan_and_package() -> tuple[
    DungeonPlan, LayoutRequest, DungeonPackage, dict[str, str]
]:
    plan = DungeonPlan.model_validate_json(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "title": "Synthetic Tide Archive",
                "premise": "Recover a tide ledger before the lower archive floods.",
                "themes": ["measured tides", "weathered brass"],
                "rooms": [
                    {
                        "ref": "quay",
                        "name": "Silt Quay",
                        "role": "entrance",
                        "purpose": "Establish the archive's flooded approach.",
                    },
                    {
                        "ref": "channel",
                        "name": "Gauge Channel",
                        "role": "exploration",
                        "purpose": "Cross a rising channel using the sluice frame.",
                        "encounter": "exploration",
                    },
                    {
                        "ref": "dial",
                        "name": "Tide Dial",
                        "role": "puzzle",
                        "purpose": "Align the recorded tides to release the ledger vault.",
                    },
                    {
                        "ref": "vault",
                        "name": "Ledger Vault",
                        "role": "objective",
                        "purpose": "Hold the synthetic tide ledger objective.",
                    },
                ],
                "critical_path": ["quay", "channel", "dial", "vault"],
                "room_contents": [
                    {
                        "room_ref": "channel",
                        "feature": {
                            "kind": "other",
                            "name": "Sluice Frame",
                            "description": "A brass frame redirects water between two drains.",
                        },
                    },
                    {
                        "room_ref": "quay",
                        "trap": {
                            "name": "Tide Mark Sweep",
                            "challenge": "moderate",
                        },
                    },
                    {"room_ref": "vault", "objective": "Tide Ledger"},
                ],
            }
        )
    )
    compiled = compile_dungeon_plan(plan)
    assert compiled.accepted
    assert compiled.brief is not None
    assert compiled.topology is not None
    assert compiled.certificate is not None
    assert compiled.mechanics_plan is not None
    request = LayoutRequest(
        schema_version="1.0.0",
        package_id="package_synthetic_tide_archive",
        brief=compiled.brief,
        topology=compiled.topology,
        certificate=compiled.certificate,
        seed=714000031,
        generator_version=ORTHOGONAL_LAYOUT_GENERATOR_VERSION,
        mechanics_plan=compiled.mechanics_plan,
        floor_bounds=compiled.floor_bounds,
    )
    layout = generate_layout(request)
    assert layout.success and layout.package is not None
    room_ids = {room.ref: room.room_id for room in compiled.certificate.rooms}
    return plan, request, layout.package, room_ids


def _envelope(
    *,
    grounding_mode: Literal["standalone", "selected_campaign"] = "selected_campaign",
    source_visibility: VisibilityPolicy = VisibilityPolicy.DM_ONLY,
    include_facts: bool = True,
) -> GenerationContextEnvelope:
    facts = (
        (
            DungeonGenerationFact(
                fact_id="tide_history",
                kind="history",
                summary="The archive measures floods against three historic brass marks.",
                source_ids=("source_history",),
            ),
            DungeonGenerationFact(
                fact_id="sluice_custom",
                kind="environment",
                summary="Archive keepers redirect water rather than attempting to stop it.",
                source_ids=("source_environment",),
            ),
            DungeonGenerationFact(
                fact_id="unused_faction",
                kind="faction",
                summary="A surveyor guild once audited the ledgers.",
                source_ids=("source_faction",),
            ),
        )
        if include_facts
        else ()
    )
    payload = DungeonGenerationContext(
        context_version="1.0.0",
        prompt_input_sha256="1" * 64,
        requested_constraints=("Keep the flood recoverable",),
        tones=("watchful", "rain-worn"),
        motif_variation_constraints=(
            "Vary the tide motif between sound, motion, and recorded measurement.",
        ),
        selected_facts=facts,
        grounding_mode=grounding_mode,
        preparation_owner_id="dm",
        context_provenance="synthetic_grounded_selection",
    )
    payload_document = payload.model_dump(mode="json")
    source_links = (
        tuple(
            ContextSourceLink(
                source_kind="document_revision",
                source_id=source_id,
                revision_id=f"revision_{index}",
                sha256=f"{index}" * 64,
                visibility_policy=source_visibility,
            )
            for index, source_id in enumerate(
                ("source_history", "source_environment", "source_faction"),
                start=1,
            )
        )
        if include_facts
        else ()
    )
    return GenerationContextEnvelope(
        context_kind="dungeon_generation",
        payload_version="1.0.0",
        campaign_revision_id=UUID(int=1),
        corpus_snapshot_id=UUID(int=2),
        rules_profile_id=UUID(int=3),
        visibility_policy=VisibilityPolicy.DM_ONLY,
        source_links=source_links,
        payload=payload_document,
        payload_sha256=canonical_json_sha256(payload_document),
    )


def test_local_enrichments_inherit_one_hash_with_relevant_authorized_facts() -> None:
    plan, request, package, room_ids = _plan_and_package()
    projection = derive_dungeon_creative_continuity(_envelope(), plan)
    feature_id = next(
        marker.id
        for marker in package.room_mechanic_markers
        if marker.room_id == room_ids["channel"] and marker.kind.value == "feature"
    )

    puzzle = build_dungeon_puzzle_enrichment_input(
        package,
        DungeonPuzzleContextSelection(
            room_id=room_ids["dial"],
            continuity_fact_ids=("tide_history",),
        ),
        plan=plan,
        creative_continuity=projection,
    )
    exploration = build_dungeon_exploration_enrichment_input(
        package,
        DungeonExplorationContextSelection(
            room_id=room_ids["channel"],
            continuity_fact_ids=("sluice_custom",),
            affordances=(
                DungeonExplorationAffordanceApproval(
                    affordance_id=feature_id,
                    use="Redirect the rising water between the room's two drains.",
                ),
            ),
            pacing_role="rising_tension",
            stakes="Delay wets exposed supplies but never blocks the only route.",
        ),
        plan=plan,
        creative_continuity=projection,
    )
    guide = build_dungeon_dm_guide(request, package, plan)
    feature = build_dungeon_feature_interaction_enrichment_input(
        package,
        guide,
        DungeonFeatureInteractionContextSelection(
            room_id=room_ids["channel"],
            feature_id=feature_id,
            continuity_fact_ids=("sluice_custom",),
            interaction_goal="Redirect the rising channel without stopping its flow.",
            stakes="A poor setting wets supplies without blocking the route.",
        ),
        plan=plan,
        creative_continuity=projection,
    )
    trap_id = next(
        marker.id
        for marker in package.room_mechanic_markers
        if marker.room_id == room_ids["quay"] and marker.kind.value == "trap"
    )
    trap = build_dungeon_trap_enrichment_input(
        package,
        guide,
        DungeonTrapContextSelection(
            room_id=room_ids["quay"],
            trap_id=trap_id,
            continuity_fact_ids=("tide_history",),
            stakes="The sweep scatters supplies without sealing the route.",
        ),
        plan=plan,
        creative_continuity=projection,
    )
    objective_id = next(
        marker.id
        for marker in package.room_mechanic_markers
        if marker.room_id == room_ids["vault"] and marker.kind.value == "objective"
    )
    objective = build_dungeon_objective_enrichment_input(
        package,
        guide,
        DungeonObjectiveContextSelection(
            room_id=room_ids["vault"],
            objective_id=objective_id,
            continuity_fact_ids=("tide_history",),
            stakes="Recover the ledger before the lower archive floods.",
        ),
        plan=plan,
        creative_continuity=projection,
    )

    contexts = (
        puzzle.continuity,
        exploration.continuity,
        feature.continuity,
        trap.continuity,
        objective.continuity,
    )
    assert {context.projection_version for context in contexts} == {
        projection.projection_version
    }
    assert {context.projection_sha256 for context in contexts} == {
        projection.projection_sha256
    }
    assert [fact.fact_id for fact in puzzle.continuity.selected_facts] == [
        "tide_history"
    ]
    assert [source.source_id for source in puzzle.continuity.source_links] == [
        "source_history"
    ]
    assert [fact.fact_id for fact in exploration.continuity.selected_facts] == [
        "sluice_custom"
    ]
    assert [source.source_id for source in exploration.continuity.source_links] == [
        "source_environment"
    ]
    assert [fact.fact_id for fact in feature.continuity.selected_facts] == [
        "sluice_custom"
    ]
    assert [source.source_id for source in feature.continuity.source_links] == [
        "source_environment"
    ]
    assert [fact.fact_id for fact in trap.continuity.selected_facts] == ["tide_history"]
    assert [source.source_id for source in trap.continuity.source_links] == [
        "source_history"
    ]
    assert [fact.fact_id for fact in objective.continuity.selected_facts] == [
        "tide_history"
    ]
    assert [source.source_id for source in objective.continuity.source_links] == [
        "source_history"
    ]
    assert "unused_faction" not in {
        fact.fact_id for context in contexts for fact in context.selected_facts
    }
    assert {room.room_ref for room in puzzle.continuity.room_intents} == {"dial"}
    assert {room.room_ref for room in exploration.continuity.room_intents} == {
        "channel"
    }
    assert {room.room_ref for room in feature.continuity.room_intents} == {"channel"}
    assert {room.room_ref for room in trap.continuity.room_intents} == {"quay"}
    assert {room.room_ref for room in objective.continuity.room_intents} == {"vault"}
    assert {item.name for item in objective.continuity.objective_intents} == {
        "Tide Ledger"
    }


def test_context_builders_reject_stale_projection_and_unauthorized_fact() -> None:
    plan, request, package, room_ids = _plan_and_package()
    projection = derive_dungeon_creative_continuity(_envelope(), plan)
    stale = projection.model_copy(update={"projection_sha256": "f" * 64})

    with pytest.raises(ConflictError, match="hash is stale"):
        build_dungeon_puzzle_enrichment_input(
            package,
            DungeonPuzzleContextSelection(room_id=room_ids["dial"]),
            plan=plan,
            creative_continuity=stale,
        )

    guide = build_dungeon_dm_guide(request, package, plan)
    feature_id = next(
        marker.id
        for marker in package.room_mechanic_markers
        if marker.room_id == room_ids["channel"] and marker.kind.value == "feature"
    )
    with pytest.raises(ConflictError, match="hash is stale"):
        build_dungeon_feature_interaction_enrichment_input(
            package,
            guide,
            DungeonFeatureInteractionContextSelection(
                room_id=room_ids["channel"],
                feature_id=feature_id,
                interaction_goal="Redirect the channel.",
                stakes="Supplies may get wet.",
            ),
            plan=plan,
            creative_continuity=stale,
        )

    trap_id = next(
        marker.id
        for marker in package.room_mechanic_markers
        if marker.room_id == room_ids["quay"] and marker.kind.value == "trap"
    )
    with pytest.raises(ConflictError, match="unauthorized or stale fact"):
        build_dungeon_trap_enrichment_input(
            package,
            guide,
            DungeonTrapContextSelection(
                room_id=room_ids["quay"],
                trap_id=trap_id,
                continuity_fact_ids=("invented_lore",),
                stakes="Supplies may scatter.",
            ),
            plan=plan,
            creative_continuity=projection,
        )

    objective_id = next(
        marker.id
        for marker in package.room_mechanic_markers
        if marker.room_id == room_ids["vault"] and marker.kind.value == "objective"
    )
    objective_selection = DungeonObjectiveContextSelection(
        room_id=room_ids["vault"],
        objective_id=objective_id,
        stakes="Recover the ledger before the archive floods.",
    )
    with pytest.raises(ConflictError, match="hash is stale"):
        build_dungeon_objective_enrichment_input(
            package,
            guide,
            objective_selection,
            plan=plan,
            creative_continuity=stale,
        )
    with pytest.raises(ConflictError, match="unauthorized or stale fact"):
        build_dungeon_objective_enrichment_input(
            package,
            guide,
            objective_selection.model_copy(
                update={"continuity_fact_ids": ("invented_lore",)}
            ),
            plan=plan,
            creative_continuity=projection,
        )


def test_projection_rejects_broader_visibility_and_ungrounded_lore() -> None:
    plan, _, _, _ = _plan_and_package()
    with pytest.raises(ConflictError, match="source visibility exceeds"):
        derive_dungeon_creative_continuity(
            _envelope(source_visibility=VisibilityPolicy.ALL_CAMPAIGN_PLAYERS),
            plan,
        )

    fact = DungeonGenerationFact(
        fact_id="invented_history",
        kind="history",
        summary="This fact must not enter an ungrounded standalone dungeon.",
        source_ids=("source_history",),
    )
    with pytest.raises(ValidationError, match="standalone dungeon context"):
        DungeonGenerationContext(
            context_version="1.0.0",
            prompt_input_sha256="2" * 64,
            selected_facts=(fact,),
            grounding_mode="standalone",
            preparation_owner_id="dm",
            context_provenance="synthetic_standalone",
        )

    standalone = DungeonGenerationContext(
        context_version="1.0.0",
        prompt_input_sha256="3" * 64,
        preparation_owner_id="dm",
        context_provenance="synthetic_standalone",
    )
    payload = standalone.model_dump(mode="json")
    envelope = GenerationContextEnvelope(
        context_kind="dungeon_generation",
        payload_version="1.0.0",
        source_links=(
            ContextSourceLink(
                source_kind="document_revision",
                source_id="unselected_source",
            ),
        ),
        payload=payload,
        payload_sha256=canonical_json_sha256(payload),
    )
    with pytest.raises(ConflictError, match="leave campaign lore unknown"):
        derive_dungeon_creative_continuity(envelope, plan)
