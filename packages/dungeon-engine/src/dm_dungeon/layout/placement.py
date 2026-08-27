"""Exact rectangle helpers shared by constructive layout and package emission."""

from dataclasses import dataclass

from dm_dungeon.contracts.geometry import (
    GridPoint,
    PolygonGeometry,
    RectangleGeometry,
)
from dm_dungeon.layout.contracts import FloorLayoutBounds


@dataclass(frozen=True, slots=True)
class Rect:
    """Internal integer rectangle represented by origin and cell dimensions."""

    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


def rectangle_from_floor_bounds(bounds: FloorLayoutBounds) -> RectangleGeometry:
    """Convert floor bounds to exact renderer-neutral geometry."""

    return RectangleGeometry(
        kind="rectangle",
        origin=GridPoint(x=0, y=0),
        width_cells=bounds.width_cells,
        height_cells=bounds.height_cells,
    )


def polygon_from_rect(rect: Rect) -> PolygonGeometry:
    """Convert an internal rectangle to a four-corner polygon."""

    return PolygonGeometry(
        kind="polygon",
        points=(
            GridPoint(x=rect.x, y=rect.y),
            GridPoint(x=rect.right, y=rect.y),
            GridPoint(x=rect.right, y=rect.bottom),
            GridPoint(x=rect.x, y=rect.bottom),
        ),
    )
