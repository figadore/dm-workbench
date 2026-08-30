"""Deterministic, layer-filtered SVG renderer for exact dungeon packages."""

import hashlib
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable

from dm_dungeon.contracts.common import Visibility
from dm_dungeon.contracts.geometry import (
    CorridorLayout,
    GridPoint,
    GridSegment,
    LayeredMapElement,
    MapGeometry,
    PointGeometry,
    PolygonGeometry,
    PolylineGeometry,
    PositionAnchorKind,
    RectangleGeometry,
    RenderLayer,
    SegmentGeometry,
    VerticalLinkLayout,
)
from dm_dungeon.contracts.package import (
    DungeonPackage,
    RoomMechanicMarkerKind,
    VerticalEndpointDoorLayout,
)
from dm_dungeon.contracts.topology import DoorType, StairDirection
from dm_dungeon.rendering.annotations import MapCalloutKind, build_map_key
from dm_dungeon.rendering.contracts import (
    SVG_RENDER_RESULT_SCHEMA_VERSION,
    SVG_RENDERER_VERSION,
    RenderAudience,
    SvgAnnotationMode,
    SvgRenderDiagnostic,
    SvgRenderDiagnosticCode,
    SvgRenderRequest,
    SvgRenderResult,
    SvgThemeName,
)
from dm_dungeon.rendering.themes import get_theme
from dm_dungeon.validation import DiagnosticSeverity, validate_geometry
from dm_dungeon.validation.grid import cells_for_corridor

SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def render_svg(package: DungeonPackage, request: SvgRenderRequest) -> SvgRenderResult:
    """Render one floor after fail-closed audience filtering."""
    diagnostics: list[SvgRenderDiagnostic] = []
    if request.package_id != package.id:
        diagnostics.append(
            _diagnostic(
                SvgRenderDiagnosticCode.PACKAGE_ID_MISMATCH,
                (package.id, request.package_id),
                f"Render request targets package {request.package_id!r}, not "
                f"{package.id!r}.",
                "Use the exact package ID pinned by the render caller.",
            )
        )

    floor = next((item for item in package.floors if item.id == request.floor_id), None)
    if floor is None:
        diagnostics.append(
            _diagnostic(
                SvgRenderDiagnosticCode.FLOOR_UNKNOWN,
                (request.floor_id,),
                f"Render request references unknown floor {request.floor_id!r}.",
                "Select a floor declared by the exact package.",
            )
        )
    elif request.audience is RenderAudience.PLAYER and floor.visibility is not (
        Visibility.PLAYER_SAFE
    ):
        diagnostics.append(
            _diagnostic(
                SvgRenderDiagnosticCode.FLOOR_NOT_PUBLISHABLE,
                (floor.id,),
                f"Floor {floor.id!r} is not classified for player publication.",
                "Use the DM audience or explicitly publish a player-safe floor version.",
            )
        )

    geometry_report = validate_geometry(package)
    for finding in geometry_report.diagnostics:
        if finding.severity is DiagnosticSeverity.ERROR:
            diagnostics.append(
                _diagnostic(
                    SvgRenderDiagnosticCode.GEOMETRY_INVALID,
                    finding.affected_ids,
                    finding.message,
                    finding.repair_hint,
                    source_code=finding.code.value,
                )
            )
    if diagnostics or floor is None:
        return _failed_result(package, request, diagnostics)

    layers = {layer.id: layer for layer in package.layers}
    if not _layered_visible(floor, layers, request.audience):
        return _failed_result(
            package,
            request,
            [
                _diagnostic(
                    SvgRenderDiagnosticCode.FLOOR_NOT_PUBLISHABLE,
                    (floor.id,),
                    f"Floor {floor.id!r} render layer excludes the requested audience.",
                    "Enable the audience on the floor layer or choose another floor.",
                )
            ],
        )

    scale = request.pixels_per_cell
    width = floor.bounds.width_cells * scale
    height = floor.bounds.height_cells * scale
    root = ET.Element(
        "svg",
        {
            "xmlns": SVG_NAMESPACE,
            "version": "1.1",
            "width": str(width),
            "height": str(height),
            "viewBox": f"0 0 {width} {height}",
            "role": "img",
            "data-renderer-version": SVG_RENDERER_VERSION,
            "data-package-id": package.id,
            "data-floor-id": floor.id,
            "data-audience": request.audience.value,
            "data-theme": request.theme.value,
        },
    )
    title = ET.SubElement(root, "title")
    title.text = f"{request.audience.value.title()} dungeon map"
    style = ET.SubElement(root, "style", {"type": "text/css"})
    theme = get_theme(request.theme)
    style.text = theme.css + (
        theme.callout_css
        if _annotation_mode(package, request) is SvgAnnotationMode.CALLOUTS
        else ""
    )
    ET.SubElement(
        root,
        "rect",
        {
            "id": "map-background",
            "class": "map-background",
            "x": "0",
            "y": "0",
            "width": str(width),
            "height": str(height),
        },
    )

    rendered_ids: list[str] = []
    _render_terrain_and_zones(
        root,
        package,
        floor.id,
        layers,
        request,
        scale,
        rendered_ids,
    )
    _render_corridors(
        root,
        package,
        floor.id,
        layers,
        request,
        scale,
        rendered_ids,
    )
    if request.show_grid:
        _render_grid(root, floor.bounds.width_cells, floor.bounds.height_cells, scale)
    _render_rooms(
        root,
        package,
        floor.id,
        layers,
        request,
        scale,
        rendered_ids,
    )
    _render_passage_openings(
        root,
        package,
        floor.id,
        layers,
        request,
        scale,
    )
    _render_doors(
        root,
        package,
        floor.id,
        layers,
        request,
        scale,
        rendered_ids,
    )
    _render_features_and_hazards(
        root,
        package,
        floor.id,
        layers,
        request,
        scale,
        rendered_ids,
    )
    _render_transitions(
        root,
        package,
        floor.id,
        layers,
        request,
        scale,
        rendered_ids,
    )
    if request.show_labels and (
        request.audience is RenderAudience.DM
        or _annotation_mode(package, request) is SvgAnnotationMode.DEVELOPER_IDS
    ):
        _render_labels(
            root,
            package,
            floor.id,
            layers,
            request,
            scale,
            rendered_ids,
        )
    if request.show_markers:
        _render_markers(
            root,
            package,
            floor.id,
            layers,
            request,
            scale,
            rendered_ids,
        )
    if _annotation_mode(package, request) is SvgAnnotationMode.CALLOUTS:
        _render_callouts(root, package, floor.id, request, scale)
        if request.audience is RenderAudience.DM:
            _render_dm_legend(
                root,
                package,
                floor.id,
                layers,
                request,
                scale,
            )

    svg = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    digest = hashlib.sha256(svg.encode("utf-8")).hexdigest()
    return SvgRenderResult(
        schema_version=SVG_RENDER_RESULT_SCHEMA_VERSION,
        renderer_version=SVG_RENDERER_VERSION,
        package_id=package.id,
        floor_id=floor.id,
        audience=request.audience,
        success=True,
        width_pixels=width,
        height_pixels=height,
        svg=svg,
        sha256=digest,
        rendered_component_ids=tuple(rendered_ids),
        diagnostics=(),
    )


