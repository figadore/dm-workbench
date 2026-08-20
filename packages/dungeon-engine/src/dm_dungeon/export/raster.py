"""Deterministic Pillow rasterization of the filtered SVG subset."""

import io
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


def rasterize_svg(svg: str, dpi: int) -> bytes:
    """Rasterize the trusted SVG subset emitted by the pinned SVG renderer."""
    root = ET.fromstring(svg)
    width = int(root.attrib["width"])
    height = int(root.attrib["height"])
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    for element in root.iter():
        tag = _local_name(element.tag)
        css_classes = set(element.attrib.get("class", "").split())
        if tag == "line":
            line_coordinates = (
                float(element.attrib["x1"]),
                float(element.attrib["y1"]),
                float(element.attrib["x2"]),
                float(element.attrib["y2"]),
            )
            color, width_px = _line_style(css_classes, element.attrib)
            if {"door-secret", "door-trapped"} & css_classes:
                _draw_dashed_line(draw, line_coordinates, color, width_px)
            else:
                draw.line(line_coordinates, fill=color, width=width_px)
        elif tag == "polyline":
            polyline_points = _parse_points(element.attrib.get("points", ""))
            color, width_px = _line_style(css_classes, element.attrib)
            if len(polyline_points) >= 2:
                draw.line(
                    polyline_points,
                    fill=color,
                    width=width_px,
                    joint="curve",
                )
        elif tag == "polygon":
            polygon_points = _parse_points(element.attrib.get("points", ""))
            if len(polygon_points) >= 3:
                fill, outline, width_px = _shape_style(css_classes)
                if fill is not None:
                    draw.polygon(polygon_points, fill=fill)
                if outline is not None:
                    draw.line(
                        (*polygon_points, polygon_points[0]),
                        fill=outline,
                        width=width_px,
                        joint="curve",
                    )
        elif tag == "rect":
            x = float(element.attrib.get("x", "0"))
            y = float(element.attrib.get("y", "0"))
            rectangle = (
                x,
                y,
                x + float(element.attrib["width"]),
                y + float(element.attrib["height"]),
            )
            fill, outline, width_px = _shape_style(css_classes)
            draw.rectangle(rectangle, fill=fill, outline=outline, width=width_px)
        elif tag == "circle":
            center_x = float(element.attrib["cx"])
            center_y = float(element.attrib["cy"])
            radius = float(element.attrib["r"])
            fill, outline, width_px = _shape_style(css_classes)
            draw.ellipse(
                (
                    center_x - radius,
                    center_y - radius,
                    center_x + radius,
                    center_y + radius,
                ),
                fill=fill,
                outline=outline,
                width=width_px,
            )
        elif tag == "text" and element.text:
            x = float(element.attrib.get("x", "0"))
            y = float(element.attrib.get("y", "0"))
            color = "#111111" if "annotation" not in css_classes else "#444444"
            anchor = "mm" if element.attrib.get("text-anchor") == "middle" else "ls"
            try:
                draw.text((x, y), element.text, fill=color, font=font, anchor=anchor)
            except UnicodeEncodeError:
                draw.text((x, y), "?", fill=color, font=font, anchor=anchor)

    output = io.BytesIO()
    image.save(
        output,
        format="PNG",
        optimize=False,
        compress_level=9,
        dpi=(dpi, dpi),
    )
    return output.getvalue()


def png_dimensions(data: bytes) -> tuple[int, int]:
    """Read dimensions from PNG bytes without mutating them."""
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def ink_coverage_basis_points(data: bytes) -> int:
    """Estimate dark-pixel coverage in hundredths of a percent."""
    with Image.open(io.BytesIO(data)) as source:
        grayscale = source.convert("L")
        histogram = grayscale.histogram()
        dark_pixels = sum(histogram[:245])
        total_pixels = source.width * source.height
    if total_pixels == 0:
        return 0
    return (dark_pixels * 10000 + total_pixels // 2) // total_pixels


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _parse_points(value: str) -> tuple[tuple[float, float], ...]:
    points: list[tuple[float, float]] = []
    for pair in value.split():
        x, y = pair.split(",", maxsplit=1)
        points.append((float(x), float(y)))
    return tuple(points)


def _line_style(
    css_classes: set[str],
    attributes: dict[str, str],
) -> tuple[str, int]:
    requested_width = float(attributes.get("stroke-width", "1"))
    width = max(1, round(requested_width))
    if "grid-line" in css_classes:
        return "#d2d2d2", 1
    if "corridor" in css_classes and "corridor-outline" not in css_classes:
        return "#ffffff", width
    if "door-secret" in css_classes:
        return "#555555", width
    return "#111111", width


def _shape_style(css_classes: set[str]) -> tuple[str | None, str | None, int]:
    if "map-background" in css_classes:
        return "#ffffff", None, 1
    if "room" in css_classes:
        return None, "#111111", 2
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
    }:
        return "#ffffff", "#111111", 2
    if "hazard" in css_classes or "hazard-callout" in css_classes:
        return None, "#111111", 2
    return None, "#111111", 1


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    points: tuple[float, float, float, float],
    color: str,
    width: int,
) -> None:
    x1, y1, x2, y2 = points
    length = abs(x2 - x1) + abs(y2 - y1)
    if length <= 0:
        return
    dash = 4.0
    gap = 3.0
    cursor = 0.0
    while cursor < length:
        end = min(length, cursor + dash)
        start_ratio = cursor / length
        end_ratio = end / length
        draw.line(
            (
                x1 + (x2 - x1) * start_ratio,
                y1 + (y2 - y1) * start_ratio,
                x1 + (x2 - x1) * end_ratio,
                y1 + (y2 - y1) * end_ratio,
            ),
            fill=color,
            width=width,
        )
        cursor += dash + gap
