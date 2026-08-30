"""ReportLab drawing adapter for the trusted deterministic SVG subset."""

import xml.etree.ElementTree as ET

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]


def draw_svg(canvas: Canvas, svg: str) -> None:
    """Draw filtered SVG primitives into the canvas's current transform."""
    root = ET.fromstring(svg)
    for element in root.iter():
        tag = _local_name(element.tag)
        css_classes = set(element.attrib.get("class", "").split())
        if tag == "line":
            _set_line_style(canvas, css_classes, element.attrib)
            canvas.line(
                float(element.attrib["x1"]),
                float(element.attrib["y1"]),
                float(element.attrib["x2"]),
                float(element.attrib["y2"]),
            )
        elif tag == "polyline":
            points = _parse_points(element.attrib.get("points", ""))
            if len(points) >= 2:
                _set_line_style(canvas, css_classes, element.attrib)
                path = canvas.beginPath()
                path.moveTo(*points[0])
                for point in points[1:]:
                    path.lineTo(*point)
                canvas.drawPath(path, stroke=1, fill=0)
        elif tag == "polygon":
            points = _parse_points(element.attrib.get("points", ""))
            if len(points) >= 3:
                fill, stroke, width = _shape_style(css_classes)
                path = canvas.beginPath()
                path.moveTo(*points[0])
                for point in points[1:]:
                    path.lineTo(*point)
                path.close()
                _set_shape_style(canvas, fill, stroke, width)
                canvas.drawPath(
                    path,
                    stroke=1 if stroke is not None else 0,
                    fill=1 if fill is not None else 0,
                )
        elif tag == "rect":
            x = float(element.attrib.get("x", "0"))
            y = float(element.attrib.get("y", "0"))
            width_value = float(element.attrib["width"])
            height_value = float(element.attrib["height"])
            fill, stroke, line_width = _shape_style(css_classes)
            _set_shape_style(canvas, fill, stroke, line_width)
            canvas.rect(
                x,
                y,
                width_value,
                height_value,
                stroke=1 if stroke is not None else 0,
                fill=1 if fill is not None else 0,
            )
        elif tag == "circle":
            center_x = float(element.attrib["cx"])
            center_y = float(element.attrib["cy"])
            radius = float(element.attrib["r"])
            fill, stroke, line_width = _shape_style(css_classes)
            _set_shape_style(canvas, fill, stroke, line_width)
            canvas.circle(
                center_x,
                center_y,
                radius,
                stroke=1 if stroke is not None else 0,
                fill=1 if fill is not None else 0,
            )
        elif tag == "text" and element.text:
            _draw_text(canvas, element, css_classes)


def _draw_text(canvas: Canvas, element: ET.Element, css_classes: set[str]) -> None:
    x = float(element.attrib.get("x", "0"))
    y = float(element.attrib.get("y", "0"))
    size = float(
        element.attrib.get("font-size", "10" if "annotation" in css_classes else "12")
    )
    canvas.saveState()
    canvas.translate(x, y)
    canvas.scale(1, -1)
    canvas.setFillColor(colors.HexColor("#333333"))
    canvas.setFont("Helvetica", size)
    text = element.text or ""
    if element.attrib.get("text-anchor") == "middle":
        canvas.drawCentredString(0, -size * 0.35, text)
    else:
        canvas.drawString(0, -size * 0.35, text)
    canvas.restoreState()


def _set_line_style(
    canvas: Canvas,
    css_classes: set[str],
    attributes: dict[str, str],
) -> None:
    width = float(attributes.get("stroke-width", "1"))
    canvas.setLineWidth(width)
    canvas.setDash()
    if "grid-line" in css_classes:
        canvas.setStrokeColor(colors.HexColor("#d2d2d2"))
        canvas.setLineWidth(0.5)
    elif "passage-opening" in css_classes:
        canvas.setStrokeColor(colors.white)
    elif "corridor" in css_classes and "corridor-outline" not in css_classes:
        canvas.setStrokeColor(colors.white)
    elif "door-secret" in css_classes:
        canvas.setStrokeColor(colors.HexColor("#555555"))
        canvas.setDash(4, 3)
    elif "door-trapped" in css_classes:
        canvas.setStrokeColor(colors.HexColor("#111111"))
        canvas.setDash(2, 2)
    else:
        canvas.setStrokeColor(colors.HexColor("#111111"))


def _shape_style(
    css_classes: set[str],
) -> tuple[str | None, str | None, float]:
    if "map-background" in css_classes:
        return "#ffffff", None, 1
    if "map-legend-panel" in css_classes:
        return "#ffffff", "#111111", 1.5
    if "room" in css_classes:
        return None, "#111111", 2
    if "corridor" in css_classes and "corridor-outline" not in css_classes:
        return "#ffffff", None, 1
    if "terrain" in css_classes:
        return "#eeeeee", "#777777", 1
    if "zone" in css_classes:
        return None, "#777777", 1
    if css_classes & {
        "feature",
        "marker",
        "stair",
        "room-callout",
        "component-callout",
        "feature-callout",
        "callout-badge-shape",
        "legend-symbol",
    }:
        return "#ffffff", "#111111", 1.5
    if "hazard" in css_classes:
        return None, "#111111", 2
    return None, "#111111", 1


def _set_shape_style(
    canvas: Canvas,
    fill: str | None,
    stroke: str | None,
    line_width: float,
) -> None:
    canvas.setLineWidth(line_width)
    canvas.setDash()
    if fill is not None:
        canvas.setFillColor(colors.HexColor(fill))
    if stroke is not None:
        canvas.setStrokeColor(colors.HexColor(stroke))


def _parse_points(value: str) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = []
    for pair in value.split():
        x, y = pair.split(",", maxsplit=1)
        points.append((float(x), float(y)))
    return tuple(points)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]