def _render_grid(
    root: ET.Element, width_cells: int, height_cells: int, scale: int
) -> None:
    group = ET.SubElement(root, "g", {"id": "grid", "data-kind": "grid"})
    for x in range(width_cells + 1):
        coordinate = x * scale
        ET.SubElement(
            group,
            "line",
            {
                "class": "grid-line",
                "x1": str(coordinate),
                "y1": "0",
                "x2": str(coordinate),
                "y2": str(height_cells * scale),
            },
        )
    for y in range(height_cells + 1):
        coordinate = y * scale
        ET.SubElement(
            group,
            "line",
            {
                "class": "grid-line",
                "x1": "0",
                "y1": str(coordinate),
                "x2": str(width_cells * scale),
                "y2": str(coordinate),
            },
        )


def _render_terrain_and_zones(
    root: ET.Element,
    package: DungeonPackage,
    floor_id: str,
    layers: dict[str, RenderLayer],
    request: SvgRenderRequest,
    scale: int,
    rendered_ids: list[str],
) -> None:
    group = ET.SubElement(root, "g", {"id": "terrain-and-zones"})
    for terrain in package.terrain:
        if terrain.floor_id == floor_id and _layered_visible(
            terrain, layers, request.audience
        ):
            component = _component_group(group, terrain, "terrain", rendered_ids)
            _append_geometry(component, terrain.area, scale, "terrain")
    for zone in package.zones:
        if zone.floor_id == floor_id and _layered_visible(
            zone, layers, request.audience
        ):
            component = _component_group(group, zone, "zone", rendered_ids)
            _append_geometry(component, zone.geometry, scale, "zone")


def _render_corridors(
    root: ET.Element,
    package: DungeonPackage,
    floor_id: str,
    layers: dict[str, RenderLayer],
    request: SvgRenderRequest,
    scale: int,
    rendered_ids: list[str],
) -> None:
    group = ET.SubElement(root, "g", {"id": "corridors"})
    for corridor in package.corridors:
        if corridor.floor_id != floor_id or not _layered_visible(
            corridor, layers, request.audience
        ):
            continue
        component = _component_group(group, corridor, "corridor", rendered_ids)
        opening_segments = tuple(
            opening.segment
            for opening in package.passage_openings
            if opening.corridor_id == corridor.id
        )
        cells, outline_edges = _corridor_footprint_primitives(
            corridor,
            scale,
            opening_segments,
        )
        for left, top, right, bottom in cells:
            ET.SubElement(
                component,
                "rect",
                {
                    "class": "corridor",
                    "x": str(left),
                    "y": str(top),
                    "width": str(right - left),
                    "height": str(bottom - top),
                },
            )
        for start, end in outline_edges:
            ET.SubElement(
                component,
                "line",
                {
                    "class": "corridor-outline",
                    "x1": str(start[0]),
                    "y1": str(start[1]),
                    "x2": str(end[0]),
                    "y2": str(end[1]),
                    "stroke-width": "4",
                },
            )


def _corridor_footprint_primitives(
    corridor: CorridorLayout,
    scale: int,
    opening_segments: tuple[GridSegment, ...] = (),
) -> tuple[
    tuple[tuple[int, int, int, int], ...],
    tuple[tuple[tuple[int, int], tuple[int, int]], ...],
]:
    """Project the exact validated footprint into every trusted drawing adapter.

    Rectangles and lines are deliberately used instead of compact SVG path syntax:
    the same primitives are consumed by browser SVG, Pillow PNG, and ReportLab PDF
    adapters, preventing corridor walls from disappearing in raster review maps.
    """
    cells = cells_for_corridor(corridor.path, corridor.width_cells)
    opening_edges = {
        _segment_key_points(
            (segment.start.x * scale, segment.start.y * scale),
            (segment.end.x * scale, segment.end.y * scale),
        )
        for segment in opening_segments
    }
    cell_rectangles: list[tuple[int, int, int, int]] = []
    outline_edges: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for x, y in sorted(cells, key=lambda cell: (cell[1], cell[0])):
        left = x * scale
        top = y * scale
        right = (x + 1) * scale
        bottom = (y + 1) * scale
        cell_rectangles.append((left, top, right, bottom))
        for neighbor, start, end in (
            ((x, y - 1), (left, top), (right, top)),
            ((x + 1, y), (right, top), (right, bottom)),
            ((x, y + 1), (right, bottom), (left, bottom)),
            ((x - 1, y), (left, bottom), (left, top)),
        ):
            if (
                neighbor not in cells
                and _segment_key_points(start, end) not in opening_edges
            ):
                outline_edges.append((start, end))
    return tuple(cell_rectangles), tuple(outline_edges)


