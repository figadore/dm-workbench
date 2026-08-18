"""Renderer-neutral exact square-grid dungeon geometry contracts."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    OpaqueId,
    ShortText,
    Visibility,
    VisibleContract,
)
from dm_dungeon.contracts.topology import (
    DoorType,
    RoomCapacity,
    RoomRole,
    StairDirection,
    VerticalLinkKind,
)

GridCoordinate = Annotated[int, Field(ge=0)]
PositiveCells = Annotated[int, Field(ge=1)]
NonNegativeCount = Annotated[int, Field(ge=0)]
PositiveCount = Annotated[int, Field(ge=1)]


class GridType(StrEnum):
    """Supported tactical grid types."""

    SQUARE = "square"


class GridSpec(ContractModel):
    """Scale and orientation shared by an exact package."""

    grid_type: GridType = GridType.SQUARE
    cell_scale_feet: PositiveCells = 5
    orthogonal: Literal[True] = True


class GridPoint(ContractModel):
    """An integer point in floor-local grid coordinates."""

    x: GridCoordinate
    y: GridCoordinate


class GridSegment(ContractModel):
    """A renderer-neutral line segment."""

    start: GridPoint
    end: GridPoint


class PointGeometry(ContractModel):
    """A single map point."""

    kind: Literal["point"]
    point: GridPoint


class SegmentGeometry(ContractModel):
    """A line-segment map shape."""

    kind: Literal["segment"]
    segment: GridSegment


class PolylineGeometry(ContractModel):
    """An ordered open path."""

    kind: Literal["polyline"]
    points: tuple[GridPoint, ...] = Field(min_length=2)


class PolygonGeometry(ContractModel):
    """A renderer-neutral closed area whose final edge is implicit."""

    kind: Literal["polygon"]
    points: tuple[GridPoint, ...] = Field(min_length=3)


class RectangleGeometry(ContractModel):
    """An orthogonal rectangle in grid coordinates."""

    kind: Literal["rectangle"]
    origin: GridPoint
    width_cells: PositiveCells
    height_cells: PositiveCells


type MapGeometry = Annotated[
    PointGeometry
    | SegmentGeometry
    | PolylineGeometry
    | PolygonGeometry
    | RectangleGeometry,
    Field(discriminator="kind"),
]


class RenderLayerKind(StrEnum):
    """Semantic layer categories understood by later renderers."""

    BASE = "base"
    DM_ANNOTATIONS = "dm_annotations"
    DM_SECRETS = "dm_secrets"
    FEATURES = "features"
    GRID = "grid"
    LABELS = "labels"
    TERRAIN = "terrain"


class RenderLayer(VisibleContract):
    """An ordered render layer with fail-closed export policy."""

    id: OpaqueId
    name: ShortText
    kind: RenderLayerKind
    z_index: int
    include_in_dm_export: bool
    include_in_player_export: bool

    @model_validator(mode="after")
    def prevent_dm_layer_publication(self) -> Self:
        if self.visibility is Visibility.DM_ONLY and self.include_in_player_export:
            raise ValueError("dm_only layers cannot be included in player exports")
        return self


class LayeredMapElement(VisibleContract):
    """An exact map element assigned to one declared render layer."""

    id: OpaqueId
    layer_id: OpaqueId


class FloorBoundMapElement(LayeredMapElement):
    """A layered map element located on one declared floor."""

    floor_id: OpaqueId


class RoomBoundMapElement(FloorBoundMapElement):
    """A floor element optionally associated with a containing room."""

    room_id: OpaqueId | None


class FloorLayout(LayeredMapElement):
    """Exact bounds for one independently laid-out floor."""

    name: ShortText
    level_index: int
    bounds: RectangleGeometry


class RoomLayout(FloorBoundMapElement):
    """Exact room polygon corresponding to one topology room ID."""

    role: RoomRole
    boundary: PolygonGeometry
    capacity: RoomCapacity
    tags: tuple[ShortText, ...] = ()


class CorridorLayout(FloorBoundMapElement):
    """Exact centerline and width for a corridor."""

    path: PolylineGeometry
    width_cells: PositiveCells
    connects_room_ids: tuple[OpaqueId, OpaqueId]


class DoorLayout(FloorBoundMapElement):
    """Exact segment and mechanics classification for a door."""

    door_type: DoorType
    segment: GridSegment
    connects_room_ids: tuple[OpaqueId, OpaqueId]
    gate_id: OpaqueId | None = None
    hazard_id: OpaqueId | None = None

    @model_validator(mode="after")
    def validate_door_requirements(self) -> Self:
        if self.door_type is DoorType.LOCKED and self.gate_id is None:
            raise ValueError("locked doors require gate_id")
        if self.door_type is DoorType.TRAPPED and self.hazard_id is None:
            raise ValueError("trapped doors require hazard_id")
        if self.door_type in {DoorType.SECRET, DoorType.TRAPPED}:
            if self.visibility is not Visibility.DM_ONLY:
                raise ValueError("secret and trapped doors must be dm_only")
        return self


class StairLayout(FloorBoundMapElement):
    """One rendered stair endpoint on a floor."""

    position: GridPoint
    direction: StairDirection
    vertical_link_id: OpaqueId
    hidden: bool = False


class VerticalEndpoint(ContractModel):
    """One endpoint of a cross-floor link."""

    floor_id: OpaqueId
    position: GridPoint
    stair_id: OpaqueId | None = None
    hidden: bool = False


class VerticalLinkLayout(VisibleContract):
    """A paired or multi-stop connection between floor positions."""

    id: OpaqueId
    link_type: VerticalLinkKind
    endpoints: tuple[VerticalEndpoint, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def require_distinct_floors(self) -> Self:
        floor_ids = {endpoint.floor_id for endpoint in self.endpoints}
        if len(floor_ids) != len(self.endpoints):
            raise ValueError("vertical-link endpoints must use distinct floors")
        return self


class FeatureKind(StrEnum):
    """Initial physical feature vocabulary."""

    ALTAR = "altar"
    BRIDGE = "bridge"
    FURNITURE = "furniture"
    PILLAR = "pillar"
    PIT = "pit"
    STATUE = "statue"
    OTHER = "other"


class Feature(RoomBoundMapElement):
    """A physical map feature with exact renderer-neutral geometry."""

    kind: FeatureKind
    name: ShortText
    geometry: MapGeometry
    details: NonEmptyText | None = None


class TerrainKind(StrEnum):
    """Initial terrain vocabulary."""

    DIFFICULT = "difficult"
    ICE = "ice"
    LAVA = "lava"
    RUBBLE = "rubble"
    WATER = "water"
    OTHER = "other"


class Terrain(RoomBoundMapElement):
    """An area affecting traversal or presentation."""

    kind: TerrainKind
    area: PolygonGeometry
    movement_cost_multiplier: PositiveCount
    blocks_movement: bool


class HazardKind(StrEnum):
    """Initial map-hazard vocabulary."""

    ENVIRONMENTAL = "environmental"
    MAGICAL = "magical"
    PIT = "pit"
    TRAP = "trap"
    OTHER = "other"


class Hazard(RoomBoundMapElement):
    """A classified hazard; hidden details stay on DM-only layers."""

    kind: HazardKind
    name: ShortText
    geometry: MapGeometry
    trigger: NonEmptyText
    effect: NonEmptyText
    detection_difficulty: NonNegativeCount | None = None
    disable_difficulty: NonNegativeCount | None = None


class ZoneKind(StrEnum):
    """Semantic areas used by rendering and encounter fit."""

    ENCOUNTER = "encounter"
    HAZARD = "hazard"
    OBJECTIVE = "objective"
    SPAWN = "spawn"
    TERRAIN = "terrain"
    OTHER = "other"


class Zone(RoomBoundMapElement):
    """A named semantic map area."""

    kind: ZoneKind
    name: ShortText
    geometry: MapGeometry


class Label(FloorBoundMapElement):
    """A classified text label at an exact grid position."""

    text: ShortText
    position: GridPoint
    rotation_degrees: int = 0


class PositionAnchorKind(StrEnum):
    """Purpose of a stable point marker."""

    CLUE = "clue"
    CREATURE_START = "creature_start"
    ENTRANCE = "entrance"
    EXIT = "exit"
    INTERACTION = "interaction"
    TREASURE = "treasure"
    OTHER = "other"


class PositionAnchor(RoomBoundMapElement):
    """A stable exact point referenced by later preparation artifacts."""

    kind: PositionAnchorKind
    position: GridPoint
    name: ShortText


class EncounterSlot(FloorBoundMapElement):
    """A stable capacity-oriented slot, not an encounter implementation."""

    room_id: OpaqueId
    zone_id: OpaqueId | None = None
    anchor_ids: tuple[OpaqueId, ...] = ()
    minimum_creatures: NonNegativeCount
    maximum_creatures: NonNegativeCount
    tags: tuple[ShortText, ...] = ()

    @model_validator(mode="after")
    def validate_creature_bounds(self) -> Self:
        if self.minimum_creatures > self.maximum_creatures:
            raise ValueError("minimum_creatures cannot exceed maximum_creatures")
        return self
