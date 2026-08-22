"""Code-owned short-callout allocation and collision-free map annotation layout."""

from enum import StrEnum
from typing import Literal

from dm_dungeon.contracts.common import ContractModel, OpaqueId, VersionedContract
from dm_dungeon.contracts.geometry import (
    GridPoint,
    LayeredMapElement,
    MapGeometry,
    PointGeometry,
    PolygonGeometry,
    PolylineGeometry,
    RectangleGeometry,
    SegmentGeometry,
)
from dm_dungeon.contracts.package import (
    DungeonPackage,
    RoomMechanicMarkerKind,
    VerticalEndpointDoorLayout,
)
from dm_dungeon.rendering.contracts import RenderAudience

MAP_KEY_SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"


class MapCalloutKind(StrEnum):
    """Trusted map-key kinds; their short prefixes are renderer-owned."""

    ROOM = "room"
    DOOR = "door"
    HAZARD = "hazard"
    PUZZLE = "puzzle"
    FEATURE = "feature"
    OBJECTIVE = "objective"
    TRANSITION = "transition"


class MapCallout(ContractModel):
    """One stable key entry and its collision-tested SVG placement."""

    component_id: OpaqueId
    kind: MapCalloutKind
    token: str
    floor_id: OpaqueId
    anchor: GridPoint
    label_x: float
    label_y: float
    width: float
    height: float
    leader_required: bool
    badges: tuple[str, ...] = ()


class MapKey(VersionedContract):
    """Per-floor projection shared by SVG, raster, and later DM-guide consumers."""

    supported_schema_version = MAP_KEY_SCHEMA_VERSION

    schema_version: Literal["1.0.0"]
    floor_id: OpaqueId
    audience: RenderAudience
    entries: tuple[MapCallout, ...]


def build_map_key(
    package: DungeonPackage,
    floor_id: str,
    audience: RenderAudience,
    *,
    scale: int,
) -> MapKey:
    """Allocate short callouts in a deterministic, non-overlapping order.

    Callouts are only allocated after audience filtering.  Thus a player projection
    cannot infer DM-only component counts or IDs through numbering gaps.
    """
    layers = {layer.id: layer for layer in package.layers}

    def visible(
        component: LayeredMapElement | VerticalEndpointDoorLayout,
    ) -> bool:
        layer = layers[component.layer_id]
        if audience is RenderAudience.DM:
            return layer.include_in_dm_export
        return (
            component.visibility.value == "player_safe"
            and layer.visibility.value == "player_safe"
            and layer.include_in_player_export
        )

    candidates: list[tuple[MapCalloutKind, str, GridPoint, tuple[str, ...]]] = []
    for room in package.rooms:
        if room.floor_id == floor_id and visible(room):
            candidates.append(
                (MapCalloutKind.ROOM, room.id, _polygon_anchor(room.boundary), ())
            )
    for door in package.composable_doors:
        if door.floor_id == floor_id and visible(door):
            badges: tuple[str, ...] = ()
            if audience is RenderAudience.DM:
                badges = tuple(
                    badge
                    for active, badge in (
                        (door.mechanics.concealed, "S"),
                        (door.mechanics.gate_id is not None, "L"),
                        (door.mechanics.trap_id is not None, "T"),
                    )
                    if active
                )
            candidates.append(
                (
                    MapCalloutKind.DOOR,
                    door.id,
                    _segment_anchor(door.segment.start, door.segment.end),
                    badges,
                )
            )
    for endpoint_door in package.vertical_endpoint_doors:
        if endpoint_door.floor_id != floor_id or not visible(endpoint_door):
            continue
        badges = (
            tuple(
                badge
                for active, badge in (
                    (endpoint_door.mechanics.concealed, "S"),
                    (endpoint_door.mechanics.gate_id is not None, "L"),
                    (endpoint_door.mechanics.trap_id is not None, "T"),
                )
                if active
            )
            if audience is RenderAudience.DM
            else ()
        )
        candidates.append(
            (
                MapCalloutKind.DOOR,
                endpoint_door.id,
                endpoint_door.position,
                badges,
            )
        )
    for hazard in package.hazards:
        if hazard.floor_id == floor_id and visible(hazard):
            candidates.append(
                (
                    MapCalloutKind.HAZARD,
                    hazard.id,
                    _geometry_anchor(hazard.geometry),
                    (),
                )
            )
    for feature in package.features:
        if feature.floor_id == floor_id and visible(feature):
            candidates.append(
                (
                    MapCalloutKind.FEATURE,
                    feature.id,
                    _geometry_anchor(feature.geometry),
                    (),
                )
            )
    marker_kinds = {
        RoomMechanicMarkerKind.TRAP: MapCalloutKind.HAZARD,
        RoomMechanicMarkerKind.PUZZLE: MapCalloutKind.PUZZLE,
        RoomMechanicMarkerKind.FEATURE: MapCalloutKind.FEATURE,
        RoomMechanicMarkerKind.OBJECTIVE: MapCalloutKind.OBJECTIVE,
    }
    for marker in package.room_mechanic_markers:
        if marker.floor_id == floor_id and visible(marker):
            candidates.append(
                (marker_kinds[marker.kind], marker.id, marker.position, ())
            )
    stair_ids = set()
    for stair in package.stairs:
        if stair.floor_id == floor_id and visible(stair):
            candidates.append((MapCalloutKind.TRANSITION, stair.id, stair.position, ()))
            stair_ids.add(stair.id)
    for link in package.vertical_links:
        if link.visibility.value != "player_safe" and audience is not RenderAudience.DM:
            continue
        for endpoint in link.endpoints:
            if (
                endpoint.floor_id == floor_id
                and endpoint.stair_id not in stair_ids
                and (
                    audience is RenderAudience.DM
                    or endpoint.visibility.value == "player_safe"
                )
            ):
                candidates.append(
                    (MapCalloutKind.TRANSITION, link.id, endpoint.position, ())
                )

    prefixes = {
        MapCalloutKind.DOOR: "D",
        MapCalloutKind.HAZARD: "T",
        MapCalloutKind.PUZZLE: "P",
        MapCalloutKind.FEATURE: "F",
        MapCalloutKind.OBJECTIVE: "O",
        MapCalloutKind.TRANSITION: "X",
    }
    numbered: list[tuple[MapCalloutKind, str, GridPoint, str, tuple[str, ...]]] = []
    for kind in MapCalloutKind:
        items = sorted(item for item in candidates if item[0] is kind)
        for number, (_, component_id, anchor, badges) in enumerate(items, start=1):
            token = (
                str(number)
                if kind is MapCalloutKind.ROOM
                else f"{prefixes[kind]}{number}"
            )
            numbered.append((kind, component_id, anchor, token, badges))

    occupied: list[tuple[float, float, float, float]] = []
    entries: list[MapCallout] = []
    for kind, component_id, anchor, token, badges in numbered:
        width, height = _text_bounds(token, scale)
        anchor_x, anchor_y = anchor.x * scale, anchor.y * scale
        positions = (
            (0, 0),
            (0, -0.55),
            (0.55, 0),
            (-0.55, 0),
            (0, 0.55),
            (0.6, -0.55),
            (-0.6, -0.55),
        )
        chosen: tuple[float, float] | None = None
        leader = False
        for dx, dy in positions:
            x, y = anchor_x + dx * scale, anchor_y + dy * scale
            box = _box(x, y, width, height)
            if not any(_intersects(box, prior) for prior in occupied):
                chosen = (x, y)
                break
        if chosen is None:
            # A deterministic outer ring is collision-free for finite inputs; the
            # leader makes the association explicit rather than obscuring geometry.
            ring = 1
            while chosen is None:
                for dx, dy in (
                    (ring, -ring),
                    (ring, ring),
                    (-ring, ring),
                    (-ring, -ring),
                ):
                    x, y = anchor_x + dx * scale, anchor_y + dy * scale
                    box = _box(x, y, width, height)
                    if not any(_intersects(box, prior) for prior in occupied):
                        chosen, leader = (x, y), True
                        break
                ring += 1
        assert chosen is not None
        label_x, label_y = chosen
        occupied.append(_box(label_x, label_y, width, height))
        entries.append(
            MapCallout(
                component_id=component_id,
                kind=kind,
                token=token,
                floor_id=floor_id,
                anchor=anchor,
                label_x=label_x,
                label_y=label_y,
                width=width,
                height=height,
                leader_required=leader,
                badges=badges,
            )
        )
    return MapKey(
        schema_version=MAP_KEY_SCHEMA_VERSION,
        floor_id=floor_id,
        audience=audience,
        entries=tuple(entries),
    )