def _render_rooms(
    root: ET.Element,
    package: DungeonPackage,
    floor_id: str,
    layers: dict[str, RenderLayer],
    request: SvgRenderRequest,
    scale: int,
    rendered_ids: list[str],
) -> None:
    group = ET.SubElement(root, "g", {"id": "rooms"})
    for room in package.rooms:
        if room.floor_id != floor_id or not _layered_visible(
            room, layers, request.audience
        ):
            continue
        component = _component_group(group, room, "room", rendered_ids)
        ET.SubElement(
            component,
            "polygon",
            {
                "class": "room",
                "points": _points(room.boundary.points, scale),
            },
        )
        if (
            _annotation_mode(package, request) is SvgAnnotationMode.DEVELOPER_IDS
            and request.audience is RenderAudience.DM
        ):
            center = _polygon_center(room.boundary)
            annotation = ET.SubElement(
                component,
                "text",
                {
                    "class": "annotation",
                    "x": _number(center[0] * scale),
                    "y": _number(center[1] * scale),
                    "text-anchor": "middle",
                    "data-kind": "room-id",
                },
            )
            annotation.text = room.id


def _render_passage_openings(
    root: ET.Element,
    package: DungeonPackage,
    floor_id: str,
    layers: dict[str, RenderLayer],
    request: SvgRenderRequest,
    scale: int,
) -> None:
    """Erase room-wall strokes at validated V1 passage openings."""
    corridors = {corridor.id: corridor for corridor in package.corridors}
    group = ET.SubElement(root, "g", {"id": "passage-openings"})
    for opening in package.passage_openings:
        corridor = corridors[opening.corridor_id]
        if corridor.floor_id != floor_id or not _layered_visible(
            corridor, layers, request.audience
        ):
            continue
        ET.SubElement(
            group,
            "line",
            {
                "class": "passage-opening",
                "stroke": "#fff",
                "stroke-width": "4" if request.theme is SvgThemeName.LOW_INK else "3",
                "vector-effect": "non-scaling-stroke",
                "x1": str(opening.segment.start.x * scale),
                "y1": str(opening.segment.start.y * scale),
                "x2": str(opening.segment.end.x * scale),
                "y2": str(opening.segment.end.y * scale),
            },
        )


def _render_doors(
    root: ET.Element,
    package: DungeonPackage,
    floor_id: str,
    layers: dict[str, RenderLayer],
    request: SvgRenderRequest,
    scale: int,
    rendered_ids: list[str],
) -> None:
    group = ET.SubElement(root, "g", {"id": "doors"})
    for door in package.composable_doors:
        if door.floor_id != floor_id or not _layered_visible(
            door, layers, request.audience
        ):
            continue
        component = _component_group(group, door, "door", rendered_ids)
        rendered_door_type = (
            DoorType.NORMAL
            if request.audience is RenderAudience.PLAYER
            else (
                DoorType.SECRET
                if door.mechanics.concealed
                else (
                    DoorType.TRAPPED
                    if door.mechanics.trap_id is not None
                    else (
                        DoorType.LOCKED
                        if door.mechanics.gate_id is not None
                        else DoorType.NORMAL
                    )
                )
            )
        )
        if request.audience is RenderAudience.DM:
            component.set("data-door-concealed", str(door.mechanics.concealed).lower())
            component.set(
                "data-door-gated", str(door.mechanics.gate_id is not None).lower()
            )
            component.set(
                "data-door-trapped", str(door.mechanics.trap_id is not None).lower()
            )
        component.set("data-door-type", rendered_door_type.value)
        css_class = "door"
        if rendered_door_type is DoorType.SECRET:
            css_class += " door-secret"
        elif rendered_door_type is DoorType.TRAPPED:
            css_class += " door-trapped"
        ET.SubElement(
            component,
            "line",
            {
                "class": css_class,
                # Keep the width explicit so browser SVG, Pillow PNG, and ReportLab
                # PDF all render the same unmistakable slab over the lighter grid.
                "stroke-width": ("6" if request.theme is SvgThemeName.LOW_INK else "5"),
                "x1": str(door.segment.start.x * scale),
                "y1": str(door.segment.start.y * scale),
                "x2": str(door.segment.end.x * scale),
                "y2": str(door.segment.end.y * scale),
            },
        )
        if _annotation_mode(
            package, request
        ) is SvgAnnotationMode.DEVELOPER_IDS and rendered_door_type in {
            DoorType.SECRET,
            DoorType.TRAPPED,
        }:
            midpoint = _segment_midpoint(door.segment.start, door.segment.end)
            symbol = ET.SubElement(
                component,
                "text",
                {
                    "class": "annotation",
                    "x": _number(midpoint[0] * scale),
                    "y": _number(midpoint[1] * scale),
                    "text-anchor": "middle",
                    "data-kind": "door-secret-symbol",
                },
            )
            symbol.text = "S" if rendered_door_type is DoorType.SECRET else "!"


