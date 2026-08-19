"""P7-13 exact package contract with explicit passage endpoint openings.

This contract is deliberately separate from the retained ``DungeonPackage`` 1.1.0
reader.  New generation records the opening in each room wall and the direction a
passage must travel away from that wall; old packages remain byte-for-byte
round-trippable through their original model.
"""

from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from dm_dungeon.contracts.common import ContractModel, OpaqueId, ensure_unique_ids
from dm_dungeon.contracts.geometry import GridSegment
from dm_dungeon.contracts.package import DungeonPackage

DUNGEON_PACKAGE_V2_SCHEMA_VERSION = "1.2.0"


class PassageApproachDirection(StrEnum):
    """Direction from a room wall into the attached passage."""

    NORTH = "north"
    EAST = "east"
    SOUTH = "south"
    WEST = "west"


class PassageOpening(ContractModel):
    """One declared room-wall opening used by a P7-13 passage.

    The opening is a one-cell wall segment. ``approach_direction`` points from
    the room through that segment to the first exterior corridor cell.
    """

    id: OpaqueId
    corridor_id: OpaqueId
    room_id: OpaqueId
    segment: GridSegment
    approach_direction: PassageApproachDirection

    @model_validator(mode="after")
    def require_one_cell_directional_segment(self) -> Self:
        dx = self.segment.end.x - self.segment.start.x
        dy = self.segment.end.y - self.segment.start.y
        if abs(dx) + abs(dy) != 1:
            raise ValueError("passage openings require one-cell wall segments")
        if (
            self.approach_direction
            in {
                PassageApproachDirection.NORTH,
                PassageApproachDirection.SOUTH,
            }
            and dy != 0
        ):
            raise ValueError("north/south passage openings require horizontal segments")
        if (
            self.approach_direction
            in {
                PassageApproachDirection.EAST,
                PassageApproachDirection.WEST,
            }
            and dx != 0
        ):
            raise ValueError("east/west passage openings require vertical segments")
        return self


class DungeonPackageV2(DungeonPackage):
    """New exact package with retained-artifact-safe passage semantics."""

    supported_schema_version = DUNGEON_PACKAGE_V2_SCHEMA_VERSION

    schema_version: Literal["1.2.0"]  # type: ignore[assignment]
    passage_openings: tuple[PassageOpening, ...] = ()

    @model_validator(mode="after")
    def require_complete_passage_openings(self) -> Self:
        ensure_unique_ids(
            {"passage_openings": (item.id for item in self.passage_openings)}
        )
        corridors = {corridor.id: corridor for corridor in self.corridors}
        openings_by_corridor: dict[str, list[PassageOpening]] = {}
        for opening in self.passage_openings:
            corridor = corridors.get(opening.corridor_id)
            if corridor is None:
                raise ValueError(
                    f"passage opening {opening.id!r} references unknown corridor "
                    f"{opening.corridor_id!r}"
                )
            if opening.room_id not in corridor.connects_room_ids:
                raise ValueError(
                    f"passage opening {opening.id!r} room is not connected by "
                    f"corridor {corridor.id!r}"
                )
            openings_by_corridor.setdefault(corridor.id, []).append(opening)

        for corridor in self.corridors:
            openings = openings_by_corridor.get(corridor.id, [])
            if len(openings) != 2 or {item.room_id for item in openings} != set(
                corridor.connects_room_ids
            ):
                raise ValueError(
                    f"corridor {corridor.id!r} requires one passage opening for "
                    "each connected room"
                )
        return self