def _text_bounds(token: str, scale: int) -> tuple[float, float]:
    """Pinned font-metric approximation, including a circle/marker clearance."""
    font_size = max(9, min(14, round(scale * 0.24)))
    return (
        max(font_size * 1.4, font_size * (0.62 * len(token) + 0.7)),
        font_size * 1.45,
    )


def _box(
    x: float, y: float, width: float, height: float
) -> tuple[float, float, float, float]:
    return (x - width / 2, y - height / 2, x + width / 2, y + height / 2)


def _intersects(
    first: tuple[float, float, float, float], second: tuple[float, float, float, float]
) -> bool:
    return not (
        first[2] <= second[0]
        or second[2] <= first[0]
        or first[3] <= second[1]
        or second[3] <= first[1]
    )


def _polygon_anchor(geometry: PolygonGeometry) -> GridPoint:
    return GridPoint(
        x=round(sum(point.x for point in geometry.points) / len(geometry.points)),
        y=round(sum(point.y for point in geometry.points) / len(geometry.points)),
    )


def _segment_anchor(start: GridPoint, end: GridPoint) -> GridPoint:
    return GridPoint(x=round((start.x + end.x) / 2), y=round((start.y + end.y) / 2))


def _geometry_anchor(geometry: MapGeometry) -> GridPoint:
    if isinstance(geometry, PointGeometry):
        return geometry.point
    if isinstance(geometry, SegmentGeometry):
        return _segment_anchor(geometry.segment.start, geometry.segment.end)
    if isinstance(geometry, (PolylineGeometry, PolygonGeometry)):
        return GridPoint(
            x=round(sum(point.x for point in geometry.points) / len(geometry.points)),
            y=round(sum(point.y for point in geometry.points) / len(geometry.points)),
        )
    if isinstance(geometry, RectangleGeometry):
        return GridPoint(
            x=geometry.origin.x + geometry.width_cells // 2,
            y=geometry.origin.y + geometry.height_cells // 2,
        )
    raise TypeError(f"unsupported geometry {type(geometry)!r}")