def _render_features_and_hazards(
    root: ET.Element,
    package: DungeonPackage,
    floor_id: str,
    layers: dict[str, RenderLayer],
    request: SvgRenderRequest,
    scale: int,
    rendered_ids: list[str],
) -> None:
    group = ET.SubElement(root, "g", {"id": "features-and-hazards"})
    for feature in package.features:
        if feature.floor_id == floor_id and _layered_visible(
            feature, layers, request.audience
        ):
            component = _component_group(group, feature, "feature", rendered_ids)
            component.set("data-feature-kind", feature.kind.value)
            _append_geometry(component, feature.geometry, scale, "feature")
    for hazard in package.hazards:
        if hazard.floor_id == floor_id and _layered_visible(
            hazard, layers, request.audience
        ):
            component = _component_group(group, hazard, "hazard", rendered_ids)
            component.set("data-hazard-kind", hazard.kind.value)
            _append_geometry(component, hazard.geometry, scale, "hazard")
    for marker in package.room_mechanic_markers:
        if marker.floor_id != floor_id or not _layered_visible(
            marker, layers, request.audience
        ):
            continue
        if (
            request.audience is RenderAudience.PLAYER
            and marker.kind is not RoomMechanicMarkerKind.FEATURE
        ):
            continue
        component = _component_group(
            group, marker, "room-mechanic-marker", rendered_ids
        )
        component.set("data-mechanic-kind", marker.kind.value)
        if _annotation_mode(package, request) is not SvgAnnotationMode.CALLOUTS:
            _append_room_mechanic_symbol(component, marker.position, marker.kind, scale)


def _render_transitions(
    root: ET.Element,
    package: DungeonPackage,
    floor_id: str,
    layers: dict[str, RenderLayer],
    request: SvgRenderRequest,
    scale: int,
    rendered_ids: list[str],
) -> None:
    group = ET.SubElement(root, "g", {"id": "transitions"})
    rendered_stair_ids: set[str] = set()
    for stair in package.stairs:
        if stair.floor_id != floor_id or not _layered_visible(
            stair, layers, request.audience
        ):
            continue
        component = _component_group(group, stair, "stair", rendered_ids)
        _append_transition_symbol(
            component,
            stair.position,
            stair.direction.value,
            scale,
        )
        rendered_stair_ids.add(stair.id)

    for link in package.vertical_links:
        if not _nonlayered_visible(link, request.audience):
            continue
        visible_endpoints = [
            (index, endpoint)
            for index, endpoint in enumerate(link.endpoints)
            if endpoint.floor_id == floor_id
            and (
                request.audience is RenderAudience.DM
                or endpoint.visibility is Visibility.PLAYER_SAFE
            )
            and (
                endpoint.stair_id is None or endpoint.stair_id not in rendered_stair_ids
            )
        ]
        for index, endpoint in visible_endpoints:
            component = ET.SubElement(
                group,
                "g",
                {
                    "id": f"{_xml_id(link.id)}-endpoint-{index}",
                    "data-component-id": link.id,
                    "data-kind": "vertical-link",
                    "data-link-kind": link.link_type.value,
                    "data-visibility": link.visibility.value,
                },
            )
            if link.id not in rendered_ids:
                rendered_ids.append(link.id)
            _append_transition_symbol(
                component,
                endpoint.position,
                link.link_type.value,
                scale,
            )

    for endpoint_door in package.vertical_endpoint_doors:
        if endpoint_door.floor_id != floor_id or not _layered_visible(
            endpoint_door, layers, request.audience
        ):
            continue
        component = _component_group(
            group, endpoint_door, "vertical-endpoint-door", rendered_ids
        )
        component.set("data-endpoint", endpoint_door.endpoint.value)
        component.set("data-endpoint-kind", endpoint_door.kind.value)
        if request.audience is RenderAudience.DM:
            component.set(
                "data-door-concealed",
                str(endpoint_door.mechanics.concealed).lower(),
            )
            component.set(
                "data-door-gated",
                str(endpoint_door.mechanics.gate_id is not None).lower(),
            )
            component.set(
                "data-door-trapped",
                str(endpoint_door.mechanics.trap_id is not None).lower(),
            )
        _append_endpoint_door_symbol(component, endpoint_door, scale)


def _append_endpoint_door_symbol(
    parent: ET.Element,
    endpoint_door: VerticalEndpointDoorLayout,
    scale: int,
) -> None:
    """Draw a point-anchored door/hatch without embedding DM-only mechanics."""

    x = endpoint_door.position.x * scale
    y = endpoint_door.position.y * scale
    half = scale * 0.28
    attributes = {
        "class": "door",
        "x": _number(x - half),
        "y": _number(y - half),
        "width": _number(half * 2),
        "height": _number(half * 2),
    }
    if endpoint_door.kind.value == "hatch":
        attributes["rx"] = _number(scale * 0.08)
    ET.SubElement(parent, "rect", attributes)


