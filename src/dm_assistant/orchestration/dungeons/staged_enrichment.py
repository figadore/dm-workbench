"""Pure planning for independently failable dungeon enrichment tasks."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal

from pydantic import Field, model_validator

from dm_assistant.orchestration.dungeons.contracts import (
    DungeonDmGuide,
    DungeonStudioSpecification,
    ExactDungeonComponentId,
    WorkflowModel,
)
from dm_dungeon.contracts import EncounterSlotIntent, RoomMechanicMarkerKind, RoomRole

DungeonStagedEnrichmentTaskKind = Literal[
    "puzzle",
    "exploration",
    "feature_interaction",
    "trap",
    "objective",
    "room_narrative",
]

_KIND_ORDER: tuple[DungeonStagedEnrichmentTaskKind, ...] = (
    "puzzle",
    "exploration",
    "feature_interaction",
    "trap",
    "objective",
    "room_narrative",
)


class DungeonStagedEnrichmentTask(WorkflowModel):
    """The next homogeneous exact-ID responsibility; it does not dispatch work."""

    kind: DungeonStagedEnrichmentTaskKind
    room_ids: tuple[ExactDungeonComponentId, ...] = Field(min_length=1, max_length=8)
    target_ids: tuple[ExactDungeonComponentId, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def require_shape_for_task_kind(self) -> DungeonStagedEnrichmentTask:
        if len(self.room_ids) != len(set(self.room_ids)):
            raise ValueError("staged enrichment tasks require unique exact room IDs")
        if len(self.target_ids) != len(set(self.target_ids)):
            raise ValueError("staged enrichment tasks require unique exact target IDs")
        if self.kind == "room_narrative":
            if self.target_ids != self.room_ids:
                raise ValueError("room narrative targets must be the exact room IDs")
        elif len(self.room_ids) != 1 or len(self.target_ids) != 1:
            raise ValueError("one mechanic enrichment task must target one exact slot")
        return self


class DungeonStagedEnrichmentBlocker(WorkflowModel):
    """A body-free reason that makes automatic task selection unsafe."""

    code: Literal[
        "staged_enrichment.guide_missing",
        "staged_enrichment.package_guide_mismatch",
        "staged_enrichment.slot_unsupported",
        "staged_enrichment.accepted_state_inconsistent",
        "staged_enrichment.narrative_waiting_on_mechanics",
    ]
    component_id: ExactDungeonComponentId
    message: str = Field(min_length=1, max_length=300)


class DungeonStagedEnrichmentPlan(WorkflowModel):
    """Deterministic provider-free selection of the next enrichment boundary."""

    schema_version: Literal["1.0.0"] = "1.0.0"
    status: Literal["ready", "blocked", "complete"]
    next_task: DungeonStagedEnrichmentTask | None = None
    blockers: tuple[DungeonStagedEnrichmentBlocker, ...] = ()

    @model_validator(mode="after")
    def require_state_shape(self) -> DungeonStagedEnrichmentPlan:
        if self.status == "ready":
            if self.next_task is None or self.blockers:
                raise ValueError("a ready staged plan requires exactly one next task")
        elif self.status == "blocked":
            if self.next_task is not None or not self.blockers:
                raise ValueError("a blocked staged plan requires blockers and no task")
        elif self.next_task is not None or self.blockers:
            raise ValueError("a complete staged plan has no task or blockers")
        return self


@dataclass(frozen=True)
class _Slot:
    kind: DungeonStagedEnrichmentTaskKind
    room_id: str
    target_id: str


@dataclass(frozen=True)
class _SlotState:
    accepted: tuple[_Slot, ...]
    pending: tuple[_Slot, ...]
    blockers: tuple[DungeonStagedEnrichmentBlocker, ...]


def plan_dungeon_staged_enrichment(
    specification: DungeonStudioSpecification,
) -> DungeonStagedEnrichmentPlan:
    """Select the next task from exact structure, guide state, and accepted lineage.

    This function performs no provider, persistence, topology, geometry, approval, or
    canonical operation. It treats guide content and retained successful lineage as one
    inseparable accepted state so an untracked projection is never overwritten.
    """

    guide = specification.dm_guide
    if guide is None:
        return _blocked(
            DungeonStagedEnrichmentBlocker(
                code="staged_enrichment.guide_missing",
                component_id=specification.package.id,
                message="Staged enrichment requires the current exact DM guide.",
            )
        )

    structural_blockers = _structural_blockers(specification, guide)
    if structural_blockers:
        return _blocked(*structural_blockers)

    slots = _exact_slots(specification, guide)
    lineage_counts, lineage_blockers = _accepted_lineage_counts(specification, slots)
    state = _classify_slots(guide, slots, lineage_counts)
    blockers = _deduplicate_blockers((*lineage_blockers, *state.blockers))
    if blockers:
        return _blocked(*blockers)

    pending_by_kind = {
        kind: tuple(slot for slot in state.pending if slot.kind == kind)
        for kind in _KIND_ORDER
    }
    for kind in _KIND_ORDER[:-1]:
        pending = pending_by_kind[kind]
        if pending:
            slot = pending[0]
            return DungeonStagedEnrichmentPlan(
                status="ready",
                next_task=DungeonStagedEnrichmentTask(
                    kind=kind,
                    room_ids=(slot.room_id,),
                    target_ids=(slot.target_id,),
                ),
            )

    narrative_pending = pending_by_kind["room_narrative"]
    if narrative_pending:
        accepted_mechanic_rooms = _accepted_mechanic_rooms(slots, state.accepted)
        eligible = tuple(
            slot
            for slot in narrative_pending
            if _room_mechanics_complete(
                slot.room_id, slots=slots, accepted_rooms=accepted_mechanic_rooms
            )
        )
        if not eligible:
            return _blocked(
                DungeonStagedEnrichmentBlocker(
                    code="staged_enrichment.narrative_waiting_on_mechanics",
                    component_id=narrative_pending[0].room_id,
                    message=(
                        "Room narrative selection waits until every local mechanic has "
                        "accepted guide content and matching lineage."
                    ),
                )
            )
        room_ids = tuple(slot.room_id for slot in eligible[:8])
        return DungeonStagedEnrichmentPlan(
            status="ready",
            next_task=DungeonStagedEnrichmentTask(
                kind="room_narrative",
                room_ids=room_ids,
                target_ids=room_ids,
            ),
        )

    return DungeonStagedEnrichmentPlan(status="complete")


def _structural_blockers(
    specification: DungeonStudioSpecification,
    guide: DungeonDmGuide,
) -> tuple[DungeonStagedEnrichmentBlocker, ...]:
    package = specification.package
    blockers: list[DungeonStagedEnrichmentBlocker] = []
    package_room_ids = {room.id for room in package.rooms}
    guide_room_ids = {room.room_id for room in guide.rooms}
    if package_room_ids != guide_room_ids:
        component_id = sorted(package_room_ids ^ guide_room_ids)[0]
        blockers.append(
            DungeonStagedEnrichmentBlocker(
                code="staged_enrichment.package_guide_mismatch",
                component_id=component_id,
                message="The current guide room set does not match the exact package.",
            )
        )
        return tuple(blockers)

    guide_rooms = {room.room_id: room for room in guide.rooms}
    for slot in package.encounter_slots:
        if EncounterSlotIntent.EXPLORATION.value not in slot.tags:
            continue
        room = guide_rooms.get(slot.room_id)
        if room is None or room.encounter_slot_id != slot.id:
            blockers.append(
                DungeonStagedEnrichmentBlocker(
                    code="staged_enrichment.package_guide_mismatch",
                    component_id=slot.id,
                    message="An exploration slot is not represented by the exact guide.",
                )
            )

    guide_targets = {
        RoomMechanicMarkerKind.FEATURE: {
            item.marker_id: item.room_id for item in guide.features
        },
        RoomMechanicMarkerKind.TRAP: {
            item.marker_id: item.room_id for item in guide.traps
        },
        RoomMechanicMarkerKind.OBJECTIVE: {
            item.marker_id: item.room_id for item in guide.objectives
        },
    }
    for marker in package.room_mechanic_markers:
        expected = guide_targets.get(marker.kind)
        if expected is not None and expected.get(marker.id) != marker.room_id:
            blockers.append(
                DungeonStagedEnrichmentBlocker(
                    code="staged_enrichment.package_guide_mismatch",
                    component_id=marker.id,
                    message="A structural mechanic slot is not represented by the exact guide.",
                )
            )

    room_id_by_ref = {
        room.ref: room.room_id
        for room in specification.layout_request.certificate.rooms
    }
    exploration_room_ids = {
        slot.room_id
        for slot in package.encounter_slots
        if EncounterSlotIntent.EXPLORATION.value in slot.tags
    }
    feature_room_ids = {
        marker.room_id
        for marker in package.room_mechanic_markers
        if marker.kind is RoomMechanicMarkerKind.FEATURE
    }
    objective_room_ids = {
        marker.room_id
        for marker in package.room_mechanic_markers
        if marker.kind is RoomMechanicMarkerKind.OBJECTIVE
    }
    puzzle_room_ids = {
        room.id for room in package.rooms if room.role is RoomRole.PUZZLE
    }
    for issue in guide.content_issues:
        room_id = room_id_by_ref.get(issue.room_ref, issue.room_ref)
        supported = issue.code == "guide_content.required_missing" and (
            issue.kind == "room"
            or (issue.kind == "puzzle" and room_id in puzzle_room_ids)
            or (issue.kind == "encounter" and room_id in exploration_room_ids)
            or (issue.kind == "feature" and room_id in feature_room_ids)
            or (issue.kind == "objective" and room_id in objective_room_ids)
        )
        if not supported:
            blockers.append(
                DungeonStagedEnrichmentBlocker(
                    code="staged_enrichment.slot_unsupported",
                    component_id=issue.entry_ref or issue.target_ref or room_id,
                    message="The current guide has a blocker outside the staged task set.",
                )
            )
    return _deduplicate_blockers(blockers)


def _exact_slots(
    specification: DungeonStudioSpecification,
    guide: DungeonDmGuide,
) -> tuple[_Slot, ...]:
    package = specification.package
    presentation = {room.room_id: room.presentation_number for room in guide.rooms}
    slots: list[_Slot] = [
        _Slot("puzzle", room.id, room.id)
        for room in package.rooms
        if room.role is RoomRole.PUZZLE
    ]
    slots.extend(
        _Slot("exploration", item.room_id, item.id)
        for item in package.encounter_slots
        if EncounterSlotIntent.EXPLORATION.value in item.tags
    )
    marker_kind: dict[RoomMechanicMarkerKind, DungeonStagedEnrichmentTaskKind] = {
        RoomMechanicMarkerKind.FEATURE: "feature_interaction",
        RoomMechanicMarkerKind.TRAP: "trap",
        RoomMechanicMarkerKind.OBJECTIVE: "objective",
    }
    slots.extend(
        _Slot(marker_kind[marker.kind], marker.room_id, marker.id)
        for marker in package.room_mechanic_markers
        if marker.kind in marker_kind
    )
    slots.extend(_Slot("room_narrative", room.id, room.id) for room in package.rooms)
    kind_order = {kind: index for index, kind in enumerate(_KIND_ORDER)}
    return tuple(
        sorted(
            slots,
            key=lambda slot: (
                kind_order[slot.kind],
                presentation[slot.room_id],
                slot.target_id,
            ),
        )
    )


def _accepted_lineage_counts(
    specification: DungeonStudioSpecification,
    slots: tuple[_Slot, ...],
) -> tuple[Counter[tuple[str, str, str]], tuple[DungeonStagedEnrichmentBlocker, ...]]:
    package_id = specification.package.id
    expected = {(slot.kind, slot.room_id, slot.target_id) for slot in slots}
    counts: Counter[tuple[str, str, str]] = Counter()
    blockers: list[DungeonStagedEnrichmentBlocker] = []

    records: list[tuple[DungeonStagedEnrichmentTaskKind, str, str, str]] = []
    records.extend(
        ("puzzle", item.output.package_id, item.output.room_id, item.output.room_id)
        for item in specification.puzzle_model_lineage
    )
    records.extend(
        (
            "exploration",
            item.output.package_id,
            item.output.room_id,
            item.output.encounter_slot_id,
        )
        for item in specification.exploration_model_lineage
    )
    records.extend(
        (
            "feature_interaction",
            item.output.package_id,
            item.output.room_id,
            item.output.feature_id,
        )
        for item in specification.feature_interaction_model_lineage
    )
    records.extend(
        ("trap", item.output.package_id, item.output.room_id, item.output.trap_id)
        for item in specification.trap_model_lineage
    )
    records.extend(
        (
            "objective",
            item.output.package_id,
            item.output.room_id,
            item.output.objective_id,
        )
        for item in specification.objective_model_lineage
    )
    records.extend(
        ("room_narrative", lineage.output.package_id, room.room_id, room.room_id)
        for lineage in specification.room_narrative_model_lineage
        for room in lineage.output.rooms
    )

    for kind, output_package_id, room_id, target_id in records:
        key = (kind, room_id, target_id)
        if output_package_id != package_id or key not in expected:
            blockers.append(
                DungeonStagedEnrichmentBlocker(
                    code="staged_enrichment.accepted_state_inconsistent",
                    component_id=target_id,
                    message="Accepted lineage targets a stale or unknown exact slot.",
                )
            )
            continue
        counts[key] += 1
    return counts, _deduplicate_blockers(blockers)


def _classify_slots(
    guide: DungeonDmGuide,
    slots: tuple[_Slot, ...],
    lineage_counts: Counter[tuple[str, str, str]],
) -> _SlotState:
    content = _guide_content_state(guide)
    accepted: list[_Slot] = []
    pending: list[_Slot] = []
    blockers: list[DungeonStagedEnrichmentBlocker] = []
    for slot in slots:
        key = (slot.kind, slot.room_id, slot.target_id)
        count = lineage_counts[key]
        has_content = content.get(key, False)
        if count == 1 and has_content:
            accepted.append(slot)
        elif count == 0 and not has_content:
            pending.append(slot)
        else:
            blockers.append(
                DungeonStagedEnrichmentBlocker(
                    code="staged_enrichment.accepted_state_inconsistent",
                    component_id=slot.target_id,
                    message=(
                        "Guide content and retained accepted lineage do not describe "
                        "the same exact enrichment slot."
                    ),
                )
            )
    return _SlotState(tuple(accepted), tuple(pending), tuple(blockers))


def _guide_content_state(guide: DungeonDmGuide) -> dict[tuple[str, str, str], bool]:
    state: dict[tuple[str, str, str], bool] = {}
    state.update(
        {("puzzle", item.room_id, item.room_id): True for item in guide.puzzles}
    )
    state.update(
        {
            ("exploration", room.room_id, room.encounter_slot_id): (
                room.encounter_content is not None
            )
            for room in guide.rooms
            if room.encounter_slot_id is not None
            and room.encounter_slot is EncounterSlotIntent.EXPLORATION
        }
    )
    state.update(
        {
            ("feature_interaction", item.room_id, item.marker_id): item.content
            is not None
            for item in guide.features
        }
    )
    state.update(
        {
            ("trap", item.room_id, item.marker_id): all(
                value is not None
                for value in (
                    item.warning,
                    item.trigger,
                    item.effect,
                    item.detection,
                    item.disable,
                )
            )
            and bool(item.consequences)
            for item in guide.traps
        }
    )
    state.update(
        {
            ("objective", item.room_id, item.marker_id): item.content is not None
            for item in guide.objectives
        }
    )
    state.update(
        {
            ("room_narrative", room.room_id, room.room_id): (
                room.read_aloud is not None and len(room.sensory_details) >= 2
            )
            for room in guide.rooms
        }
    )
    return state


def _accepted_mechanic_rooms(
    slots: tuple[_Slot, ...], accepted: tuple[_Slot, ...]
) -> set[tuple[str, DungeonStagedEnrichmentTaskKind]]:
    accepted_keys = {(slot.kind, slot.room_id, slot.target_id) for slot in accepted}
    return {
        (slot.room_id, slot.kind)
        for slot in slots
        if slot.kind != "room_narrative"
        and (slot.kind, slot.room_id, slot.target_id) in accepted_keys
    }


def _room_mechanics_complete(
    room_id: str,
    *,
    slots: tuple[_Slot, ...],
    accepted_rooms: set[tuple[str, DungeonStagedEnrichmentTaskKind]],
) -> bool:
    required = {
        slot.kind
        for slot in slots
        if slot.room_id == room_id and slot.kind != "room_narrative"
    }
    return all((room_id, kind) in accepted_rooms for kind in required)


def _blocked(
    *blockers: DungeonStagedEnrichmentBlocker,
) -> DungeonStagedEnrichmentPlan:
    return DungeonStagedEnrichmentPlan(
        status="blocked", blockers=_deduplicate_blockers(blockers)
    )


def _deduplicate_blockers(
    blockers: tuple[DungeonStagedEnrichmentBlocker, ...]
    | list[DungeonStagedEnrichmentBlocker],
) -> tuple[DungeonStagedEnrichmentBlocker, ...]:
    unique = {(item.code, item.component_id, item.message): item for item in blockers}
    return tuple(unique[key] for key in sorted(unique))