def _render_callouts(
    root: ET.Element,
    package: DungeonPackage,
    floor_id: str,
    request: SvgRenderRequest,
    scale: int,
) -> None:
    """Draw the same short key projection used by raster/export consumers."""
    group = ET.SubElement(root, "g", {"id": "callouts", "data-kind": "callouts"})
    for entry in build_map_key(
        package, floor_id, request.audience, scale=scale
    ).entries:
        if entry.leader_required:
            ET.SubElement(
                group,
                "line",
                {
                    "class": "callout-leader",
                    "x1": _number(entry.anchor.x * scale),
                    "y1": _number(entry.anchor.y * scale),
                    "x2": _number(entry.label_x),
                    "y2": _number(entry.label_y),
                },
            )
        if entry.kind is MapCalloutKind.ROOM:
            ET.SubElement(
                group,
                "circle",
                {
                    "class": "room-callout",
                    "cx": _number(entry.label_x),
                    "cy": _number(entry.label_y),
                    "r": _number(entry.width / 2),
                },
            )
        elif entry.kind is MapCalloutKind.HAZARD:
            half = entry.width / 2
            ET.SubElement(
                group,
                "polygon",
                {
                    "class": "hazard-callout",
                    "points": f"{entry.label_x},{entry.label_y - half} {entry.label_x + half},{entry.label_y + half} {entry.label_x - half},{entry.label_y + half}",
                },
            )
        elif entry.kind is MapCalloutKind.PUZZLE:
            half = entry.width / 2
            ET.SubElement(
                group,
                "polygon",
                {
                    "class": "component-callout",
                    "points": f"{_number(entry.label_x)},{_number(entry.label_y - half)} "
                    f"{_number(entry.label_x + half)},{_number(entry.label_y)} "
                    f"{_number(entry.label_x)},{_number(entry.label_y + half)} "
                    f"{_number(entry.label_x - half)},{_number(entry.label_y)}",
                },
            )
        elif entry.kind is MapCalloutKind.FEATURE:
            half = entry.width / 2
            ET.SubElement(
                group,
                "rect",
                {
                    "class": "feature-callout",
                    "x": _number(entry.label_x - half),
                    "y": _number(entry.label_y - half),
                    "width": _number(half * 2),
                    "height": _number(half * 2),
                },
            )
        elif entry.kind is MapCalloutKind.OBJECTIVE:
            for ring, radius in (
                ("outer", entry.width / 2),
                ("inner", entry.width / 2 - max(2.5, scale * 0.045)),
            ):
                ET.SubElement(
                    group,
                    "circle",
                    {
                        "class": "component-callout objective-callout",
                        "cx": _number(entry.label_x),
                        "cy": _number(entry.label_y),
                        "r": _number(radius),
                        "data-objective-callout": entry.token,
                        "data-ring": ring,
                    },
                )
        else:
            ET.SubElement(
                group,
                "circle",
                {
                    "class": "component-callout",
                    "cx": _number(entry.label_x),
                    "cy": _number(entry.label_y),
                    "r": _number(entry.width / 2),
                },
            )
        text = ET.SubElement(
            group,
            "text",
            {
                "class": "callout-text",
                "x": _number(entry.label_x),
                "y": _number(entry.label_y + entry.text_height * 0.28),
                "text-anchor": "middle",
                "font-size": _number(entry.text_height / 1.45),
                "data-callout": entry.token,
                "data-component-id": entry.component_id,
                "data-kind": entry.kind.value,
            },
        )
        text.text = entry.token
        if request.audience is RenderAudience.DM:
            for badge in entry.badges:
                ET.SubElement(
                    group,
                    "rect",
                    {
                        "class": "callout-badge-shape",
                        "x": _number(badge.label_x - badge.width / 2),
                        "y": _number(badge.label_y - badge.height / 2),
                        "width": _number(badge.width),
                        "height": _number(badge.height),
                        "rx": _number(badge.width * 0.18),
                    },
                )
                badge_text = ET.SubElement(
                    group,
                    "text",
                    {
                        "class": "callout-badge",
                        "x": _number(badge.label_x),
                        "y": _number(badge.label_y + badge.height * 0.28),
                        "text-anchor": "middle",
                        "font-size": _number(badge.height * 0.72),
                        "data-badge": badge.token,
                    },
                )
                badge_text.text = badge.token


def _render_dm_legend(
    root: ET.Element,
    package: DungeonPackage,
    floor_id: str,
    layers: dict[str, RenderLayer],
    request: SvgRenderRequest,
    scale: int,
) -> None:
    """Render a compact, grayscale-safe map key in an unoccupied floor corner."""

    floor = next(item for item in package.floors if item.id == floor_id)
    canvas_width = floor.bounds.width_cells * scale
    canvas_height = floor.bounds.height_cells * scale
    margin = max(8.0, scale * 0.16)
    panel_width = min(canvas_width - 2 * margin, max(360.0, scale * 8.0))
    panel_height = min(canvas_height - 2 * margin, max(112.0, scale * 2.0))
    if panel_width <= 0 or panel_height <= 0:
        return

    occupied: list[tuple[float, float, float, float]] = []
    for room in package.rooms:
        if room.floor_id != floor_id or not _layered_visible(
            room, layers, request.audience
        ):
            continue
        xs = [point.x * scale for point in room.boundary.points]
        ys = [point.y * scale for point in room.boundary.points]
        occupied.append((min(xs), min(ys), max(xs), max(ys)))
    for corridor in package.corridors:
        if corridor.floor_id != floor_id or not _layered_visible(
            corridor, layers, request.audience
        ):
            continue
        cells = cells_for_corridor(corridor.path, corridor.width_cells)
        if cells:
            occupied.append(
                (
                    min(cell[0] for cell in cells) * scale,
                    min(cell[1] for cell in cells) * scale,
                    (max(cell[0] for cell in cells) + 1) * scale,
                    (max(cell[1] for cell in cells) + 1) * scale,
                )
            )
    for entry in build_map_key(
        package, floor_id, request.audience, scale=scale
    ).entries:
        occupied.append(
            (
                entry.label_x - entry.width / 2,
                entry.label_y - entry.height / 2,
                entry.label_x + entry.width / 2,
                entry.label_y + entry.height / 2,
            )
        )
        occupied.extend(
            (
                badge.label_x - badge.width / 2,
                badge.label_y - badge.height / 2,
                badge.label_x + badge.width / 2,
                badge.label_y + badge.height / 2,
            )
            for badge in entry.badges
        )

    candidates = (
        (margin, margin),
        (canvas_width - margin - panel_width, margin),
        (margin, canvas_height - margin - panel_height),
        (
            canvas_width - margin - panel_width,
            canvas_height - margin - panel_height,
        ),
    )
    ranked = []
    for index, (x, y) in enumerate(candidates):
        box = (x, y, x + panel_width, y + panel_height)
        overlap_count = sum(_boxes_intersect(box, item) for item in occupied)
        ranked.append((overlap_count, index, x, y))
    _, _, origin_x, origin_y = min(ranked)

    group = ET.SubElement(
        root,
        "g",
        {"id": "dm-map-legend", "data-kind": "map-legend"},
    )
    ET.SubElement(
        group,
        "rect",
        {
            "class": "map-legend-panel",
            "x": _number(origin_x),
            "y": _number(origin_y),
            "width": _number(panel_width),
            "height": _number(panel_height),
            "rx": _number(max(3.0, scale * 0.08)),
        },
    )
    font_size = max(11.0, min(15.0, scale * 0.22))
    title = ET.SubElement(
        group,
        "text",
        {
            "class": "legend-title",
            "x": _number(origin_x + 10),
            "y": _number(origin_y + font_size + 5),
            "font-size": _number(font_size),
        },
    )
    title.text = "MAP KEY"

    entries = (
        ("room", "Room"),
        ("start", "Start"),
        ("door", "Door"),
        ("lock-secret", "Lock / secret"),
        ("trap", "Trap"),
        ("feature", "Feature"),
        ("objective", "Objective"),
        ("encounter", "Encounter slot"),
    )
    header_height = font_size + 12
    row_height = (panel_height - header_height) / 2
    column_width = panel_width / 4
    symbol_radius = max(6.0, min(10.0, row_height * 0.2))
    for index, (kind, label) in enumerate(entries):
        column = index % 4
        row = index // 4
        item_x = origin_x + column * column_width
        center_x = item_x + symbol_radius + 10
        center_y = origin_y + header_height + row_height * (row + 0.5)
        _append_legend_symbol(group, kind, center_x, center_y, symbol_radius, font_size)
        text = ET.SubElement(
            group,
            "text",
            {
                "class": "legend-text",
                "x": _number(center_x + symbol_radius + 7),
                "y": _number(center_y + font_size * 0.32),
                "font-size": _number(font_size),
                "data-legend-label": kind,
            },
        )
        text.text = label


def _append_legend_symbol(
    parent: ET.Element,
    kind: str,
    x: float,
    y: float,
    radius: float,
    font_size: float,
) -> None:
    symbol_class = f"legend-symbol legend-{kind}"
    if kind in {"room", "objective"}:
        ET.SubElement(
            parent,
            "circle",
            {
                "class": symbol_class,
                "cx": _number(x),
                "cy": _number(y),
                "r": _number(radius),
            },
        )
        if kind == "objective":
            ET.SubElement(
                parent,
                "circle",
                {
                    "class": symbol_class,
                    "cx": _number(x),
                    "cy": _number(y),
                    "r": _number(radius * 0.58),
                },
            )
        elif kind == "room":
            text = ET.SubElement(
                parent,
                "text",
                {
                    "class": "legend-symbol-text",
                    "x": _number(x),
                    "y": _number(y + font_size * 0.28),
                    "text-anchor": "middle",
                    "font-size": _number(font_size * 0.78),
                },
            )
            text.text = "1"
    elif kind == "start":
        _append_start_symbol_at(parent, x, y, radius * 2.2)
    elif kind == "door":
        ET.SubElement(
            parent,
            "line",
            {
                "class": symbol_class,
                "x1": _number(x - radius),
                "y1": _number(y),
                "x2": _number(x + radius),
                "y2": _number(y),
                "stroke-width": "3",
            },
        )
    elif kind == "trap":
        ET.SubElement(
            parent,
            "polygon",
            {
                "class": symbol_class,
                "points": f"{_number(x)},{_number(y - radius)} "
                f"{_number(x + radius)},{_number(y + radius)} "
                f"{_number(x - radius)},{_number(y + radius)}",
            },
        )
    else:
        ET.SubElement(
            parent,
            "rect",
            {
                "class": symbol_class,
                "x": _number(x - radius),
                "y": _number(y - radius),
                "width": _number(radius * 2),
                "height": _number(radius * 2),
                "rx": _number(radius * 0.18 if kind == "lock-secret" else 0),
            },
        )
        if kind == "lock-secret":
            text = ET.SubElement(
                parent,
                "text",
                {
                    "class": "legend-symbol-text",
                    "x": _number(x),
                    "y": _number(y + font_size * 0.25),
                    "text-anchor": "middle",
                    "font-size": _number(font_size * 0.62),
                },
            )
            text.text = "L/S"


def _boxes_intersect(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> bool:
    return not (
        first[2] <= second[0]
        or second[2] <= first[0]
        or first[3] <= second[1]
        or second[3] <= first[1]
    )


def _annotation_mode(
    package: DungeonPackage, request: SvgRenderRequest
) -> SvgAnnotationMode:
    """Resolve developer inspection, DM callouts, or clean player geometry."""
    if request.show_room_ids:
        return SvgAnnotationMode.DEVELOPER_IDS
    if request.audience is RenderAudience.PLAYER:
        return SvgAnnotationMode.NONE
    return request.annotation_mode


def _render_labels(
    root: ET.Element,
    package: DungeonPackage,
    floor_id: str,
    layers: dict[str, RenderLayer],
    request: SvgRenderRequest,
    scale: int,
    rendered_ids: list[str],
) -> None:
    group = ET.SubElement(root, "g", {"id": "labels"})
    for label in package.labels:
        if label.floor_id != floor_id or not _layered_visible(
            label, layers, request.audience
        ):
            continue
        component = _component_group(group, label, "label", rendered_ids)
        text = ET.SubElement(
            component,
            "text",
            {
                "class": "label",
                "x": str(label.position.x * scale),
                "y": str(label.position.y * scale),
                "transform": (
                    f"rotate({label.rotation_degrees} "
                    f"{label.position.x * scale} {label.position.y * scale})"
                ),
            },
        )
        text.text = label.text


def _render_markers(
    root: ET.Element,
    package: DungeonPackage,
    floor_id: str,
    layers: dict[str, RenderLayer],
    request: SvgRenderRequest,
    scale: int,
    rendered_ids: list[str],
) -> None:
    group = ET.SubElement(root, "g", {"id": "markers"})
    anchors = {anchor.id: anchor for anchor in package.position_anchors}
    rooms = {room.id: room for room in package.rooms}
    developer_mode = (
        _annotation_mode(package, request) is SvgAnnotationMode.DEVELOPER_IDS
    )
    for anchor in package.position_anchors:
        if anchor.floor_id != floor_id or not _layered_visible(
            anchor, layers, request.audience
        ):
            continue
        if not developer_mode and (
            request.audience is RenderAudience.PLAYER
            or anchor.kind is not PositionAnchorKind.ENTRANCE
        ):
            continue
        component = _component_group(
            group,
            anchor,
            "position-anchor" if developer_mode else "dungeon-start",
            rendered_ids,
        )
        component.set("data-anchor-kind", anchor.kind.value)
        if developer_mode:
            ET.SubElement(
                component,
                "circle",
                {
                    "class": "marker",
                    "cx": str(anchor.position.x * scale),
                    "cy": str(anchor.position.y * scale),
                    "r": _number(scale * 0.18),
                },
            )
        else:
            _append_start_symbol(component, anchor.position, scale)
    for slot in package.encounter_slots:
        if (
            request.audience is RenderAudience.PLAYER
            or slot.floor_id != floor_id
            or not _layered_visible(slot, layers, request.audience)
        ):
            continue
        position = None
        if slot.anchor_ids:
            slot_anchor = anchors.get(slot.anchor_ids[0])
            if slot_anchor is not None:
                position = slot_anchor.position
        if position is None:
            room = rooms[slot.room_id]
            center = _polygon_center(room.boundary)
            position = GridPoint(x=int(center[0]), y=int(center[1]))
        component = _component_group(group, slot, "encounter-slot", rendered_ids)
        half = scale * 0.2
        ET.SubElement(
            component,
            "rect",
            {
                "class": "marker",
                "x": _number(position.x * scale - half),
                "y": _number(position.y * scale - half),
                "width": _number(half * 2),
                "height": _number(half * 2),
            },
        )
        label = ET.SubElement(
            component,
            "text",
            {
                "class": "encounter-slot-label",
                "x": _number(position.x * scale),
                "y": _number(position.y * scale + scale * 0.1),
                "font-size": _number(scale * 0.24),
                "text-anchor": "middle",
                "data-encounter-slot-label": "E",
            },
        )
        label.text = "E"


def _append_start_symbol(
    parent: ET.Element,
    point: GridPoint,
    scale: int,
) -> None:
    _append_start_symbol_at(
        parent,
        point.x * scale,
        point.y * scale,
        scale * 0.34,
    )


def _append_start_symbol_at(
    parent: ET.Element,
    x: float,
    y: float,
    size: float,
) -> None:
    """Draw a table-facing start flag, never a generic technical anchor circle."""

    pole_x = x - size * 0.32
    top = y - size * 0.55
    ET.SubElement(
        parent,
        "line",
        {
            "class": "start-marker",
            "x1": _number(pole_x),
            "y1": _number(top),
            "x2": _number(pole_x),
            "y2": _number(y + size * 0.58),
        },
    )
    ET.SubElement(
        parent,
        "polygon",
        {
            "class": "start-marker",
            "points": f"{_number(pole_x)},{_number(top)} "
            f"{_number(x + size * 0.55)},{_number(y - size * 0.28)} "
            f"{_number(pole_x)},{_number(y)}",
        },
    )


def _append_room_mechanic_symbol(
    parent: ET.Element,
    point: GridPoint,
    kind: RoomMechanicMarkerKind,
    scale: int,
) -> None:
    """Render trusted, grayscale-safe symbols without prose-bearing metadata."""

    x, y = point.x * scale, point.y * scale
    half = scale * 0.23
    if kind is RoomMechanicMarkerKind.TRAP:
        ET.SubElement(
            parent,
            "polygon",
            {
                "class": "hazard",
                "points": f"{_number(x)},{_number(y - half)} "
                f"{_number(x + half)},{_number(y + half)} "
                f"{_number(x - half)},{_number(y + half)}",
            },
        )
    elif kind is RoomMechanicMarkerKind.PUZZLE:
        ET.SubElement(
            parent,
            "polygon",
            {
                "class": "marker",
                "points": f"{_number(x)},{_number(y - half)} "
                f"{_number(x + half)},{_number(y)} "
                f"{_number(x)},{_number(y + half)} "
                f"{_number(x - half)},{_number(y)}",
            },
        )
    elif kind is RoomMechanicMarkerKind.OBJECTIVE:
        ET.SubElement(
            parent,
            "circle",
            {
                "class": "marker objective",
                "cx": _number(x),
                "cy": _number(y),
                "r": _number(half),
            },
        )
    else:
        ET.SubElement(
            parent,
            "rect",
            {
                "class": "feature",
                "x": _number(x - half),
                "y": _number(y - half),
                "width": _number(half * 2),
                "height": _number(half * 2),
            },
        )


def _append_transition_symbol(
    parent: ET.Element,
    point: GridPoint,
    symbol_text: str,
    scale: int,
) -> None:
    ET.SubElement(
        parent,
        "circle",
        {
            "class": "stair",
            "cx": str(point.x * scale),
            "cy": str(point.y * scale),
            "r": _number(scale * 0.28),
        },
    )
    text = ET.SubElement(
        parent,
        "text",
        {
            "class": "annotation",
            "x": str(point.x * scale),
            "y": _number(point.y * scale + scale * 0.1),
            "text-anchor": "middle",
            "data-kind": "transition-symbol",
        },
    )
    text.text = {
        StairDirection.UP.value: "↑",
        StairDirection.DOWN.value: "↓",
        StairDirection.BOTH.value: "↕",
    }.get(symbol_text, "↕")


def _append_geometry(
    parent: ET.Element,
    geometry: MapGeometry,
    scale: int,
    css_class: str,
) -> None:
    if isinstance(geometry, PointGeometry):
        ET.SubElement(
            parent,
            "circle",
            {
                "class": css_class,
                "cx": str(geometry.point.x * scale),
                "cy": str(geometry.point.y * scale),
                "r": _number(scale * 0.2),
            },
        )
    elif isinstance(geometry, SegmentGeometry):
        ET.SubElement(
            parent,
            "line",
            {
                "class": css_class,
                "x1": str(geometry.segment.start.x * scale),
                "y1": str(geometry.segment.start.y * scale),
                "x2": str(geometry.segment.end.x * scale),
                "y2": str(geometry.segment.end.y * scale),
            },
        )
    elif isinstance(geometry, PolylineGeometry):
        ET.SubElement(
            parent,
            "polyline",
            {
                "class": css_class,
                "points": _points(geometry.points, scale),
            },
        )
    elif isinstance(geometry, PolygonGeometry):
        ET.SubElement(
            parent,
            "polygon",
            {
                "class": css_class,
                "points": _points(geometry.points, scale),
            },
        )
    elif isinstance(geometry, RectangleGeometry):
        ET.SubElement(
            parent,
            "rect",
            {
                "class": css_class,
                "x": str(geometry.origin.x * scale),
                "y": str(geometry.origin.y * scale),
                "width": str(geometry.width_cells * scale),
                "height": str(geometry.height_cells * scale),
            },
        )


def _component_group(
    parent: ET.Element,
    component: LayeredMapElement,
    kind: str,
    rendered_ids: list[str],
) -> ET.Element:
    rendered_ids.append(component.id)
    return ET.SubElement(
        parent,
        "g",
        {
            "id": _xml_id(component.id),
            "data-component-id": component.id,
            "data-kind": kind,
            "data-layer-id": component.layer_id,
            "data-visibility": component.visibility.value,
        },
    )


def _layered_visible(
    component: LayeredMapElement,
    layers: dict[str, RenderLayer],
    audience: RenderAudience,
) -> bool:
    layer = layers[component.layer_id]
    if audience is RenderAudience.DM:
        return layer.include_in_dm_export
    return (
        component.visibility is Visibility.PLAYER_SAFE
        and layer.visibility is Visibility.PLAYER_SAFE
        and layer.include_in_player_export
    )


def _nonlayered_visible(
    component: VerticalLinkLayout,
    audience: RenderAudience,
) -> bool:
    return (
        audience is RenderAudience.DM or component.visibility is Visibility.PLAYER_SAFE
    )


def _points(points: tuple[GridPoint, ...], scale: int) -> str:
    return " ".join(f"{point.x * scale},{point.y * scale}" for point in points)


def _polygon_center(polygon: PolygonGeometry) -> tuple[float, float]:
    return (
        sum(point.x for point in polygon.points) / len(polygon.points),
        sum(point.y for point in polygon.points) / len(polygon.points),
    )


def _segment_midpoint(first: GridPoint, second: GridPoint) -> tuple[float, float]:
    return ((first.x + second.x) / 2, (first.y + second.y) / 2)


def _segment_key_points(
    start: tuple[int, int],
    end: tuple[int, int],
) -> tuple[int, int, int, int]:
    first, second = sorted((start, end))
    return (*first, *second)


def _xml_id(component_id: str) -> str:
    readable = re.sub(r"[^A-Za-z0-9_-]+", "-", component_id).strip("-")[:32]
    digest = hashlib.sha256(component_id.encode("utf-8")).hexdigest()[:10]
    return f"component-{readable or 'item'}-{digest}"


def _number(value: float) -> str:
    return f"{value:g}"


def _diagnostic(
    code: SvgRenderDiagnosticCode,
    affected_ids: Iterable[str],
    message: str,
    repair_hint: str,
    source_code: str | None = None,
) -> SvgRenderDiagnostic:
    return SvgRenderDiagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        affected_ids=tuple(sorted(set(affected_ids))),
        repair_hint=repair_hint,
        source_code=source_code,
    )


def _failed_result(
    package: DungeonPackage,
    request: SvgRenderRequest,
    diagnostics: list[SvgRenderDiagnostic],
) -> SvgRenderResult:
    return SvgRenderResult(
        schema_version=SVG_RENDER_RESULT_SCHEMA_VERSION,
        renderer_version=SVG_RENDERER_VERSION,
        package_id=package.id,
        floor_id=request.floor_id,
        audience=request.audience,
        success=False,
        width_pixels=None,
        height_pixels=None,
        svg=None,
        sha256=None,
        rendered_component_ids=(),
        diagnostics=tuple(
            sorted(
                diagnostics,
                key=lambda item: (item.code.value, item.affected_ids, item.message),
            )
        ),
    )
